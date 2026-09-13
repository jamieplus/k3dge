"""Shared workspace-status synthesis for CLI ``status`` and MCP ``k3dge_status``.

Both surfaces call :func:`workspace_status` so the MCP tool never re-scans tasks or
re-filters drift (ADR-0001 decision 6 / ADR-0008). One implementation, isomorphic output.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

from k3dge.engine.evaluator import ConsistencyEngine
from k3dge.engine.manifest import Manifest, ManifestError
from k3dge.engine.milestone import _is_doc_aux, parse_frontmatter



def cache_observability(workspace: Path) -> Optional[Dict[str, Any]]:
    """service 角色遥测，**只供展示**（peer contract §0：永不进判定链）。

    门 = 工作区存在 `.k3che/`（廉价存在探测，不解析其内容格式）；数据一律走
    角色自己的 stats 工具信封。skip/失败 ⇒ None，status 照常绿。
    """
    if not (workspace / ".k3che").is_dir():
        return None
    from k3dge.engine.pipeline_runner import run_action

    try:
        res = run_action(workspace, "cache.stats")
    except Exception:  # pragma: no cover - 观测件绝不拖垮 status
        return None
    if not res.ok or res.provider != "mcp":
        return None
    try:
        env = json.loads(res.payload or "")
    except ValueError:
        return None
    if not isinstance(env, dict) or not env.get("ok"):
        return None
    return {k: env[k] for k in ("total", "hits", "hit_rate", "indexed", "persisted") if k in env}
def lifecycle_next(workspace: Path) -> Any:
    """The single NextStep for this workspace, or None (ADR-0008 routing source).

    Lives here — not in `cli/main.py` — because `workspace_status` must put the same
    value on both exits: human `[NEXT]`, ``status --json`` `.next`, and MCP
    `k3dge_status`. Precedence stays pending_findings > ratchet_open > seal_ready > audit_suggested.
    """
    from typing import Optional

    from k3dge.engine import nextstep
    from k3dge.engine.audit_flow import open_ratchet_jobs
    from k3dge.engine.audit_trigger import audit_closed, compute_audit_suggestion
    from k3dge.engine.milestone import get_current_milestone, scan_pending_findings

    try:
        mid = get_current_milestone(workspace)
        count, samples = scan_pending_findings(workspace)
        if count > 0:
            return nextstep.NextStep.from_state(
                "pending_findings", mid, pending=count, reasons=[f"标记: {s}" for s in samples[:5]]
            )
        open_jobs = open_ratchet_jobs(workspace)   # G2：在办单压过封板提示（单没关别急着封）
        if open_jobs:
            j = open_jobs[-1]
            return nextstep.NextStep.from_state(
                "ratchet_open", j.get("milestone_id") or mid,
                reasons=[f"job {x.get('job_id')}（{x.get('state')}）" for x in open_jobs[:3]],
            )
        if audit_closed(workspace, mid):
            return nextstep.NextStep.from_state("seal_ready", mid)
        suggested, reasons = compute_audit_suggestion(workspace)
        if suggested:
            return nextstep.NextStep.from_state("audit_suggested", mid, reasons=reasons)
        return None
    except Exception:  # pragma: no cover - routing must never break status
        return None


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
            if _is_doc_aux(p.name):  # single source: engine._DOC_AUX_NAMES (was a 2nd copy)
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

    from k3dge.engine import state_machine, task_dag

    return {
        "domains": sorted(manifest.domains),
        "gate_passed": report.passed,
        "modified_domains": list(report.modified_domains),
        "drift": drift,
        "pipeline": pipeline,
        "unfinished_tasks": unfinished,
        "task_dag": task_dag.summary(workspace),
        "state_machine": state_machine.summary(),
        "next": (ns.render_mcp() if (ns := lifecycle_next(workspace)) is not None else None),
        "cache": cache_observability(workspace),
    }
