"""Two-state audit orchestration — peer contract §1 (submit → 协议外等待 → collect).

设计纪律（规则 08）：
- k3dge 只认角色 `audit`（`[roles.audit] bind` 决定实现），代码路径上不出现具体 harness 名；
- 等待不占协议：`job_id` 落编排状态（`.agent/audit_jobs.json`），何时 collect 由外层决定；
- k3dge 只验信封与形式（kind / provenance.baseline / 12 列计数），机械落盘对端字节，不补内容；
- 失败按契约错误码分类透传（报原因，不探内部）；
- `STATE_REL`（`.agent/audit_jobs.json`）是**运行态投影**（ADR-0004 §2.1.10）：本地、
  可重建、**不作判据**——判据只认 git 事实（`audit_evidence()`：边界 tag + 封版提交 trailer），
  两者冲突以 git 为准。
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Dict, Optional

from k3dge.engine import report_table
from k3dge.engine.pipeline_runner import run_action

STATE_REL = ".agent/audit_jobs.json"
_REPORT_HEADER_TOKEN = report_table.TABLE_HEADER

#: 审计结果的**闭集**（ADR-0004 §2.1.11）。唯一源：CLI / MCP / seal / 封版提交 trailer
#: 都读这里，不得各自写字符串。前两个允许推进版号，后两个不许。
AUDIT_RESULTS = ("closed", "degraded-manual", "escalated", "refused")
SEALABLE_AUDIT_RESULTS = ("closed", "degraded-manual")

#: `run_audit_flow` 的状态 → 闭集。in-flight 态（`ratchet_open` / `audit_open`）**不在**表里：
#: 它们表示"审计还没正常返回"，自然不推进版号。
_STATUS_RESULTS = {
    "audited": "closed",
    "audited_degraded": "degraded-manual",
    "escalated": "escalated",
    "rejected": "refused",
    "refused": "refused",
}


def audit_call_result(produced) -> str:
    """一跳传输的结果 → `AUDIT_RESULTS` 里的一档（ADR-0004 §2.1.11）。

    先判"这一跳是否真跑过"，再谈报告在不在——否则仓里一份旧报告就能把"什么都没跑"
    兜成闭环（本会话 M10 实测过这个洞）。`skip` 与 `ok=False` 一律 `refused`。

    `degraded-manual` 判**事实**不判位置（🅰2）：`provider == "manual"` 一律算——不管它是
    链里的降级位还是首选位。理由：`_run_manual` 自己声明产出"NOT an independent audit"
    （ADR-0006 §2.4），"没有独立透镜看过这版"是同一个事实；只看 `downgrades` 会把
    "manual 排第一位"变成绕开署名要求的路（且 trailer 会记成 `closed`＝高估记录）。
    """
    if not getattr(produced, "ok", False) or getattr(produced, "skipped", False):
        return "refused"
    if getattr(produced, "provider", None) == "manual" or getattr(produced, "downgrades", None):
        return "degraded-manual"
    return "closed"


def audit_result_of(status: str) -> Optional[str]:
    """审计流程状态 → 闭集值；in-flight（尚未正常返回）⇒ None。"""
    return _STATUS_RESULTS.get(status)


def audit_evidence(workspace: Path, milestone_id: str) -> dict:
    """审计的 **durable 证据**（判据只认这些）：边界 tag + 封版提交 trailer。

    与本地账（`.agent/audit_jobs.json` / `.agent/audit_checklist.json`）的关系是
    **写源/投影**（ADR-0004 §2.1.10）：本地账可重建、可删，**不作判据**；两者冲突
    以本函数为准（例：job.state=`collected` 但仓里无 tag/trailer ⇒ 判"未封"）。

    返回 `{"tag": <sha 或 "">, "trailers": {...}, "sealed": bool}`；非 git 仓 ⇒ 全空/False。
    """
    import subprocess

    from k3dge.engine.seal import SEAL_TRAILER_KEYS

    def _git(*args: str) -> str:
        try:
            r = subprocess.run(["git", "-C", str(workspace), *args], capture_output=True, text=True)
        except OSError:
            return ""
        return r.stdout.strip() if r.returncode == 0 else ""

    tag = _git("rev-parse", f"refs/tags/{milestone_id}^{{commit}}")
    trailers: dict = {}
    if tag:
        # 记录在**封版提交**上（tag 指基线，那条提交本身没有 trailer）⇒ 沿历史找带
        # `Seal-milestone: <id>` 的那次提交；记录分隔用 RS，字段用 US（提交正文可能多行）。
        log = _git("log", "--format=%H%x1f%(trailers)%x1e")
        for rec in log.split("\x1e"):
            rec = rec.strip("\n")
            if not rec:
                continue
            _sha, _, body = rec.partition("\x1f")
            cand = _parse_trailers(body)
            if cand.get("seal-milestone") == milestone_id:
                trailers = cand
                break
        if not trailers:
            # 第二载体：tag 注解正文（**零改动封版**没有提交可挂 ⇒ 记录只在注解里）
            trailers = _parse_trailers(_git("for-each-ref", "--format=%(contents)",
                                            f"refs/tags/{milestone_id}"))
    return {
        "tag": tag,
        "trailers": trailers,
        "sealed": bool(tag) and set(trailers) >= set(SEAL_TRAILER_KEYS),
    }


def _parse_trailers(text: str) -> dict:
    """薄委托 `seal.parse_seal_trailers`（记录格式的写源在那里，避免两处解析）。"""
    from k3dge.engine.seal import parse_seal_trailers

    return parse_seal_trailers(text)


# ---------- 编排状态（k3dge 自己的事实，不是 peer 的） ----------

def _state_path(workspace: Path) -> Path:
    return workspace / STATE_REL


def _load_state(workspace: Path) -> dict:
    p = _state_path(workspace)
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_state(workspace: Path, data: dict) -> None:
    p = _state_path(workspace)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _find_awaiting(state: dict, milestone_id: str) -> Optional[dict]:
    jobs = state.get("jobs", [])
    for job in reversed(jobs):
        if job.get("milestone_id") == milestone_id and job.get("state") == "awaiting":
            return job
    return None


def _parse_envelope(res) -> Dict:
    """从 TransportResult.payload 解析对端信封；解析不了 = 传输层失败（不当内容处理）。"""
    try:
        data = json.loads(res.payload)
        return data if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}


def _count_status(report_md: str) -> Dict[str, int]:
    """12 列表的 状态 列计数（形式可验；枚举仅三种）。

    单一表格口径：委托 `milestone._parse_audit_stats`（按表头定位「状态」列、跳过
    len != 表头 的截断行），与封板闸 `audit_trigger.audit_closed` 同源——不再固定
    cells[7] 取状态（code-13：同一报告两口径待修数会分歧，截断行可误判闭环）。
    """
    from k3dge.engine.audit_report import _parse_audit_stats

    stats = _parse_audit_stats(report_md)
    return {"待修": stats["待修"], "有意留": stats["有意留"], "已修": stats["已修"]}


# ---------- 两态入口 ----------

def submit_audit(workspace: Path, milestone_id: str, targets: Optional[list] = None, io=None,
                 role: str = "audit") -> dict:
    """produce 阶段：锁审计线 → 交件 → 落 `awaiting_audit`。协议调用必须短。

    一单一条线（ADR-0025 重设计）：`k3dit/<单>` 分支从 HEAD 拉起，锁点 L=线头 commit；
    已 checkout 的 worktree 目录即送检物。`targets` 是范围说明（Hall 物化参数），不是内容边界。
    """
    if not targets:
        # 送检范围：src（代码）+ docs（文档）——不含 .agent 等隐藏配置（真实世界不审隐藏文件）；
        # 没有 docs 的文档审计是审寂寞（doc 窗只看得到 src 内的模板）。
        targets = [t for t in ("src", "docs") if (workspace / t).is_dir()] or ["docs"]
    from k3dge.engine import worktree as _wt

    job = milestone_id or "adhoc"
    from k3dge.engine.milestone_pointer import _validate_milestone_id

    id_err = _validate_milestone_id(job)
    if id_err:
        return {"state": "failed", "detail": id_err}
    try:  # ③ 锁线：挂 worktree，脏改动进程代提交（线=现场=送检，ADR-0025 §2.9.3）
        _wt.ensure(workspace, job)
        baseline = _wt.advance(workspace, job)
    except Exception as exc:  # 非 git 仓 ⇒ 无法锁线，审计不可进行（如实报，不静默）
        return {"state": "failed", "detail": f"审计线锁线失败（消费仓须为 git 仓）: {str(exc)[:160]}"}
    if not baseline:
        return {"state": "failed", "detail": "消费仓无任何提交，无法锁审计线"}
    branch = _wt.branch_name(job)
    res = run_action(
        workspace,
        f"{role}.submit",
        io=io,
        arguments={
            "baseline": baseline,
            "scope": ",".join(targets),
            "milestone_id": milestone_id,
            # ① 交件句柄（字符串；线归 k3dge，机构凭 wt_dir 读、Hall 收回改动经 advance，
            #    席位/机构永不直接操作消费仓 .git——ADR-0025 §2.9.2）
            "branch": branch,
            "wt_dir": str(_wt.worktree_path(workspace, job).resolve()),
            # 机械闸不在审计侧（ADR-0025 Note ㉖）：`fixed`＝复核背书；代码能跑/过闸归消费侧
            # 落点（本仓 pre-commit `check` + CI `pytest`/`check --with-tests`），k3dit Hall 不执行。
        },
    )
    if res.skipped or not res.ok:
        why = "跳被跳过（skip）" if res.skipped else res.detail
        return {"state": "failed", "detail": f"{role}.submit 未真跑：{why}",
                "downgrades": res.downgrades}
    env = _parse_envelope(res)
    if not env.get("ok") or env.get("kind") != "job":
        return {
            "state": "failed",
            "detail": f"{role}.submit 未按契约返回 job 信封: {env.get('error') or env.get('message') or res.detail}",
            "downgrades": res.downgrades,
        }
    job_id = (env.get("payload") or {}).get("job_id", "")
    # 裁决 a：工单由 k3dge 派 ⇒ 消费侧对应物是 task（封板"全 done"闸兜底，跑不丢）
    from k3dge.engine.task_write import create_task

    ok_t, _m, task_path = create_task(
        workspace,
        f"audit job {job_id}: {','.join(targets)}",
        typ="audit",
        slug=f"audit_job_{job_id}",
        milestone=milestone_id or None,
        priority="P2",
    )
    state = _load_state(workspace)
    jobs = state.setdefault("jobs", [])
    jobs.append({
        "role": role,
        "ticket_task": task_path.relative_to(workspace).as_posix() if (ok_t and task_path) else None,
        "job_id": job_id,
        "milestone_id": milestone_id,
        "baseline": baseline,
        "branch": branch,
        "state": "awaiting",
        "submitted_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
    })
    _save_state(workspace, state)
    try:  # P0：首程存底（无钉则空单，也建底）；推送失败不否决建单
        push = push_present(workspace, job_id)
    except Exception:
        push = {}
    from k3dge.engine import events
    events.emit(workspace, "audit_submit", job_id=job_id, milestone=milestone_id, baseline=baseline)
    return {"ok": True, "state": "awaiting_audit", "job_id": job_id,
            "baseline": baseline, "branch": branch,
            "present_pushed": push.get("markers") if push.get("ok") else None}


def collect_audit(workspace: Path, milestone_id: str, job_id: Optional[str] = None, io=None) -> dict:
    """gate 阶段：`audit.collect` → 验壳（kind/基线/12 列）→ 机械落盘 → 数计数。

    返回态：`awaiting_audit`（PENDING/无 job）、`failed`（NOT_FOUND/FORMAT/基线不符）、
    `open`（待修>0）、`closed`（待修=0，可谈放行）。
    """
    state = _load_state(workspace)
    if job_id:
        job = next((j for j in state.get("jobs", []) if j.get("job_id") == job_id), None)
    else:
        job = _find_awaiting(state, milestone_id)
    if job is None:
        return {"state": "awaiting_audit", "detail": "no awaiting audit job; submit first"}
    role = job.get("role", "audit")
    # milestone_id 拼进落盘文件名（下方 report_path），必须先过安全校验；空值回落 adhoc（submit 同口径）
    from k3dge.engine.milestone_pointer import _validate_milestone_id

    safe_ms = milestone_id or job.get("milestone_id") or "adhoc"
    id_err = _validate_milestone_id(safe_ms)
    if id_err:
        return {"state": "failed", "error": "FORMAT", "detail": id_err}

    res = run_action(workspace, f"{role}.collect", io=io, arguments={"job_id": job["job_id"]})
    if res.skipped:
        job["state"] = "failed"
        _save_state(workspace, state)
        return {"state": "failed", "error": "NOOP",
                "detail": f"{role}.collect 未真跑：跳被跳过（skip）——空转不得当闭环（ADR-0004 §2.1.11）"}
    env = _parse_envelope(res)
    if not env.get("ok"):
        err = str(env.get("error") or "")
        if err == "PENDING":
            return {"state": "awaiting_audit", "detail": env.get("message") or "peer reports PENDING",
                    "retry_after": env.get("retry_after")}
        job["state"] = "failed"
        _save_state(workspace, state)
        if err in ("NOT_FOUND", "EXPIRED"):
            return {"state": "resubmit_needed", "detail": env.get("message") or err, "error": err}
        return {"state": "failed", "detail": env.get("message") or res.detail, "error": err or "INTERNAL"}

    if env.get("kind") != "report":
        job["state"] = "failed"
        _save_state(workspace, state)
        return {"state": "failed", "error": "FORMAT",
                "detail": f"契约要求 kind=report，实际 {env.get('kind')!r}"}

    payload = env.get("payload") or {}
    report_md = payload.get("report_markdown", "")
    if not report_table.has_table(report_md):
        job["state"] = "failed"
        _save_state(workspace, state)
        return {"state": "failed", "error": "FORMAT", "detail": "report 缺少 12 列表头（ADR-0017）"}

    prov = env.get("provenance") or {}
    baseline_ok = (prov.get("baseline") or "") == job["baseline"]
    if not baseline_ok:
        # 基线不符 = 报告与审计线锁点脱钩：拒收（不静默）
        job["state"] = "failed"
        _save_state(workspace, state)
        return {"state": "failed", "error": "FORMAT",
                "detail": f"provenance.baseline 与审计线锁点不符: {prov.get('baseline')!r} != {job['baseline']!r}"}

    # 机械落盘：对端字节原样写入，k3dge 不补内容（契约 §4）
    reviews = workspace / "docs" / "reviews"
    reviews.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()
    report_path = reviews / f"{today}-{safe_ms}-{'quality' if role != 'audit' else 'audit'}.md"
    # 案卷防互踩闸（首夜事故根因）：目标已有**异类或异基线**报告 ⇒ 拒落，不静默覆盖
    if report_path.is_file():
        prev = report_path.read_text(encoding="utf-8", errors="ignore")
        head = prev.lstrip()[:80]
        prev_quality = head.startswith("<!-- k3dge:kind: quality -->")
        if prev_quality != (role != "audit"):
            return {"ok": False, "state": "failed", "error": "FORMAT",
                    "message": f"拒绝跨类覆盖：{report_path.name} 已是{'质量' if prev_quality else '审计'}案卷"}
        # （跨单覆盖是重提交设计的一部分，不拦；只拦跨类互踩）
    report_path.write_text(report_md if report_md.endswith("\n") else report_md + "\n", encoding="utf-8")

    counts = _count_status(report_md)
    try:
        from k3dge.engine.milestone_audit import _ensure_leftovers

        _ensure_leftovers(workspace, report_md, report_path)
    except Exception as exc:  # 有意留漏登不得否决闭环，但必须可见
        print(f"[WARN][LEFTOVERS] 有意留未写入 LEFTOVERS.md: {exc}", file=__import__("sys").stderr)
    # 未尽项报告（`<!-- k3dge:incomplete -->`）：无论计数，绝不闭环/不 merge，交人工
    if "<!-- k3dge:incomplete -->" in report_md:
        outcome = "open"
    else:
        outcome = "open" if counts["待修"] > 0 else "closed"
    merged: Dict[str, Any] = {}
    if outcome == "closed":
        from k3dge.engine import worktree as _wt

        mine = [report_path.relative_to(workspace).as_posix(), STATE_REL,
                ".agent/audit_checklist.json", "docs/reviews/", "docs/tasks/"]
        ticket = job.get("ticket_task")
        if ticket:
            mine.append(ticket)
        try:
            merged = _wt.merge_back(workspace, milestone_id or "adhoc", accept_dirty=tuple(mine))
        except Exception as exc:  # pragma: no cover
            merged = {"ok": False, "mode": "error", "message": str(exc)[:120]}
    job["state"] = "collected"
    job["collected_at"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    job["report"] = report_path.relative_to(workspace).as_posix()
    job["counts"] = counts
    # merge 没闭 ⇒ collected 但 merge_ok=False：棘轮步进器拿着它幂等重试（冲突后的人工重试面）
    job["merge_ok"] = bool(merged.get("ok", True))
    pinned = False
    if outcome == "closed":
        if job["merge_ok"]:
            # rebase 合线后 pre-rebase oid 不在主干祖先链上；记下合线瞬间的主干头，
            # 供 `_baseline_covers` 认「审的内容已落在 B」（seal 相位 2 不再误建新单）。
            from k3dge.engine.seal import head_commit as _head

            landed = _head(workspace)
            if landed:
                job["landed_head"] = landed
        try:  # 闭环基线留存：报告引用的 commit 经重演可能悬空，钉 ref 防 gc；失败不否决闭环
            from k3dge.engine import worktree as _wt2

            pinned = bool(_wt2.pin_baseline(workspace, job["job_id"], job["baseline"]))
        except Exception:
            pinned = False
        ticket = job.get("ticket_task")
        if ticket and job["merge_ok"]:
            try:
                tp = workspace / ticket
                if tp.is_file():
                    seat = ((env.get("provenance") or {}).get("seat")) or "-"
                    rel = report_path.relative_to(workspace).as_posix()
                    body = tp.read_text(encoding="utf-8")
                    if "## 结案" not in body:
                        tp.write_text(body.rstrip() + (
                            f"\n\n## 结案\n\n"
                            f"- 报告：`{rel}`"
                            f"（待修 {counts['待修']} / 有意留 {counts['有意留']} / 已修 {counts['已修']}）\n"
                            f"- 席位：{seat}\n"
                        ), encoding="utf-8")
                from k3dge.engine.task_write import mark_task_done

                ok_d, _m, new_p = mark_task_done(workspace, ticket)
                if ok_d and new_p is not None:
                    job["ticket_task"] = new_p.relative_to(workspace).as_posix()
            except Exception as exc:  # 关票失败不否决闭环
                print(f"[WARN][TICKET] collect 关票失败: {exc}", file=__import__("sys").stderr)
    _save_state(workspace, state)
    from k3dge.engine import events
    events.emit(
        workspace, "audit_collect", job_id=job["job_id"], milestone=milestone_id,
        state=outcome, pending=counts["待修"], report=job["report"],
    )
    return {
        "ok": True,
        "merge": merged,
        "state": outcome,
        "pending": counts["待修"],
        "kept": counts["有意留"],
        "fixed": counts["已修"],
        "report": job["report"],
        "seat": prov.get("seat", ""),
        "baseline_ok": True,
        "baseline_pinned": pinned,
    }


def push_present(workspace: Path, job_key: str, commit: str = "", io=None) -> dict:
    """P0 接线：advance/submit 后进程抽取 worktree markers 推给对端（机械口供）。"""
    from k3dge.engine import worktree as _wt

    state = _load_state(workspace)
    cands = [j for j in state.get("jobs", [])
             if j.get("state") not in ("collected", "failed")
             and job_key in (j.get("job_id"), j.get("milestone_id"))]
    if not cands:
        return {"ok": False, "skipped": f"no in-flight job for {job_key!r}"}
    try:
        markers = _wt.present(workspace, cands[-1].get("milestone_id") or "adhoc", commit or None)
    except Exception as exc:   # 非 git 仓/无 worktree ⇒ 降级：没有机械口供可推，不炸编排
        return {"ok": False, "skipped": f"present extract failed: {str(exc)[:80]}"}
    pushed = []
    for job in cands:   # 两腿共 worktree：present 扇出给每条在办腿
        res = run_action(workspace, f"{job.get('role', 'audit')}.present", io=io,
                         arguments={"job_id": job["job_id"], "present_json": json.dumps(markers),
                                    "commit": commit or "",
                                    "present_seq": job.get("present_seq", 0) + 1})
        entry = {"job_id": job["job_id"], "ok": res.ok, "markers": len(markers)}
        if res.ok:  # 送达才加版本号：对端凭 seq 判口供新旧
            job["present_seq"] = job.get("present_seq", 0) + 1
            entry["seq"] = job["present_seq"]
        pushed.append(entry)
    _save_state(workspace, state)
    return {"ok": all(p["ok"] for p in pushed), "pushed": pushed, "markers": len(markers)}


def advance_line(workspace: Path, job_key: str, by: str = "manual", io=None) -> dict:
    """Hall 管线收拢动词：提版 → 重钉在办单基线 → 推 present。

    基线连续钉（线即主体）：提版后的新线头即在办单的新 baseline，报告按最新基线签；
    判读窗在旧 L 下的工作由复核窗覆盖（审计线模型，契约 §3）。
    `by` 记录调用方身份（hall/修席窗/人），G2 主权线可审计。
    """
    from k3dge.engine import worktree as _wt

    job = job_key or "adhoc"
    try:
        commit = _wt.advance(workspace, job)
    except RuntimeError as exc:
        return {"ok": False, "message": str(exc)}
    if not commit:
        return {"ok": False, "message": "消费仓无任何提交，无法提版"}
    state = _load_state(workspace)
    repinned = []
    for j in state.get("jobs", []):
        if j.get("state") not in ("collected", "failed") \
                and job_key in (j.get("job_id"), j.get("milestone_id")):
            j["baseline"] = commit
            j.setdefault("advances", []).append({
                "at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
                "by": by, "commit": commit})
            repinned.append(j["job_id"])
    _save_state(workspace, state)
    try:
        push = push_present(workspace, job_key, commit, io=io)
    except Exception:
        push = {}
    return {"ok": True, "commit": commit, "baseline": commit, "by": by,
            "repinned": repinned,
            "present_pushed": push.get("markers") if push.get("ok") else None,
            "pushed": push.get("pushed")}


def peer_status(workspace: Path, job_id: str, io=None) -> dict:
    """编排侧探针：`audit.status` 查对端状态机位置与计数（正文不出账本，出货走 collect）。

    `job_id` 也可是里程碑 id：本地账里按 milestone 取最新一单再探（CLI `audit status M10`
    曾把里程碑当 job_id → NOT_FOUND）。
    """
    state = _load_state(workspace)
    rec = next((j for j in state.get("jobs", []) if j.get("job_id") == job_id), None)
    if rec is None and job_id:
        mine = [j for j in state.get("jobs", []) if j.get("milestone_id") == job_id]
        if mine:
            rec = mine[-1]
            job_id = rec.get("job_id") or job_id
    role = rec.get("role", "audit") if rec else "audit"
    res = run_action(workspace, f"{role}.status", io=io, arguments={"job_id": job_id})
    if not res.ok:
        return {"ok": False, "state": "unknown", "message": res.detail, "downgrades": res.downgrades}
    env = _parse_envelope(res)
    payload = env.get("payload") if isinstance(env.get("payload"), dict) else env
    out = {"ok": bool(env.get("ok", True)), "job_id": job_id}
    out.update({k: payload.get(k) for k in
                ("state", "open", "counts", "escalated", "rounds", "lens_version", "error", "message",
                 "total_dur_s", "tries", "bounces", "incomplete", "line")
                if payload.get(k) is not None})
    return out


def open_ratchet_jobs(workspace: Path) -> list:
    """本地账上未回口的工单（只读本地 state——不为路由去打对端网络）。"""
    state = _load_state(workspace)
    return [j for j in state.get("jobs", []) if j.get("state") not in ("collected", "failed")]


def show_job(workspace: Path, job_key: str = "") -> dict:
    """Hall 查询动词：读本地账（不打对端网络）＋ 本地降级尾。

    对应缺口：`audit status` 查的是对端；Hall 要 k3dge 侧 baseline/branch/merge_ok
    此前只能 parse JSON 文件。输出含最近降级行，供 Hall 通告牌（W3）。
    """
    state = _load_state(workspace)
    jobs = [j for j in state.get("jobs", [])
            if not job_key or job_key in (j.get("job_id"), j.get("milestone_id"))]
    return {"ok": True, "jobs": jobs, "recent_downgrades": _recent_downgrades(workspace)}


def _recent_downgrades(workspace: Path, limit: int = 20) -> list:
    """`logs/k3dge.log` 尾部 WARN[DOWNGRADE] 行（本仓自有格式，Hall 侧只读展示）。"""
    try:
        lines = (workspace / "logs" / "k3dge.log").read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return []
    out = [ln.strip() for ln in lines if "WARN[DOWNGRADE]" in ln]
    return out[-limit:]


def materialize(workspace: Path, job_key: str = "", rev: str = "", dest: str = "") -> dict:
    """Hall 只读物化：把 rev（缺=在办单基线）的树解到 dest（不带 .git，不碰线/worktree）。

    对应缺口：wt 是活物，Hall 按 oid 取旧基线此前只能自己对消费仓 `.git` 下手。
    """
    from k3dge.engine import worktree as _wt

    state = _load_state(workspace)
    job = next((j for j in state.get("jobs", [])
                if job_key and job_key in (j.get("job_id"), j.get("milestone_id"))), None)
    rev = rev or (job or {}).get("baseline", "") or "HEAD"
    slug = (job or {}).get("milestone_id") or "adhoc"
    out = Path(dest) if dest else workspace / ".k3dge" / "mat" / slug / rev[:12]
    try:
        path = _wt.materialize(workspace, rev, out)
    except RuntimeError as exc:
        return {"ok": False, "message": str(exc)}
    return {"ok": True, "rev": rev, "dest": path.relative_to(workspace).as_posix()
            if path.is_relative_to(workspace) else str(path)}


def prune_finished(workspace: Path) -> dict:
    """⑤ seal 收口钩子：清已结案 job 的 worktree 与审计线（幂等，容错）。

    收口＝闸过合主干后删线删现场（ADR-0025 重设计）；主干已含线内容，史在 main。
    """
    from k3dge.engine import worktree as _wt

    state = _load_state(workspace)
    done = [j for j in state.get("jobs", []) if j.get("state") == "collected"]
    out = []
    for j in done:
        out.append(_wt.prune(workspace, j.get("milestone_id") or "adhoc"))
    # 弹壳区随收口清空（README 是区规本身，留）——"定期清"是机验，不是自律
    swept = 0
    tmpd = workspace / "tmp"
    if tmpd.is_dir():
        for junk in tmpd.iterdir():
            if junk.is_file() and junk.name != "README.md":
                try:
                    junk.unlink(); swept += 1
                except OSError:
                    pass
    return {"pruned": len(out), "tmp_swept": swept, "detail": out}
