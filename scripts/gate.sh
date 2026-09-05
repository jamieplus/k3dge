#!/usr/bin/env bash
set -euo pipefail

# Locate the repo root relative to this script (works from any cwd).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Forward all args to k3dge; default to 'check' when none given.
if [ $# -eq 0 ]; then
  set -- check
fi

# K3DGE_SOURCE 统管校验：环境声明的源 vs 本 venv 的装时落盘，不一致即拦。
# （装时真相 vs 现行政策，打架必须出声——重装或 unset 再走。）
# 政策读取：K3DGE_SOURCE 环境（显式覆盖，最高）> 本仓 pyproject [tool.k3dge].source（入库政策）；
# 都没有 = legacy（落盘收据即真相，老 venv）。
_WANT="${K3DGE_SOURCE:-}"
if [ -z "$_WANT" ] && [ -f "$ROOT/pyproject.toml" ]; then
  _WANT="$(python3 -c 'import tomllib;print(tomllib.load(open("pyproject.toml","rb")).get("tool",{}).get("k3dge",{}).get("source",""))' 2>/dev/null || true)"
  if [ -z "$_WANT" ]; then
    _WANT="$(sed -n '/^\[tool\.k3dge\]$/,/^\[/p' pyproject.toml 2>/dev/null | sed -n 's/^source *= *"\(.*\)".*/\1/p' | head -1)"
  fi
fi
_SRC_FILE="$ROOT/.venv/k3dge-source.txt"
if [ -n "$_WANT" ] && [ -f "$_SRC_FILE" ]; then
  _REC="$(head -1 "$_SRC_FILE" | tr -d ' \t\r\n')"
  [ -d "$_WANT" ] && _WANT="$(cd "$_WANT" && pwd)"
  [ -d "$_REC" ] && _REC="$(cd "$_REC" && pwd)"
  if [ "$_WANT" != "$_REC" ]; then
    echo "[k3dge-source] MISMATCH: want='$_WANT'（env>pyproject） but installed from '$_REC'." >&2
    echo "  重装或改政策后再跑闸。" >&2
    exit 2
  fi
fi

# Prefer the project-local venv so no manual activation is required.
if [ -x "$ROOT/.venv/bin/k3dge" ]; then
  exec "$ROOT/.venv/bin/k3dge" "$@"
fi

# Fall back to a globally installed k3dge (pipx / pip).
if command -v k3dge >/dev/null 2>&1; then
  exec k3dge "$@"
fi

echo "k3dge not found. Run the one-time init first:" >&2
echo "  ./k3dge-init.sh" >&2
echo "See README.md for details." >&2
exit 1
