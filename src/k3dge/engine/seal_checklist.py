"""Seal-eligibility checklist cache (ADR-0004 §2.1.2 revised).

The hard gate (`k3dge check`) surfaces seal eligibility, but recomputing full
eligibility (scan the current milestone's tasks) on *every* `check` is wasteful.
We cache a checklist keyed by a hash of the current milestone's task statuses;
`check` reads the cache and only recomputes when the task set actually changes.

The manual seal entry (`k3dge milestone seal`) also consults / regenerates this
checklist, and it tracks `verify_attempts` so the audit auto-loop can escalate
to a human after `MAX_VERIFY_ATTEMPTS` (default 3) instead of looping forever.
"""

from __future__ import annotations

import datetime
import hashlib
import json
from pathlib import Path
from typing import Optional

CHECK_LIST_PATH = ".agent/seal_checklist.json"
MAX_VERIFY_ATTEMPTS = 3


def _path(workspace: Path) -> Path:
    return workspace / CHECK_LIST_PATH


def _tasks_hash(workspace: Path, milestone_id: str) -> str:
    from k3dge.engine.milestone import scan_milestone_tasks

    tasks = scan_milestone_tasks(workspace, milestone_id)
    h = hashlib.sha256()
    for t in sorted(tasks, key=lambda x: x.path.name):
        h.update(f"{t.path.name}:{t.status}".encode("utf-8"))
    return h.hexdigest()


def compute_eligibility(workspace: Path) -> tuple[dict, bool]:
    """Recompute eligibility from scratch and persist the checklist."""
    from k3dge.engine.milestone import get_current_milestone, scan_milestone_tasks

    mid = get_current_milestone(workspace)
    tasks = scan_milestone_tasks(workspace, mid)
    tasks_done = bool(tasks) and all(t.status == "done" for t in tasks)
    # Preserve verify_attempts across recomputes only when the task set is unchanged;
    # a changed task set is a new situation, so reset the counter.
    prev = read_checklist(workspace)
    keep_attempts = prev is not None and prev.get("tasks_hash") == _tasks_hash(workspace, mid)
    data = {
        "milestone_id": mid,
        "tasks_total": len(tasks),
        "tasks_done": tasks_done,
        "tasks_hash": _tasks_hash(workspace, mid),
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "verify_attempts": prev.get("verify_attempts", 0) if keep_attempts else 0,
        "audit_state": prev.get("audit_state", "pending") if keep_attempts else "pending",
    }
    _write(workspace, data)
    return data, tasks_done


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
    # Invalidate when the task set changed since the checklist was written.
    if data.get("tasks_hash") != _tasks_hash(workspace, mid):
        return None
    return data


def ensure_checklist(workspace: Path) -> dict:
    data = read_checklist(workspace)
    if data is None:
        data, _ = compute_eligibility(workspace)
    return data


def is_eligible(workspace: Path) -> bool:
    return bool(ensure_checklist(workspace).get("tasks_done"))


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
