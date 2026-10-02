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
import os
from pathlib import Path
from typing import Any

_EVENTS_REL = ".k3dge/events.jsonl"
_MAX_LINES = 1000
_KEEP_LINES = 800


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _acquire_lock(path: Path) -> "int | None":
    """Best-effort exclusive lock on a sidecar `.lock` (returns fd, or None).

    `emit()` runs in several OS processes against the same workspace (git hooks,
    CLI, MCP server). Without serialising append+rotate, a rotator's rename can
    unlink an inode another writer holds — that writer's events vanish silently
    (ocr2-251). No fcntl (Windows) ⇒ skip locking rather than fail.
    """
    try:
        import fcntl
    except ImportError:  # pragma: no cover - non-POSIX
        return None
    try:
        fd = os.open(str(path.with_name(path.name + ".lock")), os.O_CREAT | os.O_RDWR, 0o644)
        fcntl.flock(fd, fcntl.LOCK_EX)
        return fd
    except OSError:
        return None


def emit(workspace: Path, evt: str, **data: Any) -> None:
    """Append one event line. Never raises."""
    lock_fd = None
    try:
        path = workspace / _EVENTS_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_fd = _acquire_lock(path)     # 串行化 append+rotate（ocr2-251）
        entry: dict[str, Any] = dict(data)
        # 调用方经 `**data` 传进来的 `ts`/`evt` 不得覆盖引擎生成的权威字段
        #（否则事件时间线/类型被调用方改写还无人能辨，ocr2-249）。
        entry["ts"] = _now()
        entry["evt"] = evt
        # `default=str`：调用方随时可能传 Path/datetime/set（通用 **data 接口）⇒ 别让 json.dumps 抛（ocr-074）。
        line = json.dumps(entry, ensure_ascii=False, default=str)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        _rotate(path)
    except Exception as exc:      # 纯诊断日志：任何失败都不得阻塞主命令路径（docstring 承诺，ocr-074）
        # 吞可以，但不得无声：整条事件流消失还 exit 0，消费者会把"没事件"读成"没发生"（ocr2-250）。
        import sys as _sys

        print(f"[events] WARN: 写入失败（{type(exc).__name__}: {exc}）⇒ 本条事件丢失", file=_sys.stderr)
    finally:
        if lock_fd is not None:
            try:
                os.close(lock_fd)          # 关闭即释放 flock
            except OSError:
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
        # 临时名**按进程**唯一：固定的 `events.jsonl.tmp` 会被并发 rotator 互相覆盖，
        # 各自 rename ⇒ 中间 append 的事件丢失（ocr2-251）。
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("\n".join(kept) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except OSError:
        pass



def read_events(workspace: Path, last: int = 20) -> list[dict[str, Any]]:
    """Read the last N events (newest last). Returns [] on any error."""
    try:
        path = workspace / _EVENTS_REL
        if not path.is_file():
            return []
        # 非法 UTF-8（并发 rotate 写坏/截断）抛 UnicodeDecodeError（ValueError 子类），不在
        # `except OSError` 里 ⇒ 会冒到 CLI 展示路径，违背 "Returns [] on any error"（ocr-243）。
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        if last <= 0:
            # `lines[-0:]` 会返回**全部**事件、`last<0` 返回更早的一批 ⇒ 与"取最后 N 条"相反（ocr-242）。
            return []
        entries: list[dict[str, Any]] = []
        for ln in lines[-last:]:
            try:
                obj = json.loads(ln)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(obj, dict):
                entries.append(obj)
        return entries
    except OSError:
        return []
