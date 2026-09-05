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
_SRC_FILE="$ROOT/.venv/k3dge-source.txt"
if [ -n "${K3DGE_SOURCE:-}" ] && [ -f "$_SRC_FILE" ]; then
  _REC="$(sed -n 's/^RESOLVED=//p' "$_SRC_FILE" | head -1 | cut -d' ' -f1)"
  _WANT="$K3DGE_SOURCE"
  [ -d "$_WANT" ] && _WANT="$(cd "$_WANT" && pwd)"
  [ -d "$_REC" ] && _REC="$(cd "$_REC" && pwd)"
  if [ "$_WANT" != "$_REC" ]; then
    echo "[k3dge-source] MISMATCH: K3DGE_SOURCE='$_WANT' but this venv was installed from '$_REC'." >&2
    echo "  用 K3DGE_SOURCE 重装一次（或 unset 回 legacy），再跑闸。" >&2
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
