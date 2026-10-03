#!/usr/bin/env bash
set -euo pipefail

# Initialize the CURRENT WORKING DIRECTORY as a k3dge-governed project.
# Invoked as:
#   ./k3dge-init.sh                          # inside a k3dge checkout (self)
#   /path/to/k3dge/k3dge-init.sh             # cwd is the new project
#   K3DGE_SOURCE=/path/to/k3dge ./k3dge-init.sh
#
# TARGET is always pwd. Harness directories come from scaffold — do not mkdir by hand.

TARGET="$(pwd)"
# 物理路径（`pwd -P`）：逻辑 `pwd` 经包装软链调用时会把 SCRIPT_ROOT 算到链接所在目录，
# `[ -d $SCRIPT_ROOT/src/k3dge ]` 误判 ⇒ 在 checkout 内却报 K3DGE_SOURCE 缺失（ocr2-573）。
SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"

if [ -n "${K3DGE_SOURCE:-}" ]; then
  K3DGE_HOME="$K3DGE_SOURCE"
elif [ -d "$SCRIPT_ROOT/src/k3dge" ]; then
  K3DGE_HOME="$SCRIPT_ROOT"
else
  echo "K3DGE_SOURCE is required (this directory is not a k3dge checkout)." >&2
  echo "  K3DGE_SOURCE=/path/to/k3dge ./k3dge-init.sh" >&2
  echo "  or:  cd <project> && /path/to/k3dge/k3dge-init.sh" >&2
  exit 1
fi

cd "$TARGET"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 (>=3.10) is required" >&2
  exit 1
fi
# 只验存在不验版本 ⇒ 3.9 会先建 venv/git 再在 install 阶段以难懂的形态失败（ocr-170）。
if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
  echo "python3 >= 3.10 is required (found: $(python3 -V 2>&1))" >&2
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "git is required" >&2
  exit 1
fi
# `.git` 在 worktree/submodule 下是**文件**：只判目录会对已在库内的目录重复 `git init`（ocr-171）。
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "[k3dge] git init -b main  ($TARGET)"
  git init -b main
else
  # 只在"本目录是仓根"时才算已受管：TARGET 是别的仓的子目录时，旧判据会跳过 init，
  # 让 hooks 装进祖先仓（改到无关仓）——比嵌套更糟（ocr2-369）。取 toplevel 与物理 cwd 比。
  _TOP="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  _PWD="$(cd "$TARGET" && pwd -P)"
  if [ -n "$_TOP" ] && [ "$_TOP" != "$_PWD" ]; then
    echo "[k3dge] TARGET 不是 git 仓根（toplevel='$_TOP'）⇒ 拒跑：请 cd 到仓根，或换一个不在别的仓内的空目录" >&2
    exit 1
  fi
fi

if [ ! -x .venv/bin/python ]; then
  echo "[k3dge] python3 -m venv .venv"
  python3 -m venv .venv
fi
# 已存在的 venv 也要验解释器版本：3.9/uv/降级遗留的 .venv 会溜过，随后 install/sync
# 以 SyntaxError/tomllib 形态失败（ocr2-370）。与建 venv 前对 python3 的判据同口径。
if ! .venv/bin/python -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
  echo "[k3dge] .venv/bin/python 不可用或 < 3.10；请删除 .venv 后在 Python >= 3.10 下重跑 init" >&2
  exit 1
fi
# 只看 .venv/bin/python 可执行不够：坏 pip / 无 pip / 过期 shebang 会在下一步才炸（ocr-172）。
if ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
  echo "[k3dge] venv 内无可用 pip ⇒ ensurepip"
  # stdout 静默、stderr 留作报错证据：全吞会把缺 python3-venv/只读 .venv 等真实原因一起吞掉（ocr2-690）。
  _ensurepip_err="$(.venv/bin/python -m ensurepip --upgrade 2>&1 >/dev/null)" || {
    echo "[k3dge] FAIL: .venv 里没有可用的 pip（删 .venv 重建，或修 python 安装）" >&2
    [ -n "$_ensurepip_err" ] && printf '%s\n' "$_ensurepip_err" >&2
    exit 1
  }
fi

if [ "$K3DGE_HOME" -ef "$TARGET" ]; then
  echo "[k3dge] pip install -e '.[dev]' (self)"
  .venv/bin/python -m pip install -q -e ".[dev]"
  # 自举分支也必须落盘收据：否则一旦声明政策（env 或 pyproject），三轨读不到收据就永久
  # exit 2，重跑 init 也修不回（ocr2-371）。存**物理路径**，与目录型源同口径。
  printf '%s\n' "$(cd "$TARGET" && pwd -P)" > .venv/k3dge-source.txt
