"""Append-only event log for k3dge operations.

`.k3dge/events.jsonl` records state transitions (gate results, audit jobs,
seal, task completion, next-step, downgrades). Fire-and-forget: emit failures
never block the main command path.

Design:
- Single writer (`emit()`), called from engine/CLI modules.
- Rotate at 1000 lines (keep last 800).
- No replacement of existing channels (audit_jobs.json, logs/); this is
  a parallel fact source for debug / future dashboard / CI integration.
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

_EVENTS_REL = ".k3dge/events.jsonl"
_MAX_LINES = 1000
_KEEP_LINES = 800


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def emit(workspace: Path, evt: str, **data: Any) -> None:
    """Append one event line. Never raises."""
    try:
        path = workspace / _EVENTS_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        entry: dict[str, Any] = {"ts": _now(), "evt": evt}
        entry.update(data)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        _rotate(path)
    except OSError:
        pass


def _rotate(path: Path) -> None:
    """If file exceeds _MAX_LINES, keep only the last _KEEP_LINES."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) > _MAX_LINES:
            kept = lines[-_KEEP_LINES:]
            path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    except OSError:
        pass


def read_events(workspace: Path, last: int = 20) -> list[dict[str, Any]]:
    """Read the last N events (newest last). Returns [] on any error."""
    try:
        path = workspace / _EVENTS_REL
        if not path.is_file():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()
        entries: list[dict[str, Any]] = []
        for ln in lines[-last:]:
            try:
                entries.append(json.loads(ln))
            except (json.JSONDecodeError, ValueError):
                continue
        return entries
    except OSError:
        return []
