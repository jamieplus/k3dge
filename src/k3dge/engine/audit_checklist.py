"""Audit-condition checklist (ADR-0004 §2.1.5; reframed from the old seal gate).

Records whether the *audit conditions* are met for the current milestone and the
state of the audit loop — not "can I seal". The checklist holds:
  - the quantifiable suggestion snapshot (audit_trigger: 账齐 / C2 / 体积) -> reasons
  - report closure: the single audit 12-col report's 待修 (merged audit module, ADR-0025)
  - verify_attempts: the >3-loop escalation counter (reset on each audit initiation)
  - audit_started_at: when the current audit pass was initiated (manual or auto)

Caching: keyed by a hash of the current milestone's task statuses so `check` need
not re-scan when nothing changed. **Initiating an audit (`k3dge milestone audit`)
resets the checklist** (fresh verify budget + new started_at).

**这是运行态投影，不是判据**（ADR-0004 §2.1.10 🅰1）：文件在 `.agent/`（本地、可删、可重建）；
判据只认 git 事实（基线 hash / 边界 `tag <M>=<B>` / 封版提交 trailer，见
`audit_flow.audit_evidence`），两者冲突**以 git 为准**。`[NEXT] seal_ready` 的判据在
`cli/status.lifecycle_next`（预审＝形式闸），也不在此。
"""

from __future__ import annotations

import datetime
import hashlib
import json
from pathlib import Path
from typing import Optional

CHECK_LIST_PATH = ".agent/audit_checklist.json"


def _path(workspace: Path) -> Path:
    return workspace / CHECK_LIST_PATH


def _tasks_hash(workspace: Path, milestone_id: str) -> str:
    from k3dge.engine.task_index import scan_milestone_tasks

    tasks = scan_milestone_tasks(workspace, milestone_id)
    h = hashlib.sha256()
    for t in sorted(tasks, key=lambda x: x.path.name):
        h.update(f"{t.path.name}:{t.status}".encode("utf-8"))
    return h.hexdigest()


def _snapshot(workspace: Path, milestone_id: str) -> dict:
    from k3dge.engine.audit_trigger import audit_closed, compute_audit_suggestion
    from k3dge.engine.audit_report import _find_report, _parse_audit_stats

    suggested, reasons = compute_audit_suggestion(workspace)
    found = _find_report(workspace, milestone_id, "audit")
    # **升级计入 pending**：k3dge 自己写的升级标记在报告**验证**列（`待验：未闭环` / `升级：本次未落`）——
    # 判定面（封板前置闸 / `[NEXT]`）读的是本清单的 `pending` ⇒ 不计它就会**虚报已审**（用户裁定：
    # 升级由 k3dge 的审后闸报出；报告"状态"列保持产出方原样，所以这里必须自己数）。
    escalated = 0
    if found is not None:
        from k3dge.engine.audit_bundle import ESCALATION_MARKERS
        from k3dge.engine.report_table import parse_rows

        _, rows = parse_rows(found[1])
        escalated = sum(1 for _i, r in rows
                        if any(m in str(r.get("验证") or "") for m in ESCALATION_MARKERS))
    closure = {
        "audit": {
            "present": found is not None,
            "pending": ((_parse_audit_stats(found[1])["待修"] + escalated) if found else None),
            "escalated": escalated,
        },
    }
    return {
        "audit_suggested": suggested,
        "reasons": reasons,
        "closure": closure,
        "closed": audit_closed(workspace, milestone_id),
    }


def build_checklist(workspace: Path, milestone_id: Optional[str] = None) -> dict:
    """Recompute the audit-condition snapshot and persist it (keeps counters if the
    task set is unchanged)."""
    from k3dge.engine.milestone_pointer import get_current_milestone

    mid = milestone_id or get_current_milestone(workspace)
    h = _tasks_hash(workspace, mid)
    prev = read_checklist(workspace)
    keep = prev is not None and prev.get("tasks_hash") == h
    data = {
        "milestone_id": mid,
        "tasks_hash": h,
        "generated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "audit_started_at": (prev or {}).get("audit_started_at") if keep else None,
        "verify_attempts": (prev or {}).get("verify_attempts", 0) if keep else 0,
    }
    data.update(_snapshot(workspace, mid))
    _write(workspace, data)
    return data


def read_checklist(workspace: Path) -> Optional[dict]:
    p = _path(workspace)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    mid = data.get("milestone_id")
    if mid is None:
        return None
    if data.get("tasks_hash") != _tasks_hash(workspace, mid):
        return None  # stale: task set changed
    return data


def ensure_checklist(workspace: Path) -> dict:
    return read_checklist(workspace) or build_checklist(workspace)


def reset_for_audit(workspace: Path, milestone_id: Optional[str] = None) -> dict:
    """Called when an audit pass is initiated (manual `milestone audit` or auto):
    fresh snapshot + verify budget reset + stamp started_at."""
    from k3dge.engine.milestone_pointer import get_current_milestone

    mid = milestone_id or get_current_milestone(workspace)
    data = build_checklist(workspace, mid)
    data["verify_attempts"] = 0
    data["audit_started_at"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    _write(workspace, data)
    return data


def get_verify_attempts(workspace: Path) -> int:
    return int(ensure_checklist(workspace).get("verify_attempts", 0))


def bump_verify_attempt(workspace: Path) -> int:
    data = ensure_checklist(workspace)
    data["verify_attempts"] = int(data.get("verify_attempts", 0)) + 1
    _write(workspace, data)
    return int(data["verify_attempts"])


def reset_verify_attempts(workspace: Path) -> None:
    data = ensure_checklist(workspace)
    data["verify_attempts"] = 0
    _write(workspace, data)


def _write(workspace: Path, data: dict) -> None:
    p = _path(workspace)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
