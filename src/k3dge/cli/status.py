"""Shared workspace-status synthesis for CLI ``status`` and MCP ``k3dge_status``.

Both surfaces call :func:`workspace_status` so the MCP tool never re-scans tasks or
re-filters drift (ADR-0001 decision 6 / ADR-0008). One implementation, isomorphic output.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict

from k3dge.engine.evaluator import ConsistencyEngine
from k3dge.engine.manifest import Manifest, ManifestError
from k3dge.engine.milestone import parse_frontmatter


def workspace_status(workspace: Path) -> Dict[str, Any]:
    """Synthesize current workspace state: domains / drift / pipeline / unfinished tasks.

    Returns a dict isomorphic to ``k3dge status --json``. On a missing or invalid manifest
    it returns an error-shaped dict (``{"ok": False, ...}``) so both the CLI and the MCP tool
    can render it uniformly without re-implementing the scan.
    """
    try:
        manifest = Manifest.load(workspace)
    except ManifestError as exc:
        return {"ok": False, "error": "ManifestInvalid", "message": str(exc)}

    report = ConsistencyEngine(workspace).evaluate()
    drift = [
        {"domain": v.domain, "symbol_diff": (v.detail or {}).get("symbol_diff")}
        for v in report.violations
        if v.rule_id == "CONTRACT_DRIFT"
    ]
    pipeline_path = workspace / ".agent" / "pipeline.toml"
    pipeline = {"configured": pipeline_path.exists(), "issues": []}
    if pipeline_path.exists():
        try:
            from k3dge.engine.pipeline_schema import validate_pipeline_config

            pipeline["issues"] = [f"{c}: {m}" for c, m in validate_pipeline_config(workspace)]
        except Exception as exc:  # pragma: no cover
            pipeline["issues"].append(f"PIPELINE_SCHEMA_INVALID: {exc}")

    tasks_dir = workspace / "docs" / "tasks"
    unfinished = []
    if tasks_dir.is_dir():
        for p in sorted(tasks_dir.glob("*.md")):
            if p.name in ("README.md", "_template.md"):
                continue
            try:
                txt = p.read_text(encoding="utf-8")
            except OSError:
                continue
            fm = parse_frontmatter(txt) or {}
            m = re.search(r"-\s+\*\*Status\*\*:\s*([\w-]+)", txt)
            status = (fm.get("status") or (m.group(1).lower() if m else "")).strip()
            if status != "done":
                tm = re.search(r"#\s*(.+)", txt)
                unfinished.append(
                    {
                        "task": p.stem,
                        "title": (tm.group(1).strip() if tm else p.stem),
                        "status": status,
                    }
                )

    return {
        "domains": sorted(manifest.domains),
        "gate_passed": report.passed,
        "modified_domains": list(report.modified_domains),
        "drift": drift,
        "pipeline": pipeline,
        "unfinished_tasks": unfinished,
    }
