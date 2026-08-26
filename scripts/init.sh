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
SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

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

if [ ! -d .git ]; then
  echo "[k3dge] git init -b main  ($TARGET)"
  git init -b main
fi

if [ ! -x .venv/bin/python ]; then
  echo "[k3dge] python3 -m venv .venv"
  python3 -m venv .venv
fi

if [ "$K3DGE_HOME" -ef "$TARGET" ]; then
  echo "[k3dge] pip install -e '.[dev]' (self)"
  .venv/bin/pip install -q -e ".[dev]"
else
  INSTALL_FLAGS=""
  if [ -z "${K3DGE_SOURCE:-}" ] || [ "${K3DGE_SOURCE:-}" = "pypi" ]; then
    INSTALL_TARGET="k3dge[mcp]"
    echo "[k3dge] Installing from package index (PyPI)..."
  elif [ -d "${K3DGE_SOURCE:-}" ]; then
    INSTALL_TARGET="${K3DGE_SOURCE}[mcp]"
    INSTALL_FLAGS="-e"
    echo "[k3dge] Installing editable from local path: $K3DGE_SOURCE"
  else
    INSTALL_TARGET="${K3DGE_SOURCE}[mcp]"
    echo "[k3dge] Installing from source/package: $K3DGE_SOURCE"
  fi
  # Fallback: downstream via /path/to/k3dge/k3dge-init.sh without K3DGE_SOURCE
  if [ -z "${K3DGE_SOURCE:-}" ] && [ -n "${K3DGE_HOME:-}" ] && [ -d "$K3DGE_HOME/src/k3dge" ]; then
    INSTALL_TARGET="${K3DGE_HOME}[mcp]"
    INSTALL_FLAGS="-e"
    echo "[k3dge] Installing editable from K3DGE_HOME: $K3DGE_HOME"
  fi
  .venv/bin/pip install -q ${INSTALL_FLAGS} "$INSTALL_TARGET" pre-commit pytest
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
