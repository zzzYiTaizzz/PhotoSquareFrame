# PhotoSquareFrame

PhotoSquareFrame 是一个 macOS 图片处理工具，可以把横向或纵向照片放入正方形画布，并在四周添加白色边框。

## 功能

- 支持一次添加多张照片并批量处理
- 支持将图片拖入左侧列表或右侧预览区域
- 自动根据照片最长边生成正方形画布
- 自动校正照片的 EXIF 方向
- 使用水平滑块调整白色边框宽度
- 实时预览当前照片的处理效果
- 支持 JPG、JPEG、PNG、TIFF、WEBP 和 BMP
- 导出文件名自动添加 `_square` 后缀

## 边框规则

边框宽度按照照片最长边的百分比计算，默认值为 5%。

```text
边框宽度 = 照片最长边 × 百分比
最终正方形边长 = 照片最长边 + 2 × 边框宽度
```

例如，原图为 `1200 × 800`，边框设置为 `5%`：

```text
边框宽度：60 像素
输出尺寸：1320 × 1320
```

照片本身不会被裁剪，会在正方形画布中保持原始比例并居中放置。

## 使用方法

1. 打开 `PhotoSquareFrame.app`。
2. 点击“添加图片”，选择一张或多张照片；也可以直接拖入图片。
3. 在左侧列表中选择照片，在右侧查看预览。
4. 左右拖动“边框宽度”滑块调整边框大小。
5. 点击“导出全部”，选择输出文件夹。
6. 程序会生成带 `_square` 后缀的新文件，不会覆盖原图。

## 下载和首次打开

在 GitHub Releases 页面下载 `PhotoSquareFrame.dmg`，双击后将应用拖入“应用程序”文件夹即可。

当前发布版本面向 Apple Silicon（arm64）Mac。由于应用未加入 Apple Developer 签名和公证，首次打开时如果 macOS 显示“无法验证开发者”，请右键点击应用并选择“打开”。

## 本地开发和打包

项目使用 Python、PySide6 和 Pillow。运行开发版：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

生成 DMG：

```bash
./build_dmg.sh
```

DMG 会生成在桌面，应用构建产物位于 `dist/` 目录。
