#!/usr/bin/env sh
# 构建零依赖单件：dist/k3dge.pyz（stdlib zipapp；无需 shiv/PyInstaller/uv）。
# 用途：下游仓 / 无 venv 宿主 直接 `python dist/k3dge.pyz …`。发行物，不入库（.gitignore dist/）。
set -eu
cd "$(dirname "$0")/.."
mkdir -p dist
PY="${PYTHON:-python3}"
# preflight：必须是可用、>=3.10 的 Python（与 pyproject requires-python 对齐）；否则清晰报错（ocr-138）。
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "[build-pyz] PYTHON='$PY' 不可执行（不存在或不在 PATH）" >&2
  exit 1
fi
if ! "$PY" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
  echo "[build-pyz] PYTHON='$PY' 版本 < 3.10（pyproject 下限）" >&2
  exit 1
fi
# 敏感/本地文件不得随单件外发（zipapp 无 exclude ⇒ 打包前守一道；不粗暴排除所有点开头文件，
# 模板资产里有 .schema.json 等受版本控制的点文件，ocr-137）。
if find src -type f \( -name '.env' -o -name '*.key' -o -name '*.pem' -o -name '*.jsonl' \
     -o -name '*.db' -o -name '*.sqlite*' -o -name '.DS_Store' \) | grep -q .; then
  echo "[build-pyz] src/ 含本地/敏感文件，拒绝打包（见上）" >&2
  find src -type f \( -name '.env' -o -name '*.key' -o -name '*.pem' -o -name '*.jsonl' \
       -o -name '*.db' -o -name '*.sqlite*' -o -name '.DS_Store' \) >&2
  exit 1
fi
# 产物 shebang 可配（缺省 env python3）；与构建解释器不一致时提示——下游无 `python3` 或版本 < 3.10
# 会在**别人的机器上**启动失败，且很难归因（ocr-013）。
SHEBANG="${PYZ_SHEBANG:-/usr/bin/env python3}"
# 原子写：先写进程唯一临时文件，成功再 mv；中断不留半截"看起来合法"的产物（ocr-139）。
TMP="dist/.k3dge.pyz.$$"
trap 'rm -f "$TMP"' EXIT INT TERM
"$PY" -m zipapp src -m "k3dge.cli.main:main" -p "$SHEBANG" -o "$TMP"
# 冒烟：产物入口可运行（zipapp 不校验 main 存在，改名/移模块会产出"构建成功、下游一跑就崩"，ocr-140）。
if ! "$PY" "$TMP" -h >/dev/null 2>&1; then
  echo "[build-pyz] 冒烟失败：产物入口不可运行（检查 k3dge.cli.main:main）" >&2
  exit 1
fi
chmod +x "$TMP"
mv "$TMP" dist/k3dge.pyz
echo "built dist/k3dge.pyz ($(wc -c < dist/k3dge.pyz) bytes)"
