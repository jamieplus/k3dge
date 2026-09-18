"""Milestone cursor + id validation."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

_SAFE_MILESTONE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _milestone_file(workspace: Path) -> Path:
    return workspace / ".agent" / "milestone"


def get_current_milestone(workspace: Path) -> str:
    """Current milestone cursor, default M0; stored in .agent/milestone."""
    p = _milestone_file(workspace)
    if p.is_file():
        try:
            v = p.read_text(encoding="utf-8").strip()
            if v and _SAFE_MILESTONE_ID_RE.fullmatch(v):
                return v
        except (OSError, UnicodeDecodeError):
            pass
    return "M0"


def set_current_milestone(workspace: Path, milestone_id: str) -> None:
    err = _validate_milestone_id(milestone_id)
    if err:
        raise ValueError(err)
    p = _milestone_file(workspace)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(milestone_id + "\n", encoding="utf-8")


def bump_milestone(workspace: Path) -> str:
    """M0 → M1 → M2 …; writes new cursor and returns it."""
    cur = get_current_milestone(workspace)
    m = re.match(r"^M(\d+)$", cur)
    if m:
        nxt = f"M{int(m.group(1)) + 1}"
    else:
        # Fallback: treat any id as base, suffix -next (should not happen for M* flow)
        nxt = f"{cur}-next"
    set_current_milestone(workspace, nxt)
    return nxt


def _validate_milestone_id(milestone_id: str) -> Optional[str]:
    """Return an error message if `milestone_id` is unsafe as a path component."""
    if not milestone_id or not _SAFE_MILESTONE_ID_RE.fullmatch(milestone_id):
        return (
            f"Invalid milestone id '{milestone_id}': use a letter/digit start, "
            "then letters, digits, '.', '_' or '-' only (no path separators)."
        )
    return None
