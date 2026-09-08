"""Two-state audit orchestration — peer contract §1 (submit → 协议外等待 → collect).

设计纪律（规则 08）：
- k3dge 只认角色 `audit`（`[roles.audit] bind` 决定实现），代码路径上不出现具体 harness 名；
- 等待不占协议：`job_id` 落编排状态（`.agent/audit_jobs.json`），何时 collect 由外层决定；
- k3dge 只验信封与形式（kind / provenance.baseline / 12 列计数），机械落盘对端字节，不补内容；
- 失败按契约错误码分类透传（报原因，不探内部）。
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Dict, Optional

from k3dge.engine.pipeline_runner import run_action

STATE_REL = ".agent/audit_jobs.json"
_REPORT_HEADER_TOKEN = "ID|日期|严重度|优先级|类型|问题描述|位置|状态|处置|验证|复审|验收"


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
    """12 列表的 状态 列计数（形式可验；枚举仅三种）。"""
    counts = {"待修": 0, "有意留": 0, "已修": 0}
    for line in report_md.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 8 and cells[0] not in ("ID", "---") and not set(cells[0]) <= set("-: "):
            status = cells[7]
            if status in counts:
                counts[status] += 1
    return counts


# ---------- 两态入口 ----------

def submit_audit(workspace: Path, milestone_id: str, targets: Optional[list] = None, io=None,
                 role: str = "audit") -> dict:
    """produce 阶段：锁审计线 → 交件 → 落 `awaiting_audit`。协议调用必须短。

    一单一条线（ADR-0026 重设计）：`k3dit/<单>` 分支从 HEAD 拉起，锁点 L=线头 commit；
    已 checkout 的 worktree 目录即送检物。`targets` 是范围说明（Hall 物化参数），不是内容边界。
    """
    targets = targets or (["src"] if (workspace / "src").is_dir() else ["docs"])
    from k3dge.engine import worktree as _wt

    job = milestone_id or "adhoc"
    try:  # ③ 锁线：挂 worktree，脏改动进程代提交（线=现场=送检，ADR-0026 §2.3）
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
            #    席位/机构永不直接操作消费仓 .git——ADR-0026 §2.2）
            "branch": branch,
            "wt_dir": str(_wt.worktree_path(workspace, job).resolve()),
        },
    )
    if not res.ok:
        return {"state": "failed", "detail": res.detail, "downgrades": res.downgrades}
    env = _parse_envelope(res)
    if not env.get("ok") or env.get("kind") != "job":
        return {
            "state": "failed",
            "detail": f"{role}.submit 未按契约返回 job 信封: {env.get('error') or env.get('message') or res.detail}",
            "downgrades": res.downgrades,
        }
    job_id = (env.get("payload") or {}).get("job_id", "")
    # 裁决 a：工单由 k3dge 派 ⇒ 消费侧对应物是 task（封板"全 done"闸兜底，跑不丢）
    from k3dge.engine.milestone import create_task

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
        "submitted_at": datetime.datetime.now().isoformat(timespec="seconds"),
    })
    _save_state(workspace, state)
    try:  # P0：首程存底（无钉则空单，也建底）；推送失败不否决建单
        push = push_present(workspace, job_id)
    except Exception:
        push = {}
    return {"ok": True, "state": "awaiting_audit", "job_id": job_id,
            "baseline": baseline, "branch": branch,
            "present_pushed": push.get("markers") if push.get("ok") else None}


# k3dit:leftover Q-2 CC26 collect_audit 提取验证子步骤
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

    res = run_action(workspace, f"{role}.collect", io=io, arguments={"job_id": job["job_id"]})
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
    if _REPORT_HEADER_TOKEN.replace("|", "") not in report_md.replace("|", "").replace(" ", ""):
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
    report_path = reviews / f"{today}-{milestone_id}-{'quality' if role != 'audit' else 'audit'}.md"
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
    ticket = job.get("ticket_task")
    if ticket:
        try:
            tp = workspace / ticket
            if tp.is_file():
                tp.write_text(
                    tp.read_text(encoding="utf-8").rstrip()
                    + f"\n\n## 回收记录\n\n- 报告：`{report_path.relative_to(workspace).as_posix()}`"
                    + f"（待修 {counts['待修']} / 有意留 {counts['有意留']} / 已修 {counts['已修']}）\n"
                    + f"- 席位：{((env.get('provenance') or {}).get('seat')) or '-'}；"
                    + "本 task 在报告回填闭环（待修=0）后由修复席位 `task done`\n",
                    encoding="utf-8",
                )
        except OSError as exc:  # 回填失败不改判定，但必须可见（工单与审计状态不许静默脱钩）
            print(f"[WARN][TICKET] 工单回填失败: {exc}", file=__import__("sys").stderr)
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
    job["collected_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    job["report"] = report_path.relative_to(workspace).as_posix()
    job["counts"] = counts
    # merge 没闭 ⇒ collected 但 merge_ok=False：棘轮步进器拿着它幂等重试（冲突后的人工重试面）
    job["merge_ok"] = bool(merged.get("ok", True))
    _save_state(workspace, state)
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
                                    "commit": commit or ""})
        pushed.append({"job_id": job["job_id"], "ok": res.ok, "markers": len(markers)})
    return {"ok": all(p["ok"] for p in pushed), "pushed": pushed, "markers": len(markers)}


def peer_status(workspace: Path, job_id: str, io=None) -> dict:
    """编排侧探针：`audit.status` 查对端状态机位置与计数（正文不出账本，出货走 collect）。"""
    state = _load_state(workspace)
    rec = next((j for j in state.get("jobs", []) if j.get("job_id") == job_id), None)
    role = rec.get("role", "audit") if rec else "audit"
    res = run_action(workspace, f"{role}.status", io=io, arguments={"job_id": job_id})
    if not res.ok:
        return {"ok": False, "state": "unknown", "message": res.detail, "downgrades": res.downgrades}
    env = _parse_envelope(res)
    payload = env.get("payload") if isinstance(env.get("payload"), dict) else env
    out = {"ok": bool(env.get("ok", True)), "job_id": job_id}
    out.update({k: payload.get(k) for k in
                ("state", "open", "counts", "escalated", "rounds", "lens_version", "error", "message")
                if payload.get(k) is not None})
    return out


def open_ratchet_jobs(workspace: Path) -> list:
    """本地账上未回口的工单（只读本地 state——不为路由去打对端网络）。"""
    state = _load_state(workspace)
    return [j for j in state.get("jobs", []) if j.get("state") not in ("collected", "failed")]


def prune_finished(workspace: Path) -> dict:
    """⑤ seal 收口钩子：清已结案 job 的 worktree 与审计线（幂等，容错）。

    收口＝闸过合主干后删线删现场（ADR-0026 重设计）；主干已含线内容，史在 main。
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
