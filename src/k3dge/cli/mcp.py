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
    try:
        manifest = Manifest.load(ws)
    except Exception as exc:
        return _err("ManifestInvalid", f"manifest load failed: {exc}", path=str(ws / ".agent" / "manifest.json"))
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
    try:
        manifest = Manifest.load(ws)
    except Exception as exc:
        return _err("ManifestInvalid", f"manifest load failed: {exc}", path=str(ws / ".agent" / "manifest.json"))
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
        current_iface = contract.collect_domain_interface(src_dir, manifest, ws)
    except _ExtractError as exc:
        return _err("ContractExtractFailed", str(exc))
    actual_hash = contract.compute_hash(current_iface)
    from k3dge.engine import spec_schema

    expected_hash = spec_schema.extract_contract_hash(spec_content)
    ok = expected_hash is not None and expected_hash == actual_hash

    return json.dumps(
        {
            "domain": domain,
            "ok": ok,
            "expected_hash": expected_hash,
            "actual_hash": actual_hash,
            "current_interface": current_iface,
            "remediation": "Run k3dge_sync (or CLI 'k3dge sync') if public interface deliberately changed." if not ok else None,
        },
        indent=2,
        ensure_ascii=False,
    )


@mcp.tool()
def k3dge_sync(
    domains: Optional[list[str]] = None,
    workspace_path: Optional[str] = None,
) -> str:
    """Regenerate spec interface blocks and contract hashes. Same as CLI k3dge sync."""
    from k3dge.sync.generator import sync_all

    ws = _find_workspace(workspace_path=workspace_path)
    if isinstance(domains, str):
        domains = [domains]
    try:
        changed, docs_updated = sync_all(ws, domains=domains)
    except Exception as exc:
        return _err("SyncFailed", str(exc))
    return json.dumps(
        {
            "ok": True,
            "changed": list(changed),
            "docs_updated": bool(docs_updated),
            "up_to_date": not changed and not docs_updated,
        },
        indent=2,
        ensure_ascii=False,
    )


@mcp.tool()
def k3dge_version(
    action: str = "show",
    part: str = "patch",
    set_version: Optional[str] = None,
    message: Optional[str] = None,
    workspace_path: Optional[str] = None,
) -> str:
    """Show or bump project version (same as CLI k3dge version)."""
    from k3dge.engine.version import append_changelog, bump_version, get_version

    ws = _find_workspace(workspace_path=workspace_path)
    act = action.lower().strip()
    if act == "show":
        v = get_version(ws)
        return json.dumps({"ok": True, "version": v}, indent=2, ensure_ascii=False)
    if act == "bump":
        try:
            new_v = bump_version(ws, part=part, set_version=set_version)
        except Exception as exc:
            return _err("VersionBumpFailed", str(exc))
        notes = message or f"Bump version to {new_v}."
        try:
            append_changelog(ws, new_v, notes=notes)
        except Exception as exc:
            return json.dumps(
                {"ok": True, "version": new_v, "changelog_failed": str(exc)},
                indent=2,
                ensure_ascii=False,
            )
        return json.dumps({"ok": True, "version": new_v}, indent=2, ensure_ascii=False)
    return _err("InvalidAction", f"Invalid action '{action}'. Choose from: show, bump.")


@mcp.tool()
def k3dge_task_create(
    title: str,
    typ: str = "fix",
    slug: Optional[str] = None,
    milestone_id: Optional[str] = None,
    priority: str = "P2",
    workspace_path: Optional[str] = None,
) -> str:
    """Create a living docs/tasks/ file. Same as CLI k3dge task create."""
    ws = _find_workspace(workspace_path=workspace_path)
    ok, msg, path = milestone.create_task(
        ws, title, typ=typ, slug=slug, milestone=milestone_id, priority=priority
    )
    rel = str(path.relative_to(ws)).replace("\\", "/") if path else None
    return json.dumps({"ok": ok, "message": msg, "path": rel}, indent=2, ensure_ascii=False)


