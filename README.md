# PhotoSquareFrame

一个使用 Python、PySide6 和 Pillow 制作的 macOS 图片加白色正方形边框工具。

依赖安装在项目的 `.venv` 虚拟环境中，不会修改系统 Python。

## 本地运行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## 打包 DMG

```bash
chmod +x build_dmg.sh
./build_dmg.sh
```

生成的 `PhotoSquareFrame.dmg` 会直接放到桌面；`.app` 构建产物仍位于 `dist/`。边框宽度按照片最长边的百分比计算，默认 5%。
