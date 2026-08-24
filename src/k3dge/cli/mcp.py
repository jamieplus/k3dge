"""MCP injection surface for foreign agent harnesses (DSH, Codex, Claude Code, OpenCode).

Zero-drift: those runtimes must not reimplement the gate; they call this stdio server.
Native humans/CI use ``k3dge.cli.main``, not this module. See ADR 0006.
"""

from __future__ import annotations

import json
from typing import Optional

try:
    from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]
except ImportError as _mcp_exc:  # pragma: no cover
    FastMCP = None  # type: ignore[assignment]
    _mcp_import_error = _mcp_exc
else:
    _mcp_import_error = None

from k3dge.cli.main import _find_workspace, _to_json
from k3dge.engine import contract, milestone
from k3dge.engine.contract import _ExtractError
from k3dge.engine.evaluator import ConsistencyEngine
from k3dge.engine.manifest import Manifest
from k3dge.engine.models import GateReport


def _err(code: str, message: str, path: Optional[str] = None) -> str:
    payload = {"ok": False, "error": code, "message": message}
    if path is not None:
        payload["path"] = path
    return json.dumps(payload, indent=2, ensure_ascii=False)

if FastMCP is not None:
    mcp = FastMCP("k3dge-governance-bridge")
else:  # pragma: no cover

    def _identity(fn):  # type: ignore[no-redef]
        return fn

    class _DummyMCP:  # type: ignore[no-redef]
        def resource(self, *_a, **_kw):  # type: ignore[no-untyped-def]
            return _identity

        def tool(self, *_a, **_kw):  # type: ignore[no-untyped-def]
            return lambda fn: fn

        def prompt(self, *_a, **_kw):  # type: ignore[no-untyped-def]
            return lambda fn: fn

        def run(self, *_a, **_kw):  # type: ignore[no-untyped-def]
            raise RuntimeError("mcp package not installed; install with: pip install 'k3dge[mcp]'")

    mcp = _DummyMCP()  # type: ignore[assignment]


@mcp.resource("spec://manifest")
def get_manifest_resource(workspace_path: Optional[str] = None) -> str:
    """Read .agent/manifest.json ground truth from workspace."""
    ws = _find_workspace(workspace_path=workspace_path)
    manifest_path = ws / ".agent" / "manifest.json"
    if not manifest_path.is_file():
        return _err("ManifestNotFound", "manifest.json not found", path=str(manifest_path))
    try:
        return manifest_path.read_text(encoding="utf-8")
    except Exception as exc:
        return _err("ManifestReadError", str(exc), path=str(manifest_path))


@mcp.resource("spec://domain/{domain}")
def get_domain_spec_resource(domain: str, workspace_path: Optional[str] = None) -> str:
    """Read docs/specs/<domain>/spec.md ground truth contract."""
    ws = _find_workspace(workspace_path=workspace_path)
    manifest = Manifest.load(ws)
    spec_rel = manifest.spec_path(domain)
    if not spec_rel:
        return _err("DomainNotRegistered", f"Domain '{domain}' not registered in .agent/manifest.json")
    spec_path = ws / spec_rel
    if not spec_path.is_file():
        return _err("SpecMissing", f"Spec file '{spec_rel}' missing on disk.", path=spec_rel)
    try:
        return spec_path.read_text(encoding="utf-8")
    except Exception as exc:
        return _err("SpecReadError", str(exc), path=spec_rel)


@mcp.tool()
def k3dge_check(
    workspace_path: Optional[str] = None,
    with_tests: bool = False,
    force_full: bool = False,
) -> str:
    """Run k3dge consistency gate directly via ConsistencyEngine."""
    ws = _find_workspace(workspace_path=workspace_path)
    report: GateReport = ConsistencyEngine(ws).evaluate(run_tests=with_tests, force_full=force_full)
    payload = _to_json(report)
    payload["ok"] = report.passed
    payload["render_output"] = report.render()
    payload["force_full"] = force_full
    return json.dumps(payload, indent=2, ensure_ascii=False)


@mcp.tool()
def k3dge_verify_domain_contract(domain: str, workspace_path: Optional[str] = None) -> str:
    """Verify single domain AST interface against spec using k3dge contract engine."""
    ws = _find_workspace(workspace_path=workspace_path)
    manifest = Manifest.load(ws)
    src_rel = manifest.src_path(domain)
    spec_rel = manifest.spec_path(domain)

    if not src_rel or not spec_rel:
        return _err("DomainPathIncomplete", f"Domain '{domain}' path incomplete in manifest.")

    src_dir = ws / src_rel
    spec_path = ws / spec_rel
    if not spec_path.is_file():
        return _err("SpecMissing", f"Spec file '{spec_rel}' not found.", path=spec_rel)

    spec_content = spec_path.read_text(encoding="utf-8")
    try:
        ok, expected_hash, actual_hash = contract.verify_contract(src_dir, spec_content, manifest, ws)
        current_iface = contract.collect_domain_interface(src_dir, manifest, ws)
    except _ExtractError as exc:
        return _err("ContractExtractFailed", str(exc))

    return json.dumps(
        {
            "domain": domain,
            "ok": ok,
            "expected_hash": expected_hash,
            "actual_hash": actual_hash,
            "current_interface": current_iface,
            "remediation": "Run 'k3dge sync' if public interface deliberately changed." if not ok else None,
        },
        indent=2,
        ensure_ascii=False,
    )


@mcp.tool()
def k3dge_milestone_control(
    action: str,
    milestone_id: str,
    workspace_path: Optional[str] = None,
) -> str:
    """Control milestone state machine: status, align (full-matrix regression), seal (atomic compaction)."""
    ws = _find_workspace(workspace_path=workspace_path)
    act = action.lower().strip()

    if act == "status":
        tasks = milestone.scan_milestone_tasks(ws, milestone_id)
        done_cnt = sum(1 for t in tasks if t.status == "done")
        return json.dumps(
            {
                "milestone_id": milestone_id,
                "total_tasks": len(tasks),
                "done_tasks": done_cnt,
                "pending_tasks": len(tasks) - done_cnt,
                "tasks": [{"slug": t.slug, "status": t.status, "path": str(t.path.relative_to(ws))} for t in tasks],
            },
            indent=2,
            ensure_ascii=False,
        )

    if act == "align":
        ok, msg, tasks = milestone.run_milestone_alignment(ws, milestone_id)
        return json.dumps(
            {
                "milestone_id": milestone_id,
                "aligned": ok,
                "message": msg,
                "task_count": len(tasks),
            },
            indent=2,
            ensure_ascii=False,
        )

    if act == "seal":
        ok, msg = milestone.seal_milestone(ws, milestone_id)
        return json.dumps(
            {
                "milestone_id": milestone_id,
                "sealed": ok,
                "message": msg,
            },
            indent=2,
            ensure_ascii=False,
        )

    return _err("InvalidAction", f"Invalid action '{action}'. Choose from: status, align, seal.")


@mcp.prompt()
def k3dge_5pass_audit_prompt(pass_number: int, target_scope: str, context_snippet: str) -> str:
    """Pointer to the independent audit harness. Lenses do not live in k3dge."""
    return (
        "Audit protocol is NOT part of k3dge. Read sibling k3dit docs/guides/protocol.md "
        f"and execute only Pass {pass_number}. Scope: {target_scope}.\n\n"
        f"```\n{context_snippet}\n```\n"
    )


if __name__ == "__main__":
    mcp.run()
