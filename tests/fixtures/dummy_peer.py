"""Dummy peer — 与真实 peer 同契约（`docs/protocols/peer_contract.md`），canned 工件。

桩子先行的锚：骨架链（submit → 协议外等待 → collect → 验壳 → 落盘 → 数计数）
在没有任何真实 harness 时必须可跑、可测。真实 peer 在各自仓内换实现，契约不变。

行为（全部由环境/入参决定，无隐藏状态外溢）：
- `dummy_submit`  → {ok, kind:"job", payload:{job_id}}（≤ 即时）
- `dummy_collect` → {ok, kind:"report", payload:{report_markdown}} 或 NOT_FOUND
- 报告里「待修」行数由环境变量 `DUMMY_PENDING`（默认 0）控制 —— 用来测开环/闭环两态。
"""
from __future__ import annotations

import datetime
import json
import os
import uuid

try:
    from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    try:
        from mcp.server import MCPServer as FastMCP  # type: ignore[assignment]
    except ImportError:
        FastMCP = None  # type: ignore[assignment]

if FastMCP is None:  # pragma: no cover
    raise SystemExit("mcp SDK not importable; install k3dge[mcp]")

mcp = FastMCP("dummy")

import tempfile as _tempfile
from pathlib import Path as _Path

_STATE_FILE = _Path(_tempfile.gettempdir()) / "k3dge_dummy_peer_jobs.json"


def _load_jobs() -> dict:
    try:
        return _json_loads(_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_jobs(jobs: dict) -> None:
    _STATE_FILE.write_text(_json_dumps(jobs, ensure_ascii=False), encoding="utf-8")


_json_loads = json.loads
_json_dumps = json.dumps
_HEADER = "| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |"
_SEP = "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


@mcp.tool()
def dummy_submit(bundle: str = "", bundle_hash: str = "", scope: str = "", milestone_id: str = "") -> str:
    """Contract §1: validate + enqueue only; the wait lives outside the protocol."""
    if bundle_hash and not bundle_hash.startswith("sha256:"):
        return json.dumps(
            {"ok": False, "error": "BAD_BUNDLE", "message": f"bundle_hash must be sha256:… got {bundle_hash!r}"},
            ensure_ascii=False,
        )
    job_id = uuid.uuid4().hex[:12]
    jobs = _load_jobs()
    jobs[job_id] = {"baseline": bundle_hash, "scope": scope, "milestone_id": milestone_id}
    _save_jobs(jobs)
    return json.dumps({"ok": True, "kind": "job", "payload": {"job_id": job_id}}, ensure_ascii=False)


@mcp.tool()
def dummy_collect(job_id: str) -> str:
    """Contract §1: idempotent collect; PENDING/NOT_FOUND are first-class errors."""
    job = _load_jobs().get(job_id)
    if job is None:
        return json.dumps(
            {"ok": False, "error": "NOT_FOUND", "message": f"no such job: {job_id!r}"},
            ensure_ascii=False,
        )
    pending = int(os.environ.get("DUMMY_PENDING", "0"))
    today = datetime.date.today().isoformat()
    ms = job.get("milestone_id") or "M0"
    rows = []
    for i in range(pending):
        rows.append(
            f"| D{i + 1} | {today} | 中 | P1 | 缺陷 | dummy finding {i + 1} | src/x.py:{i + 1} | 待修 | 转 task | 待补 | 待复审 |  |"
        )
    report_md = (
        f"# 审计：{job.get('scope') or 'target'}（milestone {ms}）\n\n"
        f"- **基线**: {job.get('baseline') or '-'}\n"
        f"- **审计人**: dummy+test-seat\n"
        f"- **透镜来源**: dummy（peer contract 桩）\n"
        f"- **范围**: {job.get('scope') or '-'}\n\n"
        f"{_HEADER}\n{_SEP}\n" + ("\n".join(rows) + "\n" if rows else "")
    )
    return json.dumps(
        {
            "ok": True,
            "kind": "report",
            "payload": {"report_markdown": report_md},
            "provenance": {
                "seat": "dummy+test-seat",
                "generated_at": _now(),
                "baseline": job.get("baseline") or "",
            },
        },
        ensure_ascii=False,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
