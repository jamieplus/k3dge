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
        # `default=str`：调用方随时可能传 Path/datetime/set（通用 **data 接口）⇒ 别让 json.dumps 抛（ocr-074）。
        line = json.dumps(entry, ensure_ascii=False, default=str)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        _rotate(path)
    except Exception:      # 纯诊断日志：任何失败都不得阻塞主命令路径（docstring 承诺，ocr-074）
        pass


def _rotate(path: Path) -> None:
    """If file exceeds _MAX_LINES, keep only the last _KEEP_LINES."""
    try:
        if path.stat().st_size < _MAX_LINES * 20:      # 廉价上界：远不到阈值就不读全文件（ocr-075）
            return
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        if len(lines) <= _MAX_LINES:
            return
        kept = lines[-_KEEP_LINES:]
        # 原子替换：截断与写完之间被杀（hook 被 Ctrl-C / 超时）不再清空整份日志（ocr-075）。
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text("\n".join(kept) + "\n", encoding="utf-8")
        tmp.replace(path)
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
