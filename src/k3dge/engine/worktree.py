"""审计线（k3dge 进程件，施工账⑦）：一单一条线——真实分支＋可编辑签出＋present 自动供给。

审计线模型（ADR-0026 重设计）：分支 `k3dit/<job>` 从锁点 L 拉起、住**消费仓 .git**，
worktree `.k3dge/wt/<job>` 即送检现场（对象格式/树布局同主干，merge 即普通 git）。
Hall 凭 wt 目录拷窗、收回改动经 advance 提版；判读窗永不操作消费仓 .git。
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
    """把 .k3dge/（对象库/worktree）写进仓库本地 exclude——派生物不得污染被审仓的 status。"""
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

    路径：ff 直达；否则把线 (base..br] `rebase --onto` 重演到主干头（线提交全是机械件，
    重演即普通 git）再 ff；冲突 ⇒ abort 复原＋升级人工。真 merge 不再使用（审计线模型）。

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
    main_head = _git(workspace, "rev-parse", "HEAD").stdout.strip()
    base = _git(workspace, "merge-base", "HEAD", br).stdout.strip()
    tip = _git(workspace, "rev-parse", br).stdout.strip()
    if base == tip:
        # 线上无自有提交（L 本身）：无物可搬，主干先走一步也无妨
        return {"ok": True, "mode": "already"}
    wt = ensure(workspace, job)
    _git(wt, "rebase", "--abort")  # 幂等清场：上次崩溃残留的重演态先复原（无则空操作）
    rb = _git(wt, "-c", "user.name=k3dge-process", "-c", "user.email=noreply@k3dge.local",
              "rebase", "--onto", main_head, base)
    if rb.returncode != 0:
        _git(wt, "rebase", "--abort")  # 复原现场（进程件；线原位保留供人工）
        return {"ok": False, "mode": "conflict",
                "message": f"rebase 冲突（{(rb.stderr or rb.stdout).strip()[:120]}）→ 人工处理后重试（§1.4）"}
    if _git(workspace, "merge", "--ff-only", br).returncode == 0:
        return {"ok": True, "mode": "rebase"}
    return {"ok": False, "mode": "error", "message": "重演后仍无法 ff（异常态，交人工）"}


def prune(workspace: Path, job: str) -> dict:
    """⑤ 收口：删现场；审计线**仅在已并入主干时**删（闸过删线，ADR-0026 重设计）。

    未并入（在办/冲突未人工闭环）⇒ 线保留原位，崩溃恢复与幂等重试都靠它。
    """
    removed = []
    try:
        remove(workspace, job)
        removed.append(f"wt:{job}")
    except Exception:
        pass
    br = branch_name(job)
    if _git(workspace, "rev-parse", "--verify", "-q", f"refs/heads/{br}").returncode == 0 \
            and _git(workspace, "merge-base", "--is-ancestor", br, "HEAD").returncode == 0:
        d = _git(workspace, "branch", "-D", br)
        if d.returncode == 0:
            removed.append(f"branch:{br}")
    return {"removed": removed}


def remove(workspace: Path, job: str) -> None:
    _git(workspace, "worktree", "remove", "--force", str(worktree_path(workspace, job)))


def materialize(workspace: Path, rev: str, dest: Path) -> Path:
    """只读物化：把 rev 的树解到 dest（内容物，无 `.git`；不碰线/worktree/分支）。

    供 Hall 按基线 oid 取旧版——此前只能自己对消费仓 `.git` 下手。
    未知 rev ⇒ RuntimeError（不静默给错版）。
    """
    import io
    import tarfile

    if _git(workspace, "rev-parse", "--verify", "-q", f"{rev}^{{commit}}").returncode != 0:
        raise RuntimeError(f"未知版本（无法物化）: {rev!r}")
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    p = subprocess.run(["git", "archive", "--format=tar", rev], cwd=str(workspace),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError(f"物化失败: {p.stderr.decode('utf-8', 'replace').strip()[:160]}")
    with tarfile.open(fileobj=io.BytesIO(p.stdout)) as tf:
        tf.extractall(dest, filter="data")
    return dest
