#!/usr/bin/env bash
set -euo pipefail

# Locate the repo root relative to this script (works from any cwd).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"

# Forward all args to k3dge; default to 'check' when none given.
if [ $# -eq 0 ]; then
  set -- check
fi

# K3DGE_SOURCE 统管校验：环境声明的源 vs 本 venv 的装时落盘，不一致即拦。
# （装时真相 vs 现行政策，打架必须出声——重装或 unset 再走。）
# 政策读取：K3DGE_SOURCE 环境（显式覆盖，最高）> 本仓 pyproject [tool.k3dge].source（入库政策）；
# 都没有 = legacy（落盘收据即真相，老 venv）。
_WANT="$(printf '%s' "${K3DGE_SOURCE:-}" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
if [ -z "$_WANT" ] && [ -f "$ROOT/pyproject.toml" ]; then
  _WANT="$(python3 -c 'import tomllib;print(tomllib.load(open("pyproject.toml","rb")).get("tool",{}).get("k3dge",{}).get("source",""))' 2>/dev/null || true)"
  if [ -z "$_WANT" ]; then
    # 与 gate.py 同口径：允许 tab、单/双引号、行尾注释（原 `s/^source *= *"\(...\)"*/` 只认双引号 + 无 tab）。
    _WANT="$(sed -n '/^\[tool\.k3dge\]$/,/^\[/p' pyproject.toml 2>/dev/null \
             | sed -n "s/^[[:space:]]*source[[:space:]]*=[[:space:]]*[\"']\([^\"']*\)[\"'][[:space:]]*\(#.*\)\?$/\1/p" | head -1)"
  fi
fi
_SRC_FILE="$ROOT/.venv/k3dge-source.txt"
if [ -n "$_WANT" ]; then
  if [ ! -f "$_SRC_FILE" ]; then
    # 政策存在而收据缺失 ⇒ 无法证明本 venv 来源与政策一致（删收据/手建 venv 都会溜过）——拒跑，不再静默放行。
    echo "[k3dge-source] 政策已声明但 .venv/k3dge-source.txt 缺失：无法证明来源一致 ⇒ 拒跑" >&2
    echo "  重跑 ./k3dge-init.sh 落盘，或 unset K3DGE_SOURCE/改 pyproject 政策。" >&2
    exit 2
  fi
  IFS= read -r _REC < "$_SRC_FILE" || _REC=""       # 不用 `head -1 | tr`（pipefail + SIGPIPE 有静默风险，ocr-154）
  _REC="${_REC#$'\xef\xbb\xbf'}"                    # 去 BOM（旧 init.ps1 写的 BOM 会让比较恒不等）
  _REC="${_REC%$'\r'}"                              # 只去行尾 CR（`tr -d ' \t'` 会吞路径里的空格，ocr-156）
  _REC="$(printf '%s' "$_REC" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
  [ -d "$_WANT" ] && _WANT="$(cd "$_WANT" && pwd -P)"   # 只对真实目录取物理路径；pypi/URL 保持原样
  [ -n "$_REC" ] && [ -d "$_REC" ] && _REC="$(cd "$_REC" && pwd -P)"
  if [ -n "$_REC" ] && [ "$_WANT" != "$_REC" ]; then
    echo "[k3dge-source] MISMATCH: want='$_WANT'（env>pyproject） but installed from '$_REC'." >&2
    echo "  重装或改政策后再跑闸。" >&2
    exit 2
  fi
fi

# Prefer the project-local venv so no manual activation is required.
if [ -x "$ROOT/.venv/bin/k3dge" ]; then
  exec "$ROOT/.venv/bin/k3dge" "$@"
fi

# Fall back to a globally installed k3dge (pipx / pip)：收据只覆盖 `.venv`，全局那份来源不受政策约束
# ⇒ 政策存在时至少出声（别让人以为跑的是刚校验过的那个二进制，ocr-158）。
if command -v k3dge >/dev/null 2>&1; then
  if [ -n "$_WANT" ]; then
    echo "[k3dge-source] WARN: 政策已声明但 .venv/bin/k3dge 缺失 ⇒ 回落全局 k3dge（其来源未经收据校验）：$(command -v k3dge)" >&2
  fi
  exec k3dge "$@"
fi

echo "k3dge not found. Run the one-time init first:" >&2
echo "  ./k3dge-init.sh" >&2
echo "See README.md for details." >&2
exit 1
