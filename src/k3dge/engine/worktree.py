"""审计线（k3dge 进程件，施工账⑦）：一单一条线——真实分支＋可编辑签出＋present 自动供给。

审计线模型（ADR-0025 重设计）：分支 `k3dit/<job>` 从锁点 L 拉起、住**消费仓 .git**，
worktree `.k3dge/wt/<job>` 即送检现场（对象格式/树布局同主干，merge 即普通 git）。
Hall 凭 wt 目录拷窗、收回改动经 advance 提版；判读窗永不操作消费仓 .git。
present 由进程从 worktree 抽取（markers.extract），席位口供退居交叉核对（§ADR-0025 §2.9.4）。
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

from k3dge.engine.markers import extract, parse_text

#: job id 白名单：它进 `.k3dge/wt/<job>` 与分支名 `k3dit/<job>` ⇒ 分隔符/`..`/git 非法 ref 字符都要挡（ocr-119）。
_JOB_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _safe_job(job: str) -> str:
    j = str(job or "")
    if not j or ".." in j or not _JOB_RE.fullmatch(j):
        raise ValueError(f"invalid job id {job!r}（分隔符/`..` 会越出 .k3dge/wt 或造出畸形分支）")
    return j


# `GIT_*` 一律剥（防止调用方的 worktree/index 指针串进来），**除了配置隔离对**：
# 测试/CI 用 `GIT_CONFIG_GLOBAL`/`GIT_CONFIG_NOSYSTEM` 声明"别读宿主 globalconfig"，
# 连它们一起剥会让生产调用成为被测面里唯一没隔离的那一份——断言红绿都可能是宿主
# globalconfig（hooksPath/gpgsign/alias.*/init.defaultBranch）造成的（t-310）。
_CONFIG_ISOLATION_VARS = frozenset({"GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM"})


def _clean_env() -> dict:
    """剥掉调用方继承的 `GIT_*`（保留配置隔离对）——落点闸/物化也须复用同一口径（ocr2-335/341）。"""
    return {k: v for k, v in os.environ.items()
            if not k.startswith("GIT_") or k in _CONFIG_ISOLATION_VARS}


def _git(workspace: Path, *args: str) -> subprocess.CompletedProcess:
    # `stdin=DEVNULL`：`cat-file --batch` 之类的被注入开关不会从继承的交互 stdin 永久阻塞（ocr2-339）。
    return subprocess.run(["git", *args], cwd=str(workspace), capture_output=True, text=True,
                          env=_clean_env(), stdin=subprocess.DEVNULL)


def branch_name(job: str) -> str:
    return f"k3dit/{_safe_job(job)}"


def worktree_path(workspace: Path, job: str) -> Path:
    return workspace / ".k3dge" / "wt" / _safe_job(job)


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
        retry = _git(workspace, "worktree", "add", "-f", str(wt), branch_name(job)) \
            if _git(workspace, "rev-parse", "--verify", "-q", f"refs/heads/{branch_name(job)}").returncode == 0 \
            else _git(workspace, "worktree", "add", "-f", "-b", branch_name(job), str(wt), base or "HEAD")
        if retry.returncode != 0:
            raise RuntimeError(f"worktree add failed after prune: {(retry.stderr or retry.stdout).strip()[:200]}")
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
        ms, problems = extract(wt)
        if problems:
            # present 是权威口供：抽取问题被吞 ⇒ 少报钉却返回成功（ocr2-331）。出声。
            print(f"[worktree] WARN: present 抽取有问题（{len(problems)} 条）⇒ 钉可能少报："
                  f"{problems[:3]}", file=sys.stderr)
        return [
            {"file": m.file, "line": m.line, "kind": m.kind, "id": m.id, "scope": m.scope, "note": m.note}
            for m in ms
        ]
    finally:
        if commit:
            back = _git(wt, "checkout", "-q", br)   # 复位：后人（advance/rebase）都在分支上干活
            if back.returncode != 0:
                # 复位失败仍静默 ⇒ worktree 留在 detached，毒化后续 rebase（模块自己声明的不变量）
                err = RuntimeError(
                    f"present 复位失败（{br}）：worktree 仍处 detached，"
                    f"后续 advance/rebase 不可信：{(back.stderr or back.stdout).strip()[:160]}")
                if sys.exc_info()[0] is None:
                    raise err
                # 已有异常在传播（extract 失败）：不得顶替原始异常，出声后让原异常继续抛。
                print(f"[worktree] WARN: {err}", file=sys.stderr)


def advance(workspace: Path, job: str) -> Optional[str]:
    """轮次前进：worktree 脏 ⇒ 进程代 commit（席位身份固定为进程名：`_clean_env` 剥掉调用方
    `GIT_*`（含 author 变量），env 注入的身份无效；未设时默认进程名）；
    分支前进只接受祖先关系（含 detached 席位 commit 的合法快进）；真分叉 ⇒ 拒，升级人工（§1.4）。"""
    wt = ensure(workspace, job)
    st = _git(wt, "status", "--porcelain")
    if st.returncode != 0:            # status 失败（rc≠0、stdout 空）不得被当"干净树"（ocr2-332）
        raise RuntimeError(f"status failed in worktree {wt}: {(st.stderr or st.stdout).strip()[:160]}")
    if st.stdout.strip():
        add = _git(wt, "add", "-A")
        if add.returncode != 0:       # add 部分失败后 commit 会以已入索引子集成功（ocr2-332）
            raise RuntimeError(f"git add failed in worktree {wt}: {(add.stderr or add.stdout).strip()[:160]}")
        from k3dge.engine.attest import append_to_message

        msg = append_to_message(wt, f"round work {job}", who="k3dge-process")
        c = _git(wt, "-c", "user.name=k3dge-process", "-c", "user.email=noreply@k3dge.local",
                 "commit", "--no-verify", "-m", msg)  # 进程机械件不过被审仓 pre-commit；仍须 attestation，CI 全量验
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
    from k3dge.engine import gates
    from k3dge.engine.markers import _SCAN_SUFFIXES, _SKIP_DIR_PARTS

    _mn = int(gates.get(workspace, "markers", "max_note"))
    _mnp = int(gates.get(workspace, "markers", "max_note_pending"))

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
            # `newline=""`：保留原行尾（CRLF/CR 不被 universal-newlines 折成 LF，ocr2-333）
            # 也不给无结尾换行的文件补换行。
            with open(p, "r", encoding="utf-8", newline="") as fh:
                text = fh.read()
        except (UnicodeDecodeError, OSError):
            continue
        ms, _ = parse_text(rel, text, max_note=_mn, max_note_pending=_mnp)
        if not ms:
            continue
        src = text.splitlines(keepends=True)
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
                with open(p, "w", encoding="utf-8", newline="") as fh:
                    fh.write("".join(out))     # 逐字节保留其余行尾；全删则成空文件而非 "\n"
            except OSError as exc:
                # 写回失败 ⇒ 钉还在盘上，但调用方拿到的是"剥离成功"计数，后续 advance 会把未剥离的
                # pending 钉带进主干（ocr2-088）。进 `suspicious`（人审面），不静默 `continue`。
                suspicious.append(f"{rel}:写回失败({exc})，钉未剥离")
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
        # 先 sync：审计若动过公开符号，spec 接口/契约哈希须先回写（AGENTS：Public signature→sync），
        # 否则 check 必报 CONTRACT_DRIFT。sync 确定性幂等，随后 check 验同一结果。
        steps.append(("sync", [sys.executable, str(gate), "sync"]))
        steps.append(("check", [sys.executable, str(gate), "check"]))
    if doc.is_file():
        steps.append(("doc-gate", [sys.executable, str(doc), "--scan"]))
    if (workspace / "tests").is_dir():
        import importlib.util

        # 环境不具备（解释器没装 pytest）不得报成"落点机械闸红"（ocr2-334）：探测可用性，
        # 不可用则跳过该件（与"缺哪件跳哪件"同口径），不拿 rc≠1 回滚已 ff 的主干。
        if importlib.util.find_spec("pytest") is not None:
            steps.append(("tests", [sys.executable, "-m", "pytest", "-q"]))
    if not steps:
        return {"ok": True, "skipped": True}
    # 落点闸也是被审仓的机械件：复用 `_git` 的环境隔离（GIT_*），并去掉宿主
    # `PYTEST_ADDOPTS`，否则同一份 diff 可因调用方环境假绿/假红（ocr2-335）。
    gate_env = _clean_env()
    gate_env.pop("PYTEST_ADDOPTS", None)
    for name, cmd in steps:
        try:
            r = subprocess.run(cmd, cwd=str(workspace), capture_output=True, text=True,
                               env=gate_env)
        except OSError as exc:
            return {"ok": False, "step": name, "message": f"执行失败：{exc}"}
        if r.returncode != 0:
            tail = [ln for ln in (r.stdout + "\n" + r.stderr).strip().splitlines() if ln.strip()][-8:]
            return {"ok": False, "step": name, "message": "；".join(tail)[-300:]}
    return {"ok": True}


def _ff_with_gate(workspace: Path, br: str, pre: str, mode: str) -> Optional[dict]:
    """ff 主干 → 落点机械闸 → 闸红 `reset --hard` 回滚到 `pre`（单一回滚路径）。

    返回 `None` 表示 ff 不成（调用方决定下一步走 rebase 还是报错）；否则返回合并结论。
    先 ff / rebase 后 ff 两段共用本函数，回滚口径只有一处可漂（value-12）。
    """
    if _git(workspace, "merge", "--ff-only", br).returncode != 0:
        return None
    gate = _run_landing_gate(workspace)
    if not gate.get("ok"):
        _git(workspace, "reset", "--hard", pre)
        return {"ok": False, "mode": "gate",
                "message": f"落点机械闸红（{gate.get('step')}）：{gate.get('message', '')[:200]}"}
    return {"ok": True, "mode": mode}


def merge_back(workspace: Path, job: str, accept_dirty: tuple = ()) -> dict:
    """closure 回写主干（P1：默认自动；脏树/冲突/落点闸红 ⇒ 停并升级人工，§1.4）。

    路径：先去钉（钉永不进主干，去钉产物提版）→ ff 直达；ff 不成则把线
    (base..br] `rebase --onto` 重演到主干头（线提交全是机械件，重演即普通 git）
    再 ff；冲突 ⇒ abort 复原＋升级人工。真 merge 不再使用（审计线模型）。

    **落点机械闸**：ff 主干的**同一瞬间**跑 `_run_landing_gate`；红则 `reset --hard`
    回滚主干（先验后并）——审计成果仍在线上，交人工/重审。
    accept_dirty：编排进程自己写的件（工单 task/报告落盘/state 文件）——
    守卫防的是"人的未提交工作被卷进去"，不该拦自己刚写的字。
    """
    br = branch_name(job)
    if _git(workspace, "rev-parse", "--verify", "-q", f"refs/heads/{br}").returncode != 0:
        return {"ok": True, "mode": "no-branch"}
    dirty = []

    def _covered(p: str, a: str) -> bool:
        # 目录分量边界比较：`notes/todo.md`.startswith("note") 不得被放行（ocr2-336）。
        p, a = p.rstrip("/"), a.rstrip("/")
        return bool(a) and (p == a or p.startswith(a + "/") or a.startswith(p + "/"))

    # `core.quotePath=false`：非 ASCII 路径不被八进制转义，白名单才比得上（ocr2-336）。
    for line in _git(workspace, "-c", "core.quotePath=false", "status", "--porcelain").stdout.splitlines():
        path = line[3:].split(" -> ")[-1].strip().strip('"')
        # 双向：porcelain 会把未跟踪目录折成 `docs/`，白名单写的是 `docs/tasks/…`
        if not any(_covered(path, a) for a in accept_dirty):
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
    ff = _ff_with_gate(workspace, br, pre, "ff")
    if ff is not None:
        if ff.get("ok"):
            ff["stripped"] = strip
        return ff
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
    rb_ff = _ff_with_gate(workspace, br, pre2, "rebase")
    if rb_ff is not None:
        return rb_ff
    return {"ok": False, "mode": "error", "message": "重演后仍无法 ff（异常态，交人工）"}


def prune(workspace: Path, job: str) -> dict:
    """⑤ 收口：删现场；审计线**仅在已并入主干时**删（闸过删线，ADR-0025 重设计）。

    未并入（在办/冲突未人工闭环）⇒ 线保留原位，崩溃恢复与幂等重试都靠它。
    """
    removed = []
    # 认返回码：git worktree remove 失败（目录缺失/locked/被外部清）不得被上报成"已删"，
    # 否则留下 HEAD 指向已删分支的孤立 worktree，后续 ensure 会把它当健康现场（ocr2-338）。
    rc_remove = _git(workspace, "worktree", "remove", "--force", str(worktree_path(workspace, job)))
    wt_removed = rc_remove.returncode == 0
    if wt_removed:
        removed.append(f"wt:{job}")
    br = branch_name(job)
    if wt_removed \
            and _git(workspace, "rev-parse", "--verify", "-q", f"refs/heads/{br}").returncode == 0 \
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
    # `oid` 是外部输入：形状白名单挡住前导 `-` 被当开关（`--batch` 会从 stdin 读对象名，
    # 未加 DEVNULL 时永久阻塞），`name` 不得带 `..`/控制字符/前导 `-`（ocr2-339）。
    if not oid or not re.fullmatch(r"[0-9a-fA-F]{7,40}", oid):
        return False
    if not name or not _JOB_RE.fullmatch(name):
        return False
    if _git(workspace, "cat-file", "-t", oid).stdout.strip() != "commit":
        return False
    return _git(workspace, "update-ref", f"refs/audit-baseline/{name}", oid).returncode == 0


def _safe_extractall(tf, dest: Path) -> None:
    """跨版本安全解包（code-10）。

    `TarFile.extractall(filter=...)` 3.12 首发、仅回移到 3.11.4/3.10.12+，而本仓最低
    支持 3.10（`init.sh` 声明 >=3.10）→ 低补丁版本直接 TypeError，Hall 物化动词崩。
    优先用 data 过滤器；不支持则先手工挡绝对路径/`..`/链接外逃再解包，路径收敛不放弃。
    """
    try:
        tf.extractall(dest, filter="data")
        return
    except TypeError:  # Python < 3.11.4 / < 3.10.12：filter= 尚不存在
        pass
    # 无 `filter="data"` 时的前置校验有 TOCTOU：校验在 `extractall` 之前，此时归档里的符号链接
    # 还没落盘，后续成员经由它解析时校验看不见 ⇒ `link -> /tmp` + `link/payload` 双成员可外逃（ocr2-089）。
    # 旧 Python 上不做"先验后解"：含任何链接成员直接拒（fail-closed），无链接才做 upfront 校验后解包。
    # （`dest` 为 fresh 空目录时，无链接 ⇒ `resolve()` 不会穿过不存在的链接，upfront 校验是 sound 的。）
    for member in tf.getmembers():
        if member.issym() or member.islnk():
            raise RuntimeError(f"拒绝含链接归档（旧 Python 无 data 过滤器，无法安全解包）: {member.name}")
    dest_resolved = Path(dest).resolve()
    for member in tf.getmembers():
        target = (dest_resolved / member.name).resolve()
        if not target.is_relative_to(dest_resolved):
            raise RuntimeError(f"拒绝越界解包: {member.name}")
    tf.extractall(dest)


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
    # 覆盖式解包到已有目录会残留上一版被删的文件 ⇒ Hall 拿到两版并集且无提示（ocr2-341）。
    if dest.exists() and any(dest.iterdir()):
        raise RuntimeError(f"物化目标非空，拒绝覆盖（先清空或换目录）: {dest}")
    dest.mkdir(parents=True, exist_ok=True)
    # 与 `_git` 同口径剥 `GIT_*`：否则调用方的 GIT_DIR/GIT_WORK_TREE 会让这里归档另一个仓（ocr2-341）。
    p = subprocess.run(["git", "archive", "--format=tar", rev], cwd=str(workspace),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=_clean_env(),
                       stdin=subprocess.DEVNULL)
    if p.returncode != 0:
        raise RuntimeError(f"物化失败: {p.stderr.decode('utf-8', 'replace').strip()[:160]}")
    with tarfile.open(fileobj=io.BytesIO(p.stdout)) as tf:
        _safe_extractall(tf, dest)
    return dest
