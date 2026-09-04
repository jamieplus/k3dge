"""轮次 worktree（k3dge 进程件，施工账⑦）：真实分支＋可编辑签出＋present 自动供给。

P2 精化（已记）：轮次分支 `k3dit/<job>` 住**消费仓 .git**（分支是消费侧的物）；快照 commit 链住
`.k3dge/store.git` 的 refs/snap/*——两套对象各归各命，主仓历史不被快照污染，案卷侧零内容。
present 由进程从 worktree 抽取（markers.extract），席位口供退居交叉核对（§ADR-0026 §2.4）。
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

from k3dge.engine.markers import Marker, extract, parse_text


def _git(workspace: Path, *args: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(["git", *args], cwd=str(workspace), capture_output=True, text=True, env=env)


def branch_name(job: str) -> str:
    return f"k3dit/{job}"


def worktree_path(workspace: Path, job: str) -> Path:
    return workspace / ".k3dge" / "wt" / job


def _exclude_derived(workspace: Path) -> None:
    """把 .k3dge/（对象库/worktree/bundle）写进仓库本地 exclude——派生物不得污染被审仓的 status。"""
    out = _git(workspace, "rev-parse", "--git-common-dir").stdout.strip()
    common = (workspace / out) if out else (workspace / ".git")
    exc = Path(common) / "info" / "exclude"
    try:
        exc.parent.mkdir(parents=True, exist_ok=True)
        cur = exc.read_text(encoding="utf-8") if exc.is_file() else ""
        if ".k3dge/" not in cur:
            exc.write_text(cur + ("\n" if cur and not cur.endswith("\n") else "") + ".k3dge/\n", encoding="utf-8")
    except OSError:
        pass


def ensure(workspace: Path, job: str, base: Optional[str] = None) -> Path:
    """挂 worktree；分支首建自 base(缺=HEAD)，已存在则复用（幂等）。"""
    _exclude_derived(workspace)
    wt = worktree_path(workspace, job)
    if (wt / ".git").exists():
        return wt
    wt.parent.mkdir(parents=True, exist_ok=True)
    br = branch_name(job)
    r = _git(workspace, "rev-parse", "--verify", "-q", f"refs/heads/{br}")
    if r.returncode != 0:
        start = base or "HEAD"
        m = _git(workspace, "worktree", "add", "-b", br, str(wt), start)
    else:
        m = _git(workspace, "worktree", "add", str(wt), br)
    if m.returncode != 0 and "already registered" in (m.stderr or ""):
        _git(workspace, "worktree", "prune")            # 陈旧登记自愈（目录被外部清过）
        if base or True:
            re = _git(workspace, "worktree", "add", "-f", str(wt), branch_name(job)) \
                if _git(workspace, "rev-parse", "--verify", "-q", f"refs/heads/{branch_name(job)}").returncode == 0 \
                else _git(workspace, "worktree", "add", "-f", "-b", branch_name(job), str(wt), base or "HEAD")
            if re.returncode != 0:
                raise RuntimeError(f"worktree add failed after prune: {(re.stderr or re.stdout).strip()[:200]}")
            return wt
    if m.returncode != 0:
        raise RuntimeError(f"worktree add failed: {(m.stderr or m.stdout).strip()[:200]}")
    return wt


def present(workspace: Path, job: str, commit: Optional[str] = None) -> list:
    """worktree 同步到给定 commit（缺=分支头）后，进程抽取 markers 作 present。"""
    wt = ensure(workspace, job)
    if commit:
        r = _git(wt, "checkout", "-q", "--detach" if commit else commit)
        # 席位提交后，编排侧只读比对：detach 到具体 commit 即可
    ms, _problems = extract(wt)
    return [
        {"file": m.file, "line": m.line, "kind": m.kind, "id": m.id, "scope": m.scope, "note": m.note}
        for m in ms
    ]


def advance(workspace: Path, job: str) -> Optional[str]:
    """轮次前进：worktree 脏 ⇒ 进程代 commit（席位身份由调用方注入 env 或默认进程名）；
    分支前进只接受祖先关系（含 detached 席位 commit 的合法快进）；真分叉 ⇒ 拒，升级人工（§1.4）。"""
    wt = ensure(workspace, job)
    if _git(wt, "status", "--porcelain").stdout.strip():
        _git(wt, "add", "-A")
        c = _git(wt, "-c", "user.name=k3dge-process", "-c", "user.email=noreply@k3dge.local",
                 "commit", "--no-verify", "-m", f"round work {job}")  # 进程机械件不过被审仓 pre-commit（人的闸管人的提交）
        if c.returncode != 0:
            raise RuntimeError(f"round commit failed: {(c.stderr or c.stdout)[:200]}")
    head = _git(wt, "rev-parse", "HEAD").stdout.strip()
    b = _git(workspace, "rev-parse", branch_name(job)).stdout.strip()
    if not head or head == b:
        return b or None
    if _git(workspace, "merge-base", "--is-ancestor", b, head).returncode == 0:
        r = _git(workspace, "update-ref", f"refs/heads/{branch_name(job)}", head, b)  # CAS：旧值必须还是 b
        if r.returncode != 0:
            raise RuntimeError("non-fast-forward: 分支头已在他处移动（CAS 失败），停——交人工裁决（§1.4）")
        return head
    raise RuntimeError("non-fast-forward: worktree 与分支真分叉，停——交人工裁决（§1.4）")


def merge_back(workspace: Path, job: str, accept_dirty: tuple = ()) -> dict:
    """closure 回写主干（P1：默认自动；脏树/冲突 ⇒ 停并升级人工，§1.4）。

    accept_dirty：编排进程自己写的件（工单 task/报告落位/state 文件）——
    守卫防的是"人的未提交工作被卷进去"，不该拦自己刚写的字。
    """
    br = branch_name(job)
    if _git(workspace, "rev-parse", "--verify", "-q", f"refs/heads/{br}").returncode != 0:
        return {"ok": True, "mode": "no-branch"}
    dirty = []
    for line in _git(workspace, "status", "--porcelain").stdout.splitlines():
        path = line[3:].split(" -> ")[-1].strip().strip('"')
        # 双向前缀：porcelain 会把未跟踪目录折成 `docs/`，白名单写的是 `docs/tasks/…`
        if not any(path.startswith(a) or (a and a.startswith(path.rstrip("/"))) for a in accept_dirty):
            dirty.append(path)
    if dirty:
        return {"ok": False, "mode": "dirty",
                "message": f"工作树有未提交的人工改动（{dirty[:3]}）：merge 停，交人工处理（P1 例外）"}
    if _git(workspace, "merge-base", "--is-ancestor", br, "HEAD").returncode == 0:
        return {"ok": True, "mode": "already"}
    if _git(workspace, "merge", "--ff-only", br).returncode == 0:
        return {"ok": True, "mode": "ff"}
    m = _git(workspace, "-c", "user.name=k3dge-process", "-c", "user.email=noreply@k3dge.local",
             "merge", "--no-edit", "-m", f"audit ratchet {job} merged", br)
    if m.returncode != 0:
        if _git(workspace, "merge", "--abort").returncode != 0:   # add/add 等早退场景没有进行中的 merge
            _git(workspace, "reset", "--hard", "HEAD")            # 兜底恢复干净树（进程件，不碰未跟踪文件）
        return {"ok": False, "mode": "conflict", "message": "merge 冲突 → 人工 rebase 后重试（§1.4）"}
    return {"ok": True, "mode": "merge"}


def prune(workspace: Path, job: str, bundle_files: list[str]) -> dict:
    """⑤ end-flow 清理：worktree 与 bundle 袋是派生物；store 与已合并分支史保留。"""
    removed = []
    try:
        remove(workspace, job)
        removed.append(f"wt:{job}")
    except Exception:
        pass
    for bf in bundle_files:
        try:
            (workspace / bf).unlink(missing_ok=True)
            removed.append(bf)
        except OSError:
            pass
    return {"removed": removed}


def remove(workspace: Path, job: str) -> None:
    _git(workspace, "worktree", "remove", "--force", str(worktree_path(workspace, job)))
