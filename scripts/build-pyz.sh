#!/usr/bin/env sh
# 构建零依赖单件：dist/k3dge.pyz（stdlib zipapp；无需 shiv/PyInstaller/uv）。
# 用途：下游仓 / 无 venv 宿主 直接 `python dist/k3dge.pyz …`。发行物，不入库（.gitignore dist/）。
set -eu
# `$0` 经软链/PATH 裸名调用时指向链接所在位置 ⇒ `cd ../` 落到与仓无关的目录，`mkdir -p dist`
# 就在那里造垃圾（373）。先把链接解成真实文件，再取物理根，最后**验根**：验不过就拒跑。
SELF="$0"
case "$SELF" in
  /*) ;;
  *) SELF="$(command -v -- "$SELF" 2>/dev/null || printf '%s' "$SELF")" ;;
esac
while [ -L "$SELF" ]; do
  LINK="$(readlink -- "$SELF")"
  case "$LINK" in
    /*) SELF="$LINK" ;;
    *) SELF="$(cd "$(dirname "$SELF")" && pwd -P)/$LINK" ;;
  esac
done
cd "$(dirname "$SELF")/.." || { echo "[build-pyz] 无法进入仓根（$SELF）" >&2; exit 1; }
if [ ! -f pyproject.toml ] || [ ! -d src/k3dge ]; then
  echo "[build-pyz] 推断的仓根 '$(pwd -P)' 不像 k3dge 仓（缺 pyproject.toml 或 src/k3dge）⇒ 拒跑" >&2
  exit 1
fi
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
# 敏感/本地文件不得随单件外发（zipapp CLI 无 exclude ⇒ 打包前守一道；不粗暴排除所有点开头文件，
# 模板资产里有 .schema.json 等受版本控制的点文件，ocr-137）。
# `.DS_Store`/`__pycache__`/`*.pyc` 是**派生垃圾**（Finder/解释器随手重建，拒建＝零收益摩擦、
# 还把测试绑死在构建机整洁度上）⇒ 从"拒绝"改为"打包时过滤"（见下 create_archive filter）。
if find src -type f \( -name '.env' -o -name '*.key' -o -name '*.pem' -o -name '*.jsonl' \
     -o -name '*.db' -o -name '*.sqlite*' \) | grep -q .; then
  echo "[build-pyz] src/ 含本地/敏感文件，拒绝打包（见上）" >&2
  find src -type f \( -name '.env' -o -name '*.key' -o -name '*.pem' -o -name '*.jsonl' \
       -o -name '*.db' -o -name '*.sqlite*' \) >&2
  exit 1
fi
# 产物 shebang 可配（缺省 env python3）；与构建解释器不一致时提示——下游无 `python3` 或版本 < 3.10
# 会在**别人的机器上**启动失败，且很难归因（ocr-013）。
SHEBANG="${PYZ_SHEBANG:-/usr/bin/env python3}"
# 原子写：先写进程唯一临时文件，成功再 mv；中断不留半截"看起来合法"的产物（ocr-139）。
TMP="dist/.k3dge.pyz.$$"
trap 'rm -f "$TMP"' EXIT INT TERM
# 入口必须是仓内 `src/__main__.py`：zipapp `--main` 生成的模板不调 `sys.exit(main())`，
# 返回码被吞 ⇒ 下游用 `.pyz` 跑 `check` 恒 0 退出＝分发件把闸读成常绿（t-023 实测）。
if [ ! -f src/__main__.py ]; then
  echo "[build-pyz] 缺 src/__main__.py（入口必须 sys.exit(main())；zipapp --main 模板不包办）" >&2
  exit 1
fi
# zipapp CLI 无 exclude ⇒ 派生垃圾（__pycache__/.pyc/.DS_Store）不得随单件外发（t-020：旧产物实测 59 条）。
"$PY" -c 'import sys, zipapp
zipapp.create_archive("src", target=sys.argv[1], interpreter=sys.argv[2],
    filter=lambda p: "__pycache__" not in p.parts and p.suffix != ".pyc" and p.name != ".DS_Store")' "$TMP" "$SHEBANG"
# 冒烟①：产物入口可运行（zipapp 不校验 main 存在，改名/移模块会产出"构建成功、下游一跑就崩"，ocr-140）。
if ! "$PY" "$TMP" -h >/dev/null 2>&1; then
  echo "[build-pyz] 冒烟失败：产物入口不可运行（检查 src/__main__.py）" >&2
  exit 1
fi
# 冒烟②：退出码透传——空目录 `check` 必须**非零**。`-h` 由 argparse 自己 SystemExit(0)，
# 证明不了 main() 的返回值到达进程；这条才钉得住"入口 sys.exit"（t-023 的回归面）。
SMOKEY="$(mktemp -d)"
PYZ_ABS="$(pwd -P)/$TMP"
if ( cd "$SMOKEY" && "$PY" "$PYZ_ABS" check >/dev/null 2>&1 ); then
  echo "[build-pyz] 冒烟失败：空目录 check 退出 0——main() 返回码被吞，下游闸会常绿" >&2
  rm -rf "$SMOKEY"
  exit 1
fi
rm -rf "$SMOKEY"
chmod +x "$TMP"
mv "$TMP" dist/k3dge.pyz
echo "built dist/k3dge.pyz ($(wc -c < dist/k3dge.pyz) bytes)"
