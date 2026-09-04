from __future__ import annotations

import sys
import os
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageOps
from PySide6.QtCore import QThread, Qt, Signal, QTimer
from PySide6.QtGui import QFontDatabase, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressDialog,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from updater import UpdateInfo, download_update, fetch_update, format_error
from version import APP_VERSION


SUPPORTED = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}


class UpdateCheckWorker(QThread):
    found = Signal(object)
    failed = Signal(str)

    def run(self) -> None:
        try:
            self.found.emit(fetch_update())
        except Exception as exc:
            self.failed.emit(format_error(exc))


class UpdateDownloadWorker(QThread):
    progress = Signal(int)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, info: UpdateInfo) -> None:
        super().__init__()
        self.info = info

    def run(self) -> None:
        try:
            path = download_update(self.info, self.emit_progress)
            self.completed.emit(str(path))
        except Exception as exc:
            self.failed.emit(format_error(exc))

    def emit_progress(self, value: int) -> None:
        if self.isInterruptionRequested():
            raise InterruptedError("下载已取消。")
        self.progress.emit(value)


def add_square_frame(source: Path, percent: float, rotation: int = 0) -> Image.Image:
    """Rotate the photo, then fit it on a square white canvas with a frame."""
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened)
    if image.mode in {"RGBA", "LA", "PA"} or (image.mode == "P" and "transparency" in image.info):
        image = image.convert("RGBA")
        background = Image.new("RGBA", image.size, (255, 255, 255, 255))
        image = Image.alpha_composite(background, image)
    image = image.convert("RGB")
    if rotation % 360:
        image = image.rotate(rotation, expand=True)
    width, height = image.size
    longest = max(width, height)
    frame = round(longest * percent / 100)
    side = longest + frame * 2
    canvas = Image.new("RGB", (side, side), "white")
    canvas.paste(image, ((side - width) // 2, (side - height) // 2))
    return canvas


class DropList(QListWidget):
    pathsDropped = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.SingleSelection)

    def dragEnterEvent(self, event) -> None:
        if any(Path(url.toLocalFile()).suffix.lower() in SUPPORTED for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls()]
        self.pathsDropped.emit([p for p in paths if p.suffix.lower() in SUPPORTED])
        event.acceptProposedAction()


class DropPreview(QLabel):
    pathsDropped = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return width

    def sizeHint(self):
        size = super().sizeHint()
        side = max(size.width(), size.height(), 480)
        return size.expandedTo(size.__class__(side, side))

    def dragEnterEvent(self, event) -> None:
        if any(Path(url.toLocalFile()).suffix.lower() in SUPPORTED for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls()]
        self.pathsDropped.emit([p for p in paths if p.suffix.lower() in SUPPORTED])
        event.acceptProposedAction()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Photo Square Frame")
        self.resize(980, 650)
        self.paths: list[Path] = []
        self.rotations: list[int] = []
        self.update_check_worker: UpdateCheckWorker | None = None
        self.update_download_worker: UpdateDownloadWorker | None = None
        self.update_info: UpdateInfo | None = None
        self.update_progress: QProgressDialog | None = None

        help_menu = self.menuBar().addMenu("帮助")
        about_action = help_menu.addAction("关于 Photo Square Frame")
        about_action.triggered.connect(self.show_about)
        check_update_action = help_menu.addAction("检查更新")
        check_update_action.triggered.connect(lambda: self.check_for_updates(False))

        self.file_list = DropList()
        self.file_list.setMinimumWidth(260)
        self.file_list.currentRowChanged.connect(self.update_preview)
        self.file_list.pathsDropped.connect(self.add_paths)

        self.preview = DropPreview()
        self.preview.setText("选择或拖入图片")
        self.preview.pathsDropped.connect(self.add_paths)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(480, 480)
        self.preview.setStyleSheet("background:#000; color:#fff; border:1px solid #444;")

        self.percent = QSlider(Qt.Horizontal)
        self.percent.setRange(0, 100)
        self.percent.setValue(5)
        self.percent.setSingleStep(1)
        self.percent.valueChanged.connect(lambda _value: self.update_preview(self.file_list.currentRow()))
        self.percent_label = QLabel("5%")
        self.percent.valueChanged.connect(lambda value: self.percent_label.setText(f"{value}%"))

        self.add_button = QPushButton("添加图片")
        self.add_button.clicked.connect(self.choose_files)
        self.clear_button = QPushButton("清空")
        self.clear_button.clicked.connect(self.clear_paths)
        self.export_button = QPushButton("导出全部")
        self.export_button.clicked.connect(self.export_all)
        rotate_button_side = self.add_button.sizeHint().height()
        self.rotate_left_button = QPushButton("⟲")
        self.rotate_left_button.setToolTip("左旋转")
        self.rotate_left_button.setFixedSize(rotate_button_side, rotate_button_side)
        self.rotate_left_button.clicked.connect(lambda: self.rotate_current(90))
        self.rotate_right_button = QPushButton("⟳")
        self.rotate_right_button.setToolTip("右旋转")
        self.rotate_right_button.setFixedSize(rotate_button_side, rotate_button_side)
        self.rotate_right_button.clicked.connect(lambda: self.rotate_current(-90))

        left = QVBoxLayout()
        left.addWidget(QLabel("图片列表"))
        left.addWidget(self.file_list)
        buttons = QHBoxLayout()
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.clear_button)
        left.addLayout(buttons)

        right = QVBoxLayout()
        right.addWidget(self.preview, 1)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("边框宽度"))
        controls.addWidget(self.percent)
        controls.addWidget(self.percent_label)
        controls.addWidget(self.rotate_left_button)
        controls.addWidget(self.rotate_right_button)
        controls.addStretch()
        controls.addWidget(self.export_button)
        right.addLayout(controls)

        root = QWidget()
        layout = QHBoxLayout(root)
        layout.addLayout(left)
        layout.addLayout(right, 1)
        self.setCentralWidget(root)
        QTimer.singleShot(1500, lambda: self.check_for_updates(True))

    def show_about(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("关于 Photo Square Frame")
        dialog.setMinimumWidth(440)

        layout = QVBoxLayout(dialog)
        title = QLabel("Photo Square Frame")
        title.setStyleSheet("font-size:20px; font-weight:bold;")
        layout.addWidget(title)
        layout.addWidget(QLabel(f"版本：v{APP_VERSION}"))
        layout.addWidget(QLabel("Copyright (c) 2026 zzzYiTaizzz and Dieryao"))
        layout.addWidget(QLabel("Licensed under the MIT License."))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        license_button = buttons.addButton("查看许可证", QDialogButtonBox.ButtonRole.ActionRole)
        update_button = buttons.addButton("检查更新", QDialogButtonBox.ButtonRole.ActionRole)
        license_button.clicked.connect(lambda _checked=False: self.show_license(dialog))
        update_button.clicked.connect(lambda _checked=False: (dialog.close(), self.check_for_updates(False)))
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def show_license(self, parent: QWidget) -> None:
        candidates = [
            Path(__file__).with_name("LICENSE"),
            Path(sys.executable).parent / "LICENSE.txt",
            Path(sys.executable).parent.parent / "Resources" / "LICENSE.txt",
        ]
        text = "许可证文件未找到。"
        for candidate in candidates:
            if candidate.is_file():
                text = candidate.read_text(encoding="utf-8")
                break
        dialog = QDialog(parent)
        dialog.setWindowTitle("MIT License")
        dialog.setMinimumSize(820, 560)
        layout = QVBoxLayout(dialog)
        license_view = QPlainTextEdit()
        license_view.setReadOnly(True)
        license_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        license_view.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        license_view.setPlainText(text)
        layout.addWidget(license_view)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def check_for_updates(self, silent: bool = False) -> None:
        if self.update_check_worker and self.update_check_worker.isRunning():
            return
        self.update_check_worker = UpdateCheckWorker()
        self.update_check_worker.found.connect(lambda info: self.update_check_finished(info, silent))
        self.update_check_worker.failed.connect(lambda message: self.update_check_failed(message, silent))
        self.update_check_worker.start()

    def update_check_finished(self, info: UpdateInfo | None, silent: bool) -> None:
        if info is None:
            if not silent:
                QMessageBox.information(self, "检查更新", f"当前已是最新版本（v{APP_VERSION}）。")
            return
        self.update_info = info
        notes = info.notes.strip()
        if len(notes) > 800:
            notes = notes[:800].rstrip() + "..."
        details = f"发现新版本 v{info.version}\n\n{notes}" if notes else f"发现新版本 v{info.version}。"
        answer = QMessageBox.question(self, "发现新版本", details + "\n\n是否下载更新？")
        if answer == QMessageBox.StandardButton.Yes:
            self.download_update()

    def update_check_failed(self, message: str, silent: bool) -> None:
        if not silent:
            QMessageBox.warning(self, "检查更新失败", message)

    def download_update(self) -> None:
        if not self.update_info or (self.update_download_worker and self.update_download_worker.isRunning()):
            return
        self.update_progress = QProgressDialog("正在下载更新...", "取消", 0, 100, self)
        self.update_progress.setWindowTitle("下载更新")
        self.update_progress.setAutoClose(False)
        self.update_progress.setValue(0)
        self.update_progress.canceled.connect(self.cancel_update_download)
        self.update_download_worker = UpdateDownloadWorker(self.update_info)
        self.update_download_worker.progress.connect(self.update_progress.setValue)
        self.update_download_worker.completed.connect(self.update_download_finished)
        self.update_download_worker.failed.connect(self.update_download_failed)
        self.update_download_worker.start()

    def cancel_update_download(self) -> None:
        if self.update_download_worker and self.update_download_worker.isRunning():
            self.update_download_worker.requestInterruption()
        if self.update_progress:
            self.update_progress.close()

    def update_download_finished(self, path: str) -> None:
        if self.update_progress:
            self.update_progress.close()
        update_path = Path(path)
        QMessageBox.information(self, "下载完成", f"更新文件已校验完成：\n{update_path.name}")
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", str(update_path)])
            elif sys.platform == "win32":
                os.startfile(str(update_path))
            else:
                subprocess.Popen(["xdg-open", str(update_path)])
        except Exception as exc:
            QMessageBox.warning(self, "打开更新文件失败", str(exc))

    def update_download_failed(self, message: str) -> None:
        if self.update_progress:
            self.update_progress.close()
        QMessageBox.warning(self, "下载更新失败", message)

    def choose_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "选择图片", "", "图片 (*.jpg *.jpeg *.png *.tif *.tiff *.webp *.bmp)")
        self.add_paths([Path(f) for f in files])

    def add_paths(self, paths: list[Path]) -> None:
        existing = set(self.paths)
        added = False
        for path in paths:
            if path.is_file() and path.suffix.lower() in SUPPORTED and path not in existing:
                self.paths.append(path)
                self.rotations.append(0)
                self.file_list.addItem(QListWidgetItem(path.name))
                existing.add(path)
                added = True
        if added and self.file_list.currentRow() < 0:
            self.file_list.setCurrentRow(0)

    def clear_paths(self) -> None:
        self.paths.clear()
        self.rotations.clear()
        self.file_list.clear()
        self.preview.clear()
        self.preview.setText("选择或拖入图片")

    def rotate_current(self, degrees: int) -> None:
        row = self.file_list.currentRow()
        if row < 0 or row >= len(self.paths):
            return
        self.rotations[row] = (self.rotations[row] + degrees) % 360
        self.update_preview(row)

    def update_preview(self, row: int = -1) -> None:
        if row < 0 or row >= len(self.paths):
            return
        try:
            rotation = self.rotations[row]
            output = add_square_frame(self.paths[row], self.percent.value(), rotation)
            output.thumbnail((760, 520), Image.Resampling.LANCZOS)
            preview_path = Path(tempfile.gettempdir()) / "photosquareframe-preview.jpg"
            output.save(preview_path, quality=90)
            self.preview.setPixmap(QPixmap(str(preview_path)))
        except Exception as exc:
            self.preview.setText(f"无法读取图片：{exc}")

    def export_all(self) -> None:
        if not self.paths:
            QMessageBox.information(self, "提示", "请先添加图片。")
            return
        folder = QFileDialog.getExistingDirectory(self, "选择导出文件夹")
        if not folder:
            return
        failed: list[str] = []
        for row, source in enumerate(self.paths):
            try:
                output = add_square_frame(source, self.percent.value(), self.rotations[row])
                target = Path(folder) / f"{source.stem}_square{source.suffix.lower()}"
                if target.suffix not in {".jpg", ".jpeg", ".png"}:
                    target = target.with_suffix(".jpg")
                if target.suffix in {".jpg", ".jpeg"}:
                    output.save(target, quality=95)
                else:
                    output.save(target)
            except Exception:
                failed.append(source.name)
        if failed:
            QMessageBox.warning(self, "导出完成", "以下文件处理失败：\n" + "\n".join(failed))
        else:
            QMessageBox.information(self, "导出完成", f"已导出 {len(self.paths)} 张图片。")


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Photo Square Frame")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
