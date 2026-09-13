#!/usr/bin/env sh
# 构建零依赖单件：dist/k3dge.pyz（stdlib zipapp；无需 shiv/PyInstaller/uv）。
# 用途：下游仓 / 无 venv 宿主 直接 `python dist/k3dge.pyz …`。发行物，不入库（.gitignore dist/）。
set -eu
cd "$(dirname "$0")/.."
mkdir -p dist
PY="${PYTHON:-python3}"
"$PY" -m zipapp src -m "k3dge.cli.main:main" -p "/usr/bin/env python3" -o dist/k3dge.pyz
chmod +x dist/k3dge.pyz
echo "built dist/k3dge.pyz ($(wc -c < dist/k3dge.pyz) bytes)"
