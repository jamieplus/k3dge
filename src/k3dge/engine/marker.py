"""Session marker: single owner of the lightweight attended_zones record.

Design (audit k3d9e tensions 1-2, ADR 0022):
- No state machine, no residual diff scan. `git status --porcelain` projects the
  working tree; this file only records cross-CLI-process *attendance* causal evidence.
- `session.json` shape: {session_id, epoch_id, attended_zones: [{zone, epoch}]}.
- `epoch_id` is auto-generated (`uuid4().hex[:8]`) when no external harness supplies one;
  it rotates on `k3dge end` / timeout so a stale disk record can never grant cross-session exemption.
- `attended_zones` is advisory only — it NEVER skips the IO-boundary protocol injection or
  the challenge; it is just the cross-process receipt.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import List, Optional, Tuple

SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_EPOCH_TTL_SECONDS = 3600


def session_path(workspace: Path) -> Path:
    return workspace / ".agent" / "session.json"


def _gen_session_id() -> str:
    return "sess-" + uuid.uuid4().hex[:8]


def _gen_epoch_id() -> str:
    return uuid.uuid4().hex[:8]


def _read(workspace: Path) -> dict:
    p = session_path(workspace)
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return {}
    return {}


def _atomic_write(workspace: Path, data: dict) -> None:
    p = session_path(workspace)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, p)  # atomic; never leave a half-written JSON


def _safe_rel(workspace: Path, zone: str) -> str:
    """SEC-01: reject paths that escape the workspace (../ traversal, symlink escape)."""
    try:
        abs_zone = (workspace / zone).resolve()
        abs_root = workspace.resolve()
        abs_zone.relative_to(abs_root)
    except (ValueError, OSError) as exc:
        raise ValueError(f"zone '{zone}' escapes workspace root (SEC-01)") from exc
    return str(Path(zone)).replace("\\", "/")


def ensure_epoch(workspace: Path, epoch_id: Optional[str] = None) -> str:
    """Return the active epoch_id, generating/rotating it if absent or stale."""
    data = _read(workspace)
    if not data.get("session_id"):
        data["session_id"] = _gen_session_id()
    rotated = False
    if not epoch_id:
        existing = data.get("epoch_id")
        started_at = data.get("epoch_started_at")
        if not existing or _is_stale(started_at):
            epoch_id = _gen_epoch_id()
            rotated = True
    else:
        if not isinstance(epoch_id, str) or not SESSION_ID_RE.match(epoch_id):
            raise ValueError(f"epoch_id '{epoch_id}' invalid (must match {SESSION_ID_RE.pattern})")
        rotated = epoch_id != data.get("epoch_id")
    data["epoch_id"] = epoch_id
    if rotated or "epoch_started_at" not in data:
        import time

        data["epoch_started_at"] = int(time.time())
    if "attended_zones" not in data:
        data["attended_zones"] = []
    _atomic_write(workspace, data)
    return epoch_id


def _is_stale(started_at: Optional[int]) -> bool:
    if not started_at:
        return True
    import time

    return (time.time() - started_at) > _EPOCH_TTL_SECONDS


def register_attendance(
    workspace: Path,
    zone: str,
    answer: str,
    expected: str,
    epoch_id: Optional[str] = None,
) -> Tuple[bool, str]:
    """Record attendance for `zone` only when the agent's answer matches the challenge.

    Returns (ok, epoch_id). The record is written solely on a correct answer (never on a
    bare visit) so the session list cannot degrade into a meaningless access log.
    """
    rel = _safe_rel(workspace, zone)
    epoch = ensure_epoch(workspace, epoch_id)
    ok = (answer == expected)
    if ok:
        data = _read(workspace)
        zones: List[dict] = data.setdefault("attended_zones", [])
        entry = {"zone": rel, "epoch": epoch}
        if entry not in zones:
            zones.append(entry)
            _atomic_write(workspace, data)
    return ok, epoch


def is_attended(workspace: Path, zone: str, epoch_id: Optional[str] = None) -> bool:
    data = _read(workspace)
    epoch = epoch_id or data.get("epoch_id")
    if not epoch:
        return False
    return any(
        z.get("zone") == zone and z.get("epoch") == epoch
        for z in data.get("attended_zones", [])
    )


def attended_zones(workspace: Path) -> List[str]:
    data = _read(workspace)
    epoch = data.get("epoch_id")
    if not epoch:
        return []
    return [z["zone"] for z in data.get("attended_zones", []) if z.get("epoch") == epoch]


def reset_session(workspace: Path) -> None:
    """`k3dge end` / timeout: drop attended_zones and rotate the epoch."""
    p = session_path(workspace)
    if p.is_file():
        try:
            p.unlink()
        except OSError:
            pass
