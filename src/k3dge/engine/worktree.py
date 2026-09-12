"""审计线（k3dge 进程件，施工账⑦）：一单一条线——真实分支＋可编辑签出＋present 自动供给。

审计线模型（ADR-0024 重设计）：分支 `k3dit/<job>` 从锁点 L 拉起、住**消费仓 .git**，
worktree `.k3dge/wt/<job>` 即送检现场（对象格式/树布局同主干，merge 即普通 git）。
Hall 凭 wt 目录拷窗、收回改动经 advance 提版；判读窗永不操作消费仓 .git。
present 由进程从 worktree 抽取（markers.extract），席位口供退居交叉核对（§ADR-0024 §2.4）。
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
    """worktree 同步到给定 commit（缺=分支头）后，进程抽取 markers 作 present。
    只读比对不动分支：detach 看完即切回（detached 残留会毒化后续 rebase——分支 ref 原地踏步）。"""
    wt = ensure(workspace, job)
    br = branch_name(job)
    if commit:
        r = _git(wt, "checkout", "-q", "--detach", commit)
        if r.returncode != 0:
            _git(wt, "checkout", "-q", br)
            raise RuntimeError(f"present checkout {commit[:12]} 失败")
    try:
        ms, _problems = extract(wt)
        return [
            {"file": m.file, "line": m.line, "kind": m.kind, "id": m.id, "scope": m.scope, "note": m.note}
            for m in ms
        ]
    finally:
        if commit:
            _git(wt, "checkout", "-q", br)  # 复位：后人（advance/rebase）都在分支上干活


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


def strip_pins(workspace: Path, job: str) -> dict:
    """收官去钉：删审计线 worktree 里独占一行的钉；行尾钉不动（只上报）。
    **除 leftover 外**的钉永不进主干（§3③）——leftover 作有意留的长期文献随文件留下，故不删。
    扫描面是全树（present 的 roots 限定之外也得兜住）。返回 {stripped_files, stripped_lines, suspicious, kept}。"""
    from k3dge.engine.markers import _SCAN_SUFFIXES, _SKIP_DIR_PARTS, parse_text

    wt = ensure(workspace, job)
    files: list = []
    lines = 0
    kept = 0
    suspicious: list = []
    for p in sorted(wt.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in _SCAN_SUFFIXES:
            continue
        rel = p.relative_to(wt).as_posix()
        if set(p.relative_to(wt).parts) & set(_SKIP_DIR_PARTS):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        ms, _ = parse_text(rel, text)
        if not ms:
            continue
        src = text.splitlines()
        drop = set()
        for m in ms:
            if m.kind == "leftover":        # 长期文献，随文件上主干，不删
                kept += 1
                continue
            if src[m.line - 1].lstrip().startswith(("#", "//", "<!--")):
                drop.add(m.line)
            else:
                suspicious.append(f"{rel}:{m.line}")
        if drop:
            out = [ln for i, ln in enumerate(src, 1) if i not in drop]
            try:
                p.write_text("\n".join(out) + "\n", encoding="utf-8")
            except OSError:
                continue
            files.append(rel)
            lines += len(drop)
    return {"stripped_files": files, "stripped_lines": lines, "suspicious": suspicious, "kept": kept}


def _run_landing_gate(workspace: Path) -> dict:
    """消费侧落点机械闸（ADR-0025 Note ㉖）：主干工作树上跑 check + doc-gate + pytest。

    红 ⇒ 调用方回滚主干、挡下合并（先验后并，主干不被坏改动污染）。复用 `scripts/`（与
    pre-commit 同源）+ `pytest`（与 CI 同源）；缺哪件跳哪件（夹具/非标仓不误伤），全缺=skipped。
    """
    import sys

    steps: list = []
    gate = workspace / "scripts" / "gate.py"
    doc = workspace / "scripts" / "pre-commit"
    if gate.is_file():
        steps.append(("check", [sys.executable, str(gate), "check"]))
    if doc.is_file():
        steps.append(("doc-gate", [sys.executable, str(doc), "--scan"]))
    if (workspace / "tests").is_dir():
        steps.append(("tests", [sys.executable, "-m", "pytest", "-q"]))
    if not steps:
        return {"ok": True, "skipped": True}
    for name, cmd in steps:
        try:
            r = subprocess.run(cmd, cwd=str(workspace), capture_output=True, text=True)
        except OSError as exc:
            return {"ok": False, "step": name, "message": f"执行失败：{exc}"}
        if r.returncode != 0:
            tail = [ln for ln in (r.stdout + "\n" + r.stderr).strip().splitlines() if ln.strip()][-8:]
            return {"ok": False, "step": name, "message": "；".join(tail)[-300:]}
    return {"ok": True}


def merge_back(workspace: Path, job: str, accept_dirty: tuple = ()) -> dict:
    """closure 回写主干（P1：默认自动；脏树/冲突/落点闸红 ⇒ 停并升级人工，§1.4）。

    路径：先去钉（钉永不进主干，去钉产物提版）→ ff 直达；ff 不成则把线
    (base..br] `rebase --onto` 重演到主干头（线提交全是机械件，重演即普通 git）
    再 ff；冲突 ⇒ abort 复原＋升级人工。真 merge 不再使用（审计线模型）。

    **落点机械闸**：ff 主干的**同一瞬间**跑 `run_landing_gate`；红则 `reset --hard`
    回滚主干（先验后并）——审计成果仍在线上，交人工/重审。
    accept_dirty：编排进程自己写的件（工单 task/报告落盘/state 文件）——
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
    strip = strip_pins(workspace, job)
    try:
        advance(workspace, job)  # 去钉产物提版；干净即 no-op
    except RuntimeError as exc:
        return {"ok": False, "mode": "error", "message": f"去钉提版失败：{exc}"}
    pre = _git(workspace, "rev-parse", "HEAD").stdout.strip()
    if _git(workspace, "merge", "--ff-only", br).returncode == 0:
        gate = _run_landing_gate(workspace)
        if not gate.get("ok"):
            _git(workspace, "reset", "--hard", pre)
            return {"ok": False, "mode": "gate",
                    "message": f"落点机械闸红（{gate.get('step')}）：{gate.get('message', '')[:200]}"}
        return {"ok": True, "mode": "ff", "stripped": strip}
    main_head = _git(workspace, "rev-parse", "HEAD").stdout.strip()
    base = _git(workspace, "merge-base", "HEAD", br).stdout.strip()
    tip = _git(workspace, "rev-parse", br).stdout.strip()
    if base == tip:
        # 线上无自有提交（L 本身）：无物可搬，主干先走一步也无妨
        return {"ok": True, "mode": "already"}
    wt = ensure(workspace, job)
    _git(wt, "rebase", "--abort")  # 幂等清场：上次崩溃残留的重演态先复原（无则空操作）
    if _git(wt, "checkout", "-q", br).returncode != 0:  # 挂回分支再重演（detached 上 rebase 空转）
        return {"ok": False, "mode": "error", "message": "worktree 挂回分支失败，交人工"}
    rb = _git(wt, "-c", "user.name=k3dge-process", "-c", "user.email=noreply@k3dge.local",
              "rebase", "--onto", main_head, base)
    if rb.returncode != 0:
        _git(wt, "rebase", "--abort")  # 复原现场（进程件；线原位保留供人工）
        return {"ok": False, "mode": "conflict",
                "message": f"rebase 冲突（{(rb.stderr or rb.stdout).strip()[:120]}）→ 人工处理后重试（§1.4）"}
    pre2 = _git(workspace, "rev-parse", "HEAD").stdout.strip()
    if _git(workspace, "merge", "--ff-only", br).returncode == 0:
        gate = _run_landing_gate(workspace)
        if not gate.get("ok"):
            _git(workspace, "reset", "--hard", pre2)
            return {"ok": False, "mode": "gate",
                    "message": f"落点机械闸红（{gate.get('step')}）：{gate.get('message', '')[:200]}"}
        return {"ok": True, "mode": "rebase"}
    return {"ok": False, "mode": "error", "message": "重演后仍无法 ff（异常态，交人工）"}


def prune(workspace: Path, job: str) -> dict:
    """⑤ 收口：删现场；审计线**仅在已并入主干时**删（闸过删线，ADR-0024 重设计）。

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


def pin_baseline(workspace: Path, name: str, oid: str) -> bool:
    """留存被引用的审计基线（报告引用的 commit 经 rebase 后可能悬空，gc 即不可复验）。
    ref 与审计线共存亡之外的另一条命：只增（每单一条），清理由留存策略定，不在收口删。"""
    if not oid or _git(workspace, "cat-file", "-t", oid).stdout.strip() != "commit":
        return False
    return _git(workspace, "update-ref", f"refs/audit-baseline/{name}", oid).returncode == 0


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