@mcp.tool()
def k3dge_task_done(path: str, workspace_path: Optional[str] = None) -> str:
    """Mark one task done. Prefer the path from k3dge_task_list."""
    ws = _find_workspace(workspace_path=workspace_path)
    ok, msg, done_path = milestone.mark_task_done(ws, path)
    rel = str(done_path.relative_to(ws)).replace("\\", "/") if done_path else None
    return json.dumps({"ok": ok, "message": msg, "path": rel}, indent=2, ensure_ascii=False)


@mcp.tool()
def k3dge_task_list(
    milestone_id: Optional[str] = None,
    status: Optional[str] = None,
    workspace_path: Optional[str] = None,
) -> str:
    """Index living docs/tasks/*.md (not archive). Returns title/status/milestone/priority, not bodies."""
    ws = _find_workspace(workspace_path=workspace_path)
    rows = milestone.list_tasks(ws, milestone_id=milestone_id, status=status)
    return json.dumps(
        {
            "ok": True,
            "count": len(rows),
            "tasks": [
                {
                    "path": str(t.path.relative_to(ws)).replace("\\", "/"),
                    "title": t.title,
                    "status": t.status,
                    "milestone": t.milestone,
                    "priority": t.priority,
                }
                for t in rows
            ],
        },
        indent=2,
        ensure_ascii=False,
    )


@mcp.resource("protocol://{task_type}")
def get_protocol_resource(task_type: str, workspace_path: Optional[str] = None) -> str:
    """Read the protocol markdown a worker must follow for a given task_type.

    Deterministic operation-spec injection: the host harness pulls this into a
    fresh, bounded-attention session before acting. See ADR 0012.
    """
    from k3dge.engine.protocol import ProtocolResolutionError, ProtocolResolver

    ws = _find_workspace(workspace_path=workspace_path)
    try:
        ref = ProtocolResolver(ws).resolve(task_type)
    except ProtocolResolutionError as exc:
        return _err("ProtocolNotFound", str(exc))
    if not ref.exists:
        return _err("ProtocolMissing", f"protocol file not found: {ref.rel}", path=ref.rel)
    try:
        return ref.path.read_text(encoding="utf-8")
    except Exception as exc:
        return _err("ProtocolReadError", str(exc), path=ref.rel)


