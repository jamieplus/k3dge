#!/usr/bin/env sh
# 构建零依赖单件：dist/k3dge.pyz（stdlib zipapp；无需 shiv/PyInstaller/uv）。
# 用途：下游仓 / 无 venv 宿主 直接 `python dist/k3dge.pyz …`。发行物，不入库（.gitignore dist/）。
set -eu
cd "$(dirname "$0")/.."
mkdir -p dist
PY="${PYTHON:-python3}"
# 产物 shebang 可配（缺省 env python3）；与构建解释器不一致时提示——下游无 `python3` 或版本 < 3.10
# 会在**别人的机器上**启动失败，且很难归因（ocr-013）。
SHEBANG="${PYZ_SHEBANG:-/usr/bin/env python3}"
"$PY" -m zipapp src -m "k3dge.cli.main:main" -p "$SHEBANG" -o dist/k3dge.pyz
chmod +x dist/k3dge.pyz
echo "built dist/k3dge.pyz ($(wc -c < dist/k3dge.pyz) bytes)"
