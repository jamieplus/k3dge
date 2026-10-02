"""Git change detection against the branch merge-base."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import List

BASE_CANDIDATES = ("origin/main", "origin/master", "main", "master")


class GitError(RuntimeError):
    pass


def _try_run(cmd: List[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run git and hand back the result; a missing/unusable executable becomes GitError.

    `subprocess.run` raises FileNotFoundError (an OSError) when the `git` binary is not
    on PATH — callers upstream (`ConsistencyEngine.evaluate`) only catch GitError, so an
    unconverted OSError crashed `k3dge check` instead of reporting GIT_UNAVAILABLE.
    """
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    except OSError as exc:
        raise GitError(f"{' '.join(cmd[:2])} could not be executed: {exc}") from exc


def _run(cmd: List[str], cwd: Path) -> str:
    result = _try_run(cmd, cwd)
    if result.returncode != 0:
        # cmd[0] 已是 "git"：再拼前缀就输出 `git git status ... failed`（412）
        raise GitError(f"{' '.join(cmd)} failed: {result.stderr.strip()}")
    return result.stdout


def _is_shallow(workspace: Path) -> bool:
    result = _try_run(
        ["git", "rev-parse", "--is-shallow-repository"], cwd=workspace
    )
    if result.returncode != 0:
        # git < 2.15 不认这个 flag / 非仓库 ⇒ 旧实现拿空 stdout 返回 False，浅克隆守卫整条被跳过，
        # 与 HEAD 回退叠加成静默漏检（ocr-227）。判不出来就报错。
        raise GitError(
            "无法判定是否浅克隆（git rev-parse --is-shallow-repository rc="
            f"{result.returncode}）：" + (result.stderr or "").strip()[:200]
        )
    return result.stdout.strip() == "true"


def resolve_base(workspace: Path) -> str:
    """Return the base ref for branch-level diffing, falling back to HEAD."""
    for base in BASE_CANDIDATES:
        probe = _try_run(
            ["git", "merge-base", base, "HEAD"], workspace
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
        status_code = line[:2]
        raw = line[3:]
        if ("R" in status_code or "C" in status_code) and " -> " in raw:
            # take the destination of a rename/copy only when status is rename/copy
            raw = raw.rpartition(" -> ")[2]   # 源路径本身可含 " -> "：从右切才拿到目标（左切截成源尾，ocr-228）
        path = _strip_quotes(raw.strip())
        if path:
            files.append(path)
    return files


def _parse_porcelain_z(status: str) -> List[str]:
    """`git status --porcelain -z` 的解析（NUL 分隔、不 quote）⇒ 非 ASCII 路径不丢（ocr-061）。"""
    toks = status.split("\0")
    files: List[str] = []
    i = 0
    while i < len(toks):
        e = toks[i]
        i += 1
        if not e:
            continue
        xy, path = e[:2], e[3:]
        if "R" in xy or "C" in xy:
            if i < len(toks):      # rename/copy：下一 token 是原路径，跳过，取新路径
                i += 1
        if path.strip():
            files.append(path.strip())
    return files


def get_changed_files(workspace: Path) -> List[str]:
    """Return all files changed relative to merge-base, including uncommitted work."""
    files: List[str] = []
    seen = set()

    # `-z` + `core.quotePath=false`：非 ASCII 文件名不再被引号/八进制转义 ⇒ 中文路径不静默漏检（ocr-061）。
    status = _run(
        ["git", "-c", "core.quotePath=false", "status", "--porcelain", "-z", "--untracked-files=all"],
        workspace,
    )
    for path in _parse_porcelain_z(status):
        if path not in seen:
            seen.add(path)
            files.append(path)

    base = os.environ.get("K3DGE_BASE_SHA", "").strip()
    if not base:
        base = resolve_base(workspace)
    elif base.startswith("-") or any(c.isspace() for c in base):
        # K3DGE_BASE_SHA 来自 CI 环境：`-` 开头会被 git 当选项、含空白会裂参；非法 rev 又只报成
        # GIT_UNAVAILABLE（配置错误伪装成环境故障，ocr-229）。显式拒。
        raise GitError(f"K3DGE_BASE_SHA 非法（不得以 - 开头或含空白）：{base!r}")
    if base != "HEAD":
        committed = _run(
            ["git", "-c", "core.quotePath=false", "diff", "--name-only", "-z", f"{base}...HEAD"],
            workspace,
        ).split("\0")
        for path in committed:
            path = path.strip()
            if path and path not in seen:
                seen.add(path)
                files.append(path)
    else:
        # 基线不明（`resolve_base` 回退 HEAD）时**不许**跳过已提交 diff：`HEAD..HEAD` 是空集，
        # 门禁绿灯但一行没查（ocr2-053）。fail-closed：查全量跟踪文件（`git ls-files`），
        # 不多不少——漏检比慢检糟。
        tracked = _run(
            ["git", "-c", "core.quotePath=false", "ls-files", "-z"],
            workspace,
        ).split("\0")
        for path in tracked:
            path = path.strip()
            if path and path not in seen:
                seen.add(path)
                files.append(path)

    return files
