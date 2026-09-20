"""MCP injection surface for foreign agent harnesses (DSH, Codex, Claude Code, OpenCode).

Zero-drift: those runtimes must not reimplement the gate; they call this stdio server.
Native humans/CI use ``k3dge.cli.main``, not this module. See ADR-0006.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

try:
    from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]
except ImportError as _mcp_exc:  # pragma: no cover
    try:
        from mcp.server import MCPServer as FastMCP  # mcp 2.x 移除 fastmcp 后的正主（并列 harness 先例同形）
    except ImportError:
        FastMCP = None  # type: ignore[assignment]
        _mcp_import_error = _mcp_exc
    else:
        _mcp_import_error = None
else:
    _mcp_import_error = None

from k3dge.cli.main import _find_workspace, _to_json
from k3dge.engine import contract
from k3dge.engine.align import run_milestone_alignment
from k3dge.engine.contract import _ExtractError
from k3dge.engine.task_write import _similar_task_hints
from k3dge.engine.milestone_audit import persist_external_audit_report, run_audit_flow
from k3dge.engine.seal_flow import run_seal_flow
from k3dge.engine.task_index import list_tasks, scan_milestone_tasks
from k3dge.engine.task_write import create_task, mark_task_done
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
def get_manifest_resource() -> str:
    """Read .agent/manifest.json ground truth。workspace 取 server CWD（mcp 2.x：无模板 URI 不得带参数）。"""
    return get_manifest_resource_for(_find_workspace(Path.cwd()))


def get_manifest_resource_for(ws: Path) -> str:
    """供测试与内部调用：给定工作区返回 manifest 内容（机验同一行为体）。"""
    manifest_path = ws / ".agent" / "manifest.json"
    if not manifest_path.is_file():
        return _err("ManifestNotFound", "manifest.json not found", path=str(manifest_path))
    try:
        return manifest_path.read_text(encoding="utf-8")
    except Exception as exc:
        return _err("ManifestReadError", str(exc), path=str(manifest_path))


@mcp.resource("spec://domain/{domain}")
def get_domain_spec_resource(domain: str) -> str:
    """Read docs/specs/<domain>/spec.md ground truth contract。workspace 取 server CWD。"""
    return get_domain_spec_resource_for(domain, _find_workspace(Path.cwd()))


def get_domain_spec_resource_for(domain: str, ws: Path) -> str:
    """供测试与内部调用：给定工作区与域返回 spec 正文。"""
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
    from k3dge.cli.status import lifecycle_next

    ns = lifecycle_next(ws)
    payload["next"] = ns.render_mcp() if ns is not None else None
    return json.dumps(payload, indent=2, ensure_ascii=False)


@mcp.tool()
def k3dge_status(workspace_path: Optional[str] = None) -> str:
    """Synthesize current workspace state: domains / drift / pipeline / unfinished tasks.

    Runs ConsistencyEngine.evaluate() — same cost tier as k3dge_check. Shares the single
    workspace_status() implementation with the CLI; never re-scans tasks or re-filters drift.
    Output shape is isomorphic to ``k3dge status --json``.
    """
    from k3dge.cli.status import workspace_status

    ws = _find_workspace(workspace_path=workspace_path)
    status_obj = workspace_status(ws)
    if not status_obj.get("ok", True):
        return _err(status_obj.get("error", "UnknownError"), status_obj.get("message", ""))
    return json.dumps(status_obj, indent=2, ensure_ascii=False)


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
    ok, msg, path = create_task(
        ws, title, typ=typ, slug=slug, milestone=milestone_id, priority=priority
    )
    rel = str(path.relative_to(ws)).replace("\\", "/") if path else None
    similar = []
    if ok and path is not None:
        similar = [
            {"path": p, "title": ttl}
            for p, ttl in _similar_task_hints(ws, title, exclude=path)
        ]
    from k3dge.engine import gate_facts

    return json.dumps(
        {
            "ok": ok,
            "message": msg,
            "path": rel,
            "similar": similar,
            # 给进程的闭集投影：档位由声明面定（observe＝不阻断、不裁决）
            "similar_severity": gate_facts.severity("DUP_CHECK") if similar else None,
        },
        indent=2,
        ensure_ascii=False,
    )


@mcp.tool()
def k3dge_task_done(path: str, workspace_path: Optional[str] = None) -> str:
    """Mark one task done. Prefer the path from k3dge_task_list."""
    ws = _find_workspace(workspace_path=workspace_path)
    ok, msg, done_path = mark_task_done(ws, path)
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
    rows = list_tasks(ws, milestone_id=milestone_id, status=status)
    from k3dge.cli.status import lifecycle_next

    ns = lifecycle_next(ws)
    return json.dumps(
        {
            "ok": True,
            "count": len(rows),
            "next": ns.render_mcp() if ns is not None else None,
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


@mcp.tool()
def k3dge_doc_list(
    typ: Optional[str] = None,
    ident: Optional[str] = None,
    q: Optional[str] = None,
    include_archive: bool = False,
    workspace_path: Optional[str] = None,
) -> str:
    """Thin document catalog (path/id/title/status/tokens). Never returns bodies. Same as CLI k3dge doc list."""
    from k3dge.engine.doc_catalog import list_docs

    ws = _find_workspace(workspace_path=workspace_path)
    rows = list_docs(ws, typ=typ, ident=ident, q=q, include_archive=include_archive)
    return json.dumps({"ok": True, "count": len(rows), "docs": rows}, indent=2, ensure_ascii=False)


@mcp.tool()
def k3dge_doc_where(ident: str, workspace_path: Optional[str] = None) -> str:
    """Resolve a document id to catalog cards (path only). Same as CLI k3dge doc where."""
    from k3dge.engine.doc_catalog import where_doc

    ws = _find_workspace(workspace_path=workspace_path)
    rows = where_doc(ws, ident)
    return json.dumps({"ok": True, "count": len(rows), "docs": rows}, indent=2, ensure_ascii=False)


@mcp.tool()
def k3dge_doc_grep(
    query: str,
    typ: Optional[str] = None,
    line: bool = False,
    include_archive: bool = False,
    workspace_path: Optional[str] = None,
) -> str:
    """Scan managed doc bodies. Returns path (and line if requested). Never snippets. Same as CLI k3dge doc grep."""
    from k3dge.engine.doc_catalog import grep_docs

    ws = _find_workspace(workspace_path=workspace_path)
    rows = grep_docs(ws, query, typ=typ, line=line, include_archive=include_archive)
    return json.dumps({"ok": True, "count": len(rows), "hits": rows}, indent=2, ensure_ascii=False)


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
        tasks = scan_milestone_tasks(ws, milestone_id)
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
        # Full Matrix only — no human prompt. After align the next step is AUDIT
        # (not seal); seal unlocks only once the audit loop closes.
        from k3dge.engine import nextstep
        from k3dge.engine.audit_trigger import audit_closed, compute_audit_suggestion

        ok, msg, tasks = run_milestone_alignment(ws, milestone_id)
        if not ok:
            nxt = nextstep.next_for_rejection(milestone_id, msg)
        elif audit_closed(ws, milestone_id):
            nxt = nextstep.seal_ready_for(ws, milestone_id)
        else:
            _, reasons = compute_audit_suggestion(ws)
            nxt = nextstep.NextStep.from_state("audit_suggested", milestone_id, reasons=reasons)
        return json.dumps(
            {
                "milestone_id": milestone_id,
                "aligned": ok,
                "message": msg,
                "task_count": len(tasks),
                "next": nxt.render_mcp(),
            },
            indent=2,
            ensure_ascii=False,
        )

    if act == "audit":
        # Independent audit entry: mandatory loop, 待修==0 to close.
        from k3dge.engine import nextstep

        status, msg = run_audit_flow(ws, milestone_id)
        # 流程已自己判定并 persist 了下一步：直接投影同一个判定，不拿散文消息重猜。
        nxt = nextstep.load_persisted(ws)
        if nxt is None:
            nxt_state = {"audited": "seal_ready", "escalated": "escalated"}.get(status)
            nxt = (
                nextstep.NextStep.from_state(nxt_state, milestone_id).render_mcp()
                if nxt_state
                else nextstep.next_for_rejection(milestone_id, msg).render_mcp()
            )
        return json.dumps(
            {
                "milestone_id": milestone_id,
                "status": status,
                "audited": status == "audited",
                "message": msg,
                "next": nxt,
            },
            indent=2,
            ensure_ascii=False,
        )

    if act == "seal":
        # Seal requires a closed audit. If not closed, run_seal_flow returns
        # `audit_needed` pointing back at the audit entry.
        from k3dge.engine import nextstep

        status, msg = run_seal_flow(ws, milestone_id)
        if status != "sealed":
            nxt = nextstep.load_persisted(ws)
            if nxt is None:
                nxt = (
                    nextstep.NextStep.from_state(status, milestone_id).render_mcp()
                    if status in nextstep.STATE_OPTIONS
                    else nextstep.next_for_rejection(milestone_id, msg).render_mcp()
                )
            return json.dumps(
                {
                    "milestone_id": milestone_id,
                    "sealed": False,
                    "status": status,
                    "message": msg,
                    "next": nxt,
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
                    "status": status,
                    "message": msg,
                    "version": new_v,
                    "previous_version": prev,
                    "next": nextstep.NextStep.from_state("sealed", milestone_id).render_mcp(),
                },
                indent=2,
                ensure_ascii=False,
            )
        except Exception as exc:
            return json.dumps(
                {
                    "milestone_id": milestone_id,
                    "sealed": True,
                    "status": status,
                    "message": msg,
                    "version_bump_failed": str(exc),
                    "next": nextstep.NextStep.from_state("sealed", milestone_id).render_mcp(),
                },
                indent=2,
                ensure_ascii=False,
            )

    return _err("InvalidAction", f"Invalid action '{action}'. Choose from: status, align, audit, seal.")


@mcp.tool()
def k3dge_submit_audit_report(
    milestone_id: str,
    content: str,
    workspace_path: Optional[str] = None,
) -> str:
    """Persist a human/agent-submitted audit report as the canonical on-disk report.

    External audit sources (a human pasting a report into the dialog, or an agent
    forwarding one) must be landed under docs/reviews/ so the seal flow can gate on
    it. Canonicalizes the 12-col header when missing; latest submission wins.
    """
    ws = _find_workspace(workspace_path=workspace_path)
    path = persist_external_audit_report(ws, milestone_id, content or "")
    return json.dumps(
        {"ok": True, "milestone_id": milestone_id, "path": str(path)},
        indent=2,
        ensure_ascii=False,
    )


def _audit_protocol_with_fallback(workspace_path: Optional[str] = None) -> tuple[str, bool, str]:
    """Resolve audit protocol per Rule 07 with fallback detection.

    Returns (protocol_path, used_fallback, reason). Highlights fallback to default.
    Priority: ../k3dit/docs/guides/audit-method.md → docs/protocols/audit_default.md (local docs/guides/audit-method.md deprecated per Diátaxis)
    Also checks .mcp.json for k3dit harness availability (required for actual k3dit_run_audit call).
    """
    from k3dge.engine.mcp_json import load_mcp_endpoints

    ws = _find_workspace(workspace_path=workspace_path)
    candidates = [
        (ws.parent / "k3dit" / "docs" / "guides" / "audit-method.md", "k3dit"),
        (ws / ".." / "k3dit" / "docs" / "guides" / "audit-method.md", "k3dit alt"),
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
        has_k3dit = "k3dit" in load_mcp_endpoints(ws)
        if not has_k3dit:
            reason = ".mcp.json missing mcpServers.k3dit (harness not configured), k3dit_run_audit unavailable"
            fell_back = True
            proto = str(fallback.relative_to(ws)) if fallback.is_relative_to(ws) else str(fallback)
    if fell_back and not reason:
        reason = "protocol file not found"
    return (proto, fell_back, reason)


_DOC_SCOPE_ROOTS = (
    "adr",
    "tasks",
    "incidents",
    "memo",
    "branches",
    "reviews",
    "guides",
    "specs",
    "architecture",
    "protocols",
)


def _is_doc_scope(target_scope: str) -> bool:
    """Route to the Doc lens only on whole path segments, never substrings (code-5).

    The old `marker in scope` test matched `src/k3dge/engine/adr_gate.py` on the bare token
    `adr`, so code scopes silently skipped Pass N.
    """
    s = (target_scope or "").strip().replace("\\", "/").lower().strip("/")
    if not s:
        return False
    segs = [seg for seg in s.split("/") if seg]
    if not segs:
        return False
    return "docs" in segs or segs[0] in _DOC_SCOPE_ROOTS


@mcp.prompt()
def k3dge_5pass_audit_prompt(pass_number: int, target_scope: str, context_snippet: str) -> str:
    """Pointer to the independent audit harness (k3dit). Lenses do not live in k3dge.

    Unified audit entry — NOT a separate doc harness. Code scope routes to the 5-Pass
    lens; document scope routes to the Doc Audit section of the same protocol. Same peer
    (k3dit), same 12-col report, same on_pre_seal verify (ADR-0005).
    """
    proto, fell_back, reason = _audit_protocol_with_fallback()
    # Highlighted fallback warning when external harness (k3dit) unavailable
    banner = ""
    if fell_back:
        # Audit protocol is NOT part of k3dge; under fallback the working agent would
        # self-audit, which re-glues work/check (ADR-0006 sidecar boundary). Surface it
        # loudly and forbid self-certifying a seal with this lens.
        banner = (
            "!!! \033[1;41mWARN[DOWNGRADE]\033[0m \033[1;33m"
            f"k3dit audit harness unavailable ({reason}), "
            "falling back to DEFAULT docs/protocols/audit_default.md\033[0m !!!\n"
            "WARN[DOWNGRADE] k3dit not found → DEFAULT audit_default.md\n"
            f"[WARN] Reason: {reason}\n"
            "[WARN] lens_source = default-self: 此透镜由干活 agent 自审，不构成独立审计；"
            "seal 前须转人工 / 外部 harness（k3dit）复核，禁止自审即封板。\n\n"
        )
    if _is_doc_scope(target_scope):
        return (
            banner
            + f"Audit protocol is NOT part of k3dge. Read {proto} (Doc Audit section); "
            + ("(DEFAULT fallback = 自审，非独立审计)" if fell_back else "(k3dit lens)")
            + f" Apply the document lens (ADR conflict/coverage + README-rule compliance). "
            + f"Scope: {target_scope}. ADR facts via k3dge_adr_index.\n\n"
            f"```\n{context_snippet}\n```\n"
        )
    return (
        banner
        + f"Audit protocol is NOT part of k3dge. Read {proto}; "
        + ("(DEFAULT fallback = 自审，非独立审计)" if fell_back else "(k3dit lens)")
        + f" Execute only Pass {pass_number}. Scope: {target_scope}.\n\n"
        f"```\n{context_snippet}\n```\n"
    )


@mcp.tool()
def k3dge_adr_index(workspace_path: Optional[str] = None) -> str:
    """Fact tool: ADR set self-consistency (coverage/conflict facts). Non-judgmental; k3dit decides.

    Builds the ADR index + O(n) overlap/pointer findings (AdrIndex). Surfaces candidates
    only — never judges whether a conflict is real. See audit_default.md Doc Audit lens.
    """
    from k3dge.engine.doc_catalog import analyze_adr_coverage

    ws = _find_workspace(workspace_path=workspace_path)
    return json.dumps(analyze_adr_coverage(ws), ensure_ascii=False, indent=2)





if __name__ == "__main__":
    import os as _os

    # ADR-0006：MCP 服务进程钉住启动 CWD 作服务根，_find_workspace 据此收敛 workspace_path
    _os.environ.setdefault("K3DGE_MCP_ROOT", str(Path.cwd().resolve()))
    mcp.run()
