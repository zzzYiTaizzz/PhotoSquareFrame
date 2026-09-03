from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageOps
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)


SUPPORTED = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}


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
