#!/usr/bin/env bash
# k3dge pre-commit sentinel — the only hard local backstop against raw `git commit`.
# `k3dge commit` sets K3DGE_COMMIT_ACTIVE=1 before invoking git; any commit that
# reaches this hook without it (e.g. a bare `git commit`) is refused.
# The real gate logic lives in `k3dge commit` / CI; this is intentionally one line.
if [ "${K3DGE_COMMIT_ACTIVE}" != "1" ]; then
  echo "Forbidden: Use 'k3dge commit' instead of raw git commit (k3dge spec-gate)." >&2
  exit 1
fi