@mcp.tool()
def k3dge_protocol_resolve(
    task_type: str = "",
    path: Optional[str] = None,
    workspace_path: Optional[str] = None,
) -> str:
    """Resolve a protocol to inject before an agent acts.

    Deterministic call for an upstream harness:
    - `path` (preferred): the file about to be touched; the most-specific glob in
      `.agent/protocols.toml [paths]` decides the protocol. No match => base spec.
    - `task_type`: explicit protocol key (fallback when no path routing applies).
    Returns the operation spec markdown so attention is bounded by protocol, not
    by conversational history. Use this instead of the agent inventing rules.
    """
    from k3dge.engine.protocol import ProtocolResolutionError, ProtocolResolver

    ws = _find_workspace(workspace_path=workspace_path)
    resolver = ProtocolResolver(ws)
    ref = None
    if path:
        ref = resolver.resolve_by_path(path)
        if ref is None:
            return json.dumps(
                {
                    "ok": True,
                    "task_type": None,
                    "protocol_path": None,
                    "exists": False,
                    "content": "",
                    "note": f"no protocol mapped for path '{path}'; proceed under base spec",
                },
                indent=2,
                ensure_ascii=False,
            )
    else:
        try:
            ref = resolver.resolve(task_type)
        except ProtocolResolutionError as exc:
            return _err("ProtocolNotFound", str(exc))
    content = ref.path.read_text(encoding="utf-8") if ref.exists else ""
    return json.dumps(
        {
            "ok": True,
            "task_type": ref.task_type,
            "protocol_path": ref.rel,
            "exists": ref.exists,
            "content": content,
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
        payload = {
            "milestone_id": milestone_id,
            "aligned": ok,
            "message": msg,
            "task_count": len(tasks),
        }
        if ok:
            payload["checkpoint"] = {
                "type": "HUMAN_CHECKPOINT",
                "question": f"Milestone {milestone_id} 全绿，是否执行 5-Pass 专项审计？",
                "options": ["y", "N"],
                "default": "N",
                "timeout_seconds": 60,
            }
        return json.dumps(payload, indent=2, ensure_ascii=False)

    if act == "seal":
        ok, msg = milestone.seal_milestone(ws, milestone_id)
        if not ok:
            return json.dumps(
                {
                    "milestone_id": milestone_id,
                    "sealed": False,
                    "message": msg,
                },
                indent=2,
                ensure_ascii=False,
            )
        try:
            from k3dge.engine.version import append_changelog, bump_version, consume_unreleased, get_version

            prev = get_version(ws)
            new_v = bump_version(ws, part="patch")
            body = consume_unreleased(ws)
            notes = body if body else f"Seal milestone {milestone_id}."
            append_changelog(ws, new_v, notes=notes)
            return json.dumps(
                {
                    "milestone_id": milestone_id,
                    "sealed": True,
                    "message": msg,
                    "version": new_v,
                    "previous_version": prev,
                },
                indent=2,
                ensure_ascii=False,
            )
        except Exception as exc:
            return json.dumps(
                {
                    "milestone_id": milestone_id,
                    "sealed": True,
                    "message": msg,
                    "version_bump_failed": str(exc),
                },
                indent=2,
                ensure_ascii=False,
            )

    return _err("InvalidAction", f"Invalid action '{action}'. Choose from: status, align, seal.")


@mcp.tool()
def k3dge_protocol_challenge(
    path: Optional[str] = None,
    task_type: str = "",
    task_id: str = "",
    workspace_path: Optional[str] = None,
) -> str:
    """Compute the dynamic load-proof challenge for a workshop entry.

    Returns `sha256(normalize(protocol_text) + task_id)[:12]`. The host harness
    issues this right after injecting the protocol and before letting the agent
    act; the agent must echo it back. A correct reply proves the protocol was
    loaded into the live session (attention reset), not merely grepped. None when
    no protocol maps (base spec, no helmet required). See ADR 0012.
    """
    from k3dge.engine.protocol import ProtocolResolver

    ws = _find_workspace(workspace_path=workspace_path)
    chal = ProtocolResolver(ws).challenge(target=path, task_type=task_type, task_id=task_id or "")
    if chal is None:
        return json.dumps(
            {
                "ok": True,
                "required": False,
                "challenge": None,
                "note": "no protocol mapped; proceed under base spec",
            },
            indent=2,
            ensure_ascii=False,
        )
    return json.dumps(
        {"ok": True, "required": True, "challenge": chal},
        indent=2,
        ensure_ascii=False,
    )

    if act == "align":
        ok, msg, tasks = milestone.run_milestone_alignment(ws, milestone_id)
        payload = {
            "milestone_id": milestone_id,
            "aligned": ok,
            "message": msg,
            "task_count": len(tasks),
        }
        if ok:
            payload["checkpoint"] = {
                "type": "HUMAN_CHECKPOINT",
                "question": f"Milestone {milestone_id} 全绿，是否执行 5-Pass 专项审计？",
                "options": ["y", "N"],
                "default": "N",
                "timeout_seconds": 60,
            }
        return json.dumps(payload, indent=2, ensure_ascii=False)

    if act == "seal":
        ok, msg = milestone.seal_milestone(ws, milestone_id)
        if not ok:
            return json.dumps(
                {
                    "milestone_id": milestone_id,
                    "sealed": False,
                    "message": msg,
                },
                indent=2,
                ensure_ascii=False,
            )
        # Auto-bump patch version to keep CLI and MCP seal semantics identical (U-04); bump failure does not rollback seal (see ADR 0017)
        # Both CLI and MCP now use consume_unreleased for identical changelog body (P3-01)
        try:
            from k3dge.engine.version import append_changelog, bump_version, consume_unreleased, get_version

            prev = get_version(ws)
            new_v = bump_version(ws, part="patch")
            body = consume_unreleased(ws)
            notes = body if body else f"Seal milestone {milestone_id}."
            append_changelog(ws, new_v, notes=notes)
            return json.dumps(
                {
                    "milestone_id": milestone_id,
                    "sealed": True,
                    "message": msg,
                    "version": new_v,
                    "previous_version": prev,
                },
                indent=2,
                ensure_ascii=False,
            )
        except Exception as exc:
            return json.dumps(
                {
                    "milestone_id": milestone_id,
                    "sealed": True,
                    "message": msg,
                    "version_bump_failed": str(exc),
                },
                indent=2,
                ensure_ascii=False,
            )

    return _err("InvalidAction", f"Invalid action '{action}'. Choose from: status, align, seal.")


def _audit_protocol_with_fallback(workspace_path: Optional[str] = None) -> tuple[str, bool, str]:
    """Resolve audit protocol per Rule 07 with fallback detection.

    Returns (protocol_path, used_fallback, reason). Highlights fallback to default.
    Priority: ../k3dit/docs/guides/protocol.md → docs/protocols/audit_default.md (local docs/guides/protocol.md deprecated per Diátaxis)
    Also checks .mcp.json for k3dit harness availability (required for actual k3dit_run_audit call).
    """
    import json

    ws = _find_workspace(workspace_path=workspace_path)
    candidates = [
        (ws.parent / "k3dit" / "docs" / "guides" / "protocol.md", "k3dit"),
        (ws / ".." / "k3dit" / "docs" / "guides" / "protocol.md", "k3dit alt"),
    ]
    fallback = ws / "docs" / "protocols" / "audit_default.md"
    fell_back = True
    reason = "no k3dit protocol found"
    proto = str(fallback.relative_to(ws)) if fallback.is_relative_to(ws) else str(fallback)
    for cand, label in candidates:
        try:
            if cand.is_file():
                proto = str(cand.relative_to(ws)) if cand.is_relative_to(ws) else str(cand)
                fell_back = False
                reason = ""
                break
        except Exception:
            if cand.is_file():
                proto = str(cand)
                fell_back = False
                reason = ""
                break
    # Even if protocol file exists, check MCP harness availability for k3dit_run_audit
    if not fell_back and "k3dit" in proto:
        mcp_path = ws / ".mcp.json"
        has_k3dit = False
        try:
            if mcp_path.is_file():
                data = json.loads(mcp_path.read_text(encoding="utf-8"))
                has_k3dit = isinstance(data, dict) and isinstance(data.get("mcpServers"), dict) and "k3dit" in data["mcpServers"]
        except Exception:
            has_k3dit = False
        if not has_k3dit:
            reason = ".mcp.json missing mcpServers.k3dit (harness not configured), k3dit_run_audit unavailable"
            fell_back = True
            proto = str(fallback.relative_to(ws)) if fallback.is_relative_to(ws) else str(fallback)
    if fell_back and not reason:
        reason = "protocol file not found"
    return (proto, fell_back, reason)


@mcp.prompt()
def k3dge_5pass_audit_prompt(pass_number: int, target_scope: str, context_snippet: str) -> str:
    """Pointer to the independent audit harness. Lenses do not live in k3dge."""
    proto, fell_back, reason = _audit_protocol_with_fallback()
    # Highlighted fallback warning when external harness (k3dit) unavailable
    banner = ""
    if fell_back:
        banner = (
            "!!! \033[1;41m[WARN][HARNESS FALLBACK]\033[0m \033[1;33m"
            f"k3dit audit harness unavailable ({reason}), "
            "falling back to DEFAULT docs/protocols/audit_default.md (manual lens, no k3dit)\033[0m !!!\n"
            "[WARN][HARNESS FALLBACK] k3dit not found → DEFAULT audit_default.md\n"
            f"[WARN] Reason: {reason}\n\n"
        )
    return (
        banner
        + f"Audit protocol is NOT part of k3dge. Read {proto}; "
        + ("(DEFAULT fallback, no k3dit)" if fell_back else "(k3dit lens)")
        + f" Execute only Pass {pass_number}. Scope: {target_scope}.\n\n"
        f"```\n{context_snippet}\n```\n"
    )


@mcp.tool()
def k3dge_protocol_ticket(
    path: Optional[str] = None,
    task_type: str = "",
    task_id: str = "",
    ticket: Optional[object] = None,
    workspace_path: Optional[str] = None,
) -> str:
    """L2 entry-ticket: structured acknowledgment that the agent bound every protocol constraint.

    Without `ticket`: returns the checklist of declared constraints the agent must
    bind to the task (the "what to recite" list). With `ticket` (a JSON object or
    string): validates shape + completeness — every declared constraint must be
    acknowledged. This proves a synthesis step, not mere copying; final deliverable
    adherence is still gated by `k3dge check` (L3). See ADR 0022.
    """
    from k3dge.engine.protocol import ProtocolResolver

    ws = _find_workspace(workspace_path=workspace_path)
    resolver = ProtocolResolver(ws)
    if ticket is None:
        ref = resolver.resolve_by_path(path) if path else (resolver.resolve(task_type) if task_type else None)
        if ref is None:
            return json.dumps(
                {"ok": True, "required": False, "constraints": [], "note": "no protocol mapped; base spec"},
                indent=2,
                ensure_ascii=False,
            )
        constraints = resolver.expected_constraints(target=path, task_type=task_type) or []
        return json.dumps(
            {"ok": True, "required": True, "protocol": ref.task_type, "constraints": constraints},
            indent=2,
            ensure_ascii=False,
        )
    if isinstance(ticket, str):
        try:
            ticket = json.loads(ticket)
        except Exception as exc:
            return _err("TicketParseError", str(exc))
    errs = resolver.validate_ticket(
        target=path, task_type=task_type, ticket=ticket, task_id=task_id or ""
    )
    return json.dumps(
        {"ok": not errs, "errors": errs},
        indent=2,
        ensure_ascii=False,
    )


@mcp.tool()
def k3dge_protocol_verify(
    path: Optional[str] = None,
    task_type: str = "",
    task_id: str = "",
    ticket: Optional[object] = None,
    workspace_path: Optional[str] = None,
) -> str:
    """Soft gate (ADR 0022, revised): advisory L1+L2 verdict, never a hard block.

    Returns `pass` (no protocol / ticket valid) or `advise` (protocol required but
    ticket invalid, with remediation so a cooperating agent self-corrects). The agent
    may still proceed; persistent deviation should be escalated via `k3dge_protocol_report`
    and is ultimately caught by `k3dge check` (L3) where the agent cannot reach it.
    """
    from k3dge.engine.protocol import ProtocolResolver

    ws = _find_workspace(workspace_path=workspace_path)
    resolver = ProtocolResolver(ws)
    if isinstance(ticket, str):
        try:
            ticket = json.loads(ticket)
        except Exception as exc:
            return _err("TicketParseError", str(exc))
    verdict = resolver.verify(target=path, task_type=task_type, ticket=ticket, task_id=task_id or "")
    return json.dumps(verdict, indent=2, ensure_ascii=False)


@mcp.tool()
def k3dge_protocol_report(
    detail: str,
    path: Optional[str] = None,
    task_type: str = "",
    task_id: str = "",
    workspace_path: Optional[str] = None,
) -> str:
    """Escalate a persistent protocol deviation to a human-visible incident note.

    Writes `docs/incidents/INC-YYYYMMDD-protocol-<slug>.md` so a person knows the agent
    ignored the soft gate and proceeded regardless. This is the "report it to a human"
    backstop; it is NOT enforcement. See ADR 0022.
    """
    from k3dge.engine.protocol import write_incident

    if not detail or not detail.strip():
        return _err("MissingDetail", "report requires non-empty detail")
    ws = _find_workspace(workspace_path=workspace_path)
    out = write_incident(ws, path, task_type or None, task_id or "", detail)
    rel = str(out.relative_to(ws)) if out.is_relative_to(ws) else str(out)
    return json.dumps({"ok": True, "incident": rel}, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
