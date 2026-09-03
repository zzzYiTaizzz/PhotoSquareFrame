#!/bin/zsh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
export PYINSTALLER_CONFIG_DIR="$SCRIPT_DIR/.pyinstaller"
USER_HOME="$(cd ~ && pwd)"
DESKTOP_DIR="$USER_HOME/Desktop"
mkdir -p "$DESKTOP_DIR"
if [[ ! -x "$SCRIPT_DIR/.venv/bin/python" ]]; then
  echo "请先运行：python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi
"$SCRIPT_DIR/.venv/bin/python" -m PyInstaller --windowed --name PhotoSquareFrame --clean --noconfirm main.py
DMG_NAME="PhotoSquareFrame-macOS-arm64.dmg"
hdiutil create -volname "PhotoSquareFrame" -srcfolder "dist/PhotoSquareFrame.app" -ov -format UDZO "$DESKTOP_DIR/$DMG_NAME"
echo "Created: $DESKTOP_DIR/$DMG_NAME"
