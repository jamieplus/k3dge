"""Git change detection against the branch merge-base."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List

BASE_CANDIDATES = ("origin/main", "origin/master", "main", "master")


class GitError(RuntimeError):
    pass


def _run(cmd: List[str], cwd: Path) -> str:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise GitError(f"git {' '.join(cmd)} failed: {result.stderr.strip()}")
    return result.stdout


def _is_shallow(workspace: Path) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--is-shallow-repository"], cwd=workspace, capture_output=True, text=True
    )
    return result.stdout.strip() == "true"


def resolve_base(workspace: Path) -> str:
    """Return the base ref for branch-level diffing, falling back to HEAD."""
    for base in BASE_CANDIDATES:
        probe = subprocess.run(
            ["git", "merge-base", base, "HEAD"], cwd=workspace, capture_output=True, text=True
        )
        if probe.returncode == 0 and probe.stdout.strip():
            return base
    if _is_shallow(workspace):
        raise GitError(
            "shallow clone detected and no base branch reachable; "
            "fetch with --unshallow or set fetch-depth: 0, or export K3DGE_BASE_SHA"
        )
    return "HEAD"


def _strip_quotes(path: str) -> str:
    path = path.strip()
    if len(path) >= 2 and path[0] == '"' and path[-1] == '"':
        # git quotepath: remove surrounding quotes and unescape
        inner = path[1:-1]
        # minimal unescape for common cases; full decoding not needed for gate
        return inner.replace('\\"', '"').replace("\\\\", "\\")
    return path


def _parse_porcelain(status: str) -> List[str]:
    files: List[str] = []
    for line in status.splitlines():
        if not line.strip():
            continue
        # porcelain v1: XY<space>path, or XY<space>orig -> new for renames
        # handle quoted paths produced by core.quotepath
        raw = line[3:]
        if " -> " in raw:
            # take the destination of a rename/copy
            raw = raw.split(" -> ", 1)[1]
        path = _strip_quotes(raw.strip())
        if path:
            files.append(path)
    return files


def get_changed_files(workspace: Path) -> List[str]:
    """Return all files changed relative to merge-base, including uncommitted work."""
    files: List[str] = []
    seen = set()

    status = _run(
        ["git", "status", "--porcelain", "--untracked-files=all"], workspace
    )
    for path in _parse_porcelain(status):
        if path not in seen:
            seen.add(path)
            files.append(path)

    base_env = __import__("os").environ.get("K3DGE_BASE_SHA", "").strip()
    if base_env:
        committed = _run(["git", "diff", "--name-only", f"{base_env}...HEAD"], workspace).splitlines()
        for path in committed:
            path = _strip_quotes(path.strip())
            if path and path not in seen:
                seen.add(path)
                files.append(path)
        return files

    base = resolve_base(workspace)
    if base != "HEAD":
        committed = _run(["git", "diff", "--name-only", f"{base}...HEAD"], workspace).splitlines()
        for path in committed:
            path = _strip_quotes(path.strip())
            if path and path not in seen:
                seen.add(path)
                files.append(path)

    return files
