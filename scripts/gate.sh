#!/usr/bin/env bash
set -euo pipefail

# Locate the repo root relative to this script (works from any cwd).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Forward all args to k3dge; default to 'check' when none given.
if [ $# -eq 0 ]; then
  set -- check
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