else
  INSTALL_FLAGS=()
  if [ -z "${K3DGE_SOURCE:-}" ] || [ "${K3DGE_SOURCE:-}" = "pypi" ]; then
    INSTALL_TARGET="k3dge[mcp]"
  elif [ -d "${K3DGE_SOURCE:-}" ]; then
    # 目录型源先取**物理路径**再交给 pip：尾斜杠/相对/软链会拼出 `/path/[mcp]`（该路径不存在）
    # 或依赖 cwd，安装命令与实际来源分叉（ocr2-164）。
    INSTALL_TARGET="$(cd "$K3DGE_SOURCE" && pwd -P)[mcp]"
    INSTALL_FLAGS=("-e")
  # 子串匹配 `https://*github.com*` 会放行 `https://github.com.evil.tld/`，`https://*/*` 放行任意主机（ocr2-022）。
  # 与 init.ps1 同口径：只认 `git+` 前缀、三家已知托管商路径前缀、`.git` 后缀。
  elif case "$K3DGE_SOURCE" in git+*|https://github.com/*|https://gitlab.com/*|https://bitbucket.org/*|*.git) true ;; *) false ;; esac; then
    INSTALL_TARGET="k3dge[mcp] @ ${K3DGE_SOURCE}"
  else
    INSTALL_TARGET="${K3DGE_SOURCE}[mcp]"
  fi
  # Fallback: downstream via /path/to/k3dge/k3dge-init.sh without K3DGE_SOURCE
  if [ -z "${K3DGE_SOURCE:-}" ] && [ -n "${K3DGE_HOME:-}" ] && [ -d "$K3DGE_HOME/src/k3dge" ]; then
    INSTALL_TARGET="$(cd "$K3DGE_HOME" && pwd -P)[mcp]"
    INSTALL_FLAGS=("-e")
  fi
  # 分类后**只印一次**：旧实现各分支先印，再被 catch-all 无条件印成"editable"⇒ 同一次安装
  # 出矛盾诊断（481/ocr2-374）。按 INSTALL_FLAGS 判 editable，别硬编码。
  case "$INSTALL_TARGET" in
    *" @ "*) echo "[k3dge] Installing from VCS source (non-editable): ${K3DGE_SOURCE}" ;;
    "k3dge[mcp]") echo "[k3dge] Installing from package index (PyPI)..." ;;
    *)
      if [ "${INSTALL_FLAGS[*]:-}" = "-e" ]; then
        # `%\[mcp\]` 是转义后的 glob；旧 `${INSTALL_TARGET%[mcp]}` 把 `[mcp]` 当 m/c/p 字符集，什么都没剥掉（ocr2-374）。
        echo "[k3dge] Installing editable from local path: ${INSTALL_TARGET%\[mcp\]}"
      else
        echo "[k3dge] Installing from source/package: ${INSTALL_TARGET%\[mcp\]}"
      fi
      ;;
  esac
  case "$INSTALL_TARGET" in
    -*) echo "[k3dge] 非法 INSTALL_TARGET（不得以 - 开头，防 pip 选项注入）：$INSTALL_TARGET" >&2; exit 1 ;;
  esac
  # INSTALL_TARGET 来自 K3DGE_SOURCE（外部输入），已在上面的 `-*` 分支拒绝选项注入；这里**不再**插 `--`：
  # pip 的 optparse 会把 `-e` 后的 `--` 当成取值（`--editable=--`）⇒ "Invalid requirement: '--'"（ocr2-165）。
  .venv/bin/python -m pip install -q ${INSTALL_FLAGS[@]+"${INSTALL_FLAGS[@]}"} "$INSTALL_TARGET" pre-commit pytest
  # 统管落盘：唯一值 = 解析后的源。运行时只读它。
  case "$INSTALL_TARGET" in
    "k3dge[mcp]") _SRC_RECORDED="pypi" ;;
    "k3dge[mcp] @ "*) _SRC_RECORDED="${INSTALL_TARGET#k3dge\[mcp\] @ }" ;;
    *) _SRC_RECORDED="${INSTALL_TARGET%\[mcp\]}" ;;
  esac
  # 目录型源 ⇒ 落**物理路径**：写相对/尾斜杠/软链，会让 gate 侧在不同 cwd 下得出不同结论（ocr-174）。
  if [ -d "$_SRC_RECORDED" ]; then
    _SRC_RECORDED="$(cd "$_SRC_RECORDED" && pwd -P)"
  fi
  printf '%s\n' "$_SRC_RECORDED" > .venv/k3dge-source.txt
fi

echo "[k3dge] generating harness scaffolding in $TARGET ..."
.venv/bin/python -m k3dge.templates.scaffold "$TARGET"

echo "[k3dge] k3dge sync"
.venv/bin/k3dge sync

echo "[k3dge] pre-commit install"
.venv/bin/pre-commit install
.venv/bin/pre-commit install --hook-type commit-msg

echo ""
echo "[k3dge] Initialization complete for $TARGET"
echo "        Run 'k3dge check' anytime to verify consistency."
