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
# 管线退出码取自 `grep`：`find` 失败（不可读/无 find）时输出为空 ⇒ `grep -q .` 回 1 ⇒ 守卫静默通过（ocr2-008）。
# 先收 `find` 的输出并查它的退出码；失败即拒（fail-closed），不再看 grep。
# 另补 `.env.local`/`.env.*.local`（精确 `.env` 漏掉真实常见形态）。
if ! _found="$(find src -type f \( -name '.env' -o -name '.env.local' -o -name '.env.*.local' -o -name '*.key' -o -name '*.pem' -o -name '*.jsonl' -o -name '*.db' -o -name '*.sqlite*' \) 2>/dev/null)"; then
  echo "[build-pyz] 敏感件扫描的 find 失败（src 不可读/无 find？）⇒ 无法证明干净，拒绝打包" >&2
  exit 1
fi
if [ -n "$_found" ]; then
  echo "[build-pyz] src/ 含本地/敏感文件，拒绝打包（见下）" >&2
  printf '%s\n' "$_found" >&2
  exit 1
fi
# 产物 shebang 可配（缺省 env python3）；与构建解释器不一致时提示——下游无 `python3` 或版本 < 3.10
# 会在**别人的机器上**启动失败，且很难归因（ocr-013）。
SHEBANG="${PYZ_SHEBANG:-/usr/bin/env python3}"
# 原子写：先写进程唯一临时文件，成功再 mv；中断不留半截"看起来合法"的产物（ocr-139）。
TMP="dist/.k3dge.pyz.$$"
# 清理必须覆盖**所有**临时物（TMP + 冒烟目录 SMOKEY），且中断时要显式退出：
# POSIX shell 的 INT/TERM trap 跑完 handler 会**继续执行**下一条命令，只删文件不终止脚本
# 会让中断后的 zipapp/冒烟/mv 照常跑（mv 因源缺失而失败，报错误导归因）（ocr2-132）。
SMOKEY=""
cleanup() {
  rm -f "$TMP"
  if [ -n "$SMOKEY" ]; then
    rm -rf "$SMOKEY"
  fi
}
trap 'cleanup' EXIT
trap 'cleanup; exit 130' INT
trap 'cleanup; exit 143' TERM
# 入口必须是仓内 `src/__main__.py`：zipapp `--main` 生成的模板不调 `sys.exit(main())`，
# 返回码被吞 ⇒ 下游用 `.pyz` 跑 `check` 恒 0 退出＝分发件把闸读成常绿（t-023 实测）。
if [ ! -f src/__main__.py ]; then
  echo "[build-pyz] 缺 src/__main__.py（入口必须 sys.exit(main())；zipapp --main 模板不包办）" >&2
  exit 1
fi
# zipapp CLI 无 exclude ⇒ 派生垃圾不得随单件外发（t-020：旧产物实测 59 条）。过滤器是唯一屏障：
# 覆盖各解释器/工具链随手重建的缓存与备份，而不只是 __pycache__/.pyc/.DS_Store（ocr2-133）。
# 构建后再对产物断言一次：改了 filter 也不会静默漏掉（否则"过滤是否生效"全靠构建机整洁度）。
"$PY" -c 'import sys, zipapp, zipfile
_JUNK_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "htmlcov"}
_JUNK_SUFFIX = (".pyc", ".pyo", ".orig", ".swp", ".swo", ".egg-info")
_JUNK_NAMES = {".DS_Store", ".coverage"}
def _keep(p):
    if set(p.parts) & _JUNK_DIRS:
        return False
    if p.name in _JUNK_NAMES or p.name.endswith("~"):
        return False
    if p.suffix in _JUNK_SUFFIX:
        return False
    return True
zipapp.create_archive("src", target=sys.argv[1], interpreter=sys.argv[2], filter=_keep)
_bad = [n for n in zipfile.ZipFile(sys.argv[1]).namelist()
        if (set(n.split("/")) & _JUNK_DIRS)
        or n.endswith((".pyc", ".pyo", ".orig", ".swp", ".swo"))
        or n.endswith("/.coverage") or n == ".coverage"
        or n.endswith("/.DS_Store") or n.endswith("~")]
if _bad:
    sys.stderr.write("build-pyz: 派生物进入产物: %s\n" % _bad[:5])
    sys.exit(1)' "$TMP" "$SHEBANG"
# 冒烟①（shebang 轨）：**经产物自己的 shebang** 起进程。上面两条都用 `"$PY"` 显式起，shebang 从头到尾
# 没被执行过 ⇒ 写成 `python`、指向不存在的绝对路径、或带多参数（Linux 内核只接受单个可选参数）都会
# 构建成功，失败落在下游别人的机器上（ocr2-131）。
chmod +x "$TMP"
if ! "$TMP" -h >/dev/null 2>&1; then
  echo "[build-pyz] 冒烟失败：产物 shebang 不可执行（SHEBANG='$SHEBANG'；用 PYZ_SHEBANG 指定下游解释器）" >&2
  exit 1
fi
# 冒烟②：产物入口可运行（zipapp 不校验 main 存在，改名/移模块会产出"构建成功、下游一跑就崩"，ocr-140）。
if ! "$PY" "$TMP" -h >/dev/null 2>&1; then
  echo "[build-pyz] 冒烟失败：产物入口不可运行（检查 src/__main__.py）" >&2
  exit 1
fi
# 冒烟③：退出码透传——空目录 `check` 必须**非零**。`-h` 由 argparse 自己 SystemExit(0)，
# 证明不了 main() 的返回值到达进程；这条才钉得住"入口 sys.exit"（t-023 的回归面）。
SMOKEY="$(mktemp -d)"
PYZ_ABS="$(pwd -P)/$TMP"
# `cd` 失败 ⇒ `&&` 短路 ⇒ 子 shell 非零 ⇒ `if` 不进 ⇒ 冒烟"通过"但根本没跑（ocr2-009）。
# 子 shell 里先 `cd || exit 2`（cd 失败即 2，与"产物退出 0"区分），外层按码判定；清场用绝对路径。
_smoke_rc=0
( cd "$SMOKEY" || exit 2; "$PY" "$PYZ_ABS" check >/dev/null 2>&1 ) || _smoke_rc=$?
rm -rf "$SMOKEY"
SMOKEY=""
if [ "$_smoke_rc" -eq 0 ]; then
  echo "[build-pyz] 冒烟失败：空目录 check 退出 0——main() 返回码被吞，下游闸会常绿" >&2
  exit 1
elif [ "$_smoke_rc" -eq 2 ]; then
  echo "[build-pyz] 冒烟失败：进不去临时目录（没跑到产物）" >&2
  exit 1
fi
mv "$TMP" dist/k3dge.pyz
echo "built dist/k3dge.pyz ($(wc -c < dist/k3dge.pyz) bytes)"
