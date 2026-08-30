"""k3dge command-line interface."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional, Sequence

from k3dge.engine.evaluator import ConsistencyEngine
from k3dge.engine.models import GateReport


def _append_log(workspace: Path, line: str) -> None:
    try:
        p = workspace / "logs/k3dge.log"
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _find_workspace(start: Optional[Path] = None, workspace_path: Optional[str] = None) -> Path:
    if workspace_path:
        p = Path(workspace_path).resolve()
        return p if p.is_dir() else p.parent
    origin = (start or Path.cwd()).resolve()
    for p in [origin, *origin.parents]:
        if (p / ".git").exists() or (p / ".agent").exists():
            return p
    return origin


def _to_json(report: GateReport) -> dict:
    return {
        "passed": report.passed,
        "changed_files": list(report.changed_files),
        "modified_domains": list(report.modified_domains),
        "violations": [
            {
                "rule_id": v.rule_id,
                "message": v.message,
                "domain": v.domain,
                "file_path": v.file_path,
            }
            for v in report.violations
        ],
    }


def cmd_check(args: argparse.Namespace) -> int:
    import datetime

    workspace = _find_workspace(Path.cwd())
    report = ConsistencyEngine(workspace).evaluate(
        run_tests=getattr(args, "with_tests", False),
        force_full=getattr(args, "force_full", False),
        staged=getattr(args, "staged", False),
    )
    if args.json:
        print(json.dumps(_to_json(report), indent=2))
    else:
        print(report.render())
    code = 0 if report.passed else 1
    _append_log(
        workspace,
        f"[{datetime.datetime.now().isoformat()}] check {'--with-tests' if getattr(args, 'with_tests', False) else ''} -> {'PASS' if report.passed else 'FAIL'} "
        f"violations={len(report.violations)} domains={','.join(report.modified_domains)}",
    )
    return code


def cmd_sync(args: argparse.Namespace) -> int:
    import datetime

    from k3dge.sync.generator import sync_all

    workspace = _find_workspace(Path.cwd())
    changed, docs_updated = sync_all(workspace, domains=args.domains)
    if not changed and not docs_updated:
        print("[SYNC] Contracts already up to date.")
        _append_log(workspace, f"[{datetime.datetime.now().isoformat()}] sync -> up-to-date")
        return 0
    for domain in changed:
        print(f"[SYNC] Updated spec contract: {domain}")
    if docs_updated:
        print("[SYNC] Updated generated docs (docs/generated/).")
    _append_log(
        workspace,
        f"[{datetime.datetime.now().isoformat()}] sync -> updated domains={','.join(changed)} docs_updated={docs_updated}",
    )
    return 0


def cmd_version(args: argparse.Namespace) -> int:
    from k3dge.engine.version import append_changelog, bump_version, get_version

    workspace = _find_workspace(Path.cwd())
    if args.version_action == "show":
        v = get_version(workspace)
        print(v or "unknown")
        return 0
    if args.version_action == "bump":
        part = args.part
        set_v = args.set_version
        notes = args.message
        try:
            new_v = bump_version(workspace, part=part, set_version=set_v)
        except Exception as exc:
            print(f"[VERSION] bump failed: {exc}", file=sys.stderr)
            return 1
        # Always append changelog; seal will pass its own notes, manual bump uses --message or default
        changelog_notes = notes or f"Bump version to {new_v}."
        try:
            from k3dge.engine.version import append_changelog as _append

            _append(workspace, new_v, notes=changelog_notes)
            print(f"[VERSION] bumped to {new_v} and updated CHANGELOG.md")
        except Exception as exc:
            print(f"[VERSION] bumped to {new_v} but changelog failed: {exc}", file=sys.stderr)
        _append_log(workspace, f"[{__import__('datetime').datetime.now().isoformat()}] version bump -> {new_v} part={part}")
        return 0
    return 1


def cmd_doc(args: argparse.Namespace) -> int:
    import subprocess

    workspace = _find_workspace(Path.cwd())
    if args.doc_action == "sync":
        from k3dge.sync.generator import sync_all

        changed, docs_updated = sync_all(workspace)
        print(f"[DOC] sync: changed={changed} docs_updated={docs_updated}")
        # Run generate-docs.sh if present
        gen = workspace / "scripts" / "generate-docs.sh"
        if gen.is_file():
            try:
                result = subprocess.run(["bash", str(gen)], cwd=workspace, capture_output=True, text=True, timeout=60)
                print(result.stdout or "")
                if result.stderr:
                    print(result.stderr, file=sys.stderr)
            except Exception as exc:
                print(f"[DOC] generate-docs.sh failed: {exc}", file=sys.stderr)
        # Verify SUMMARY index
        summary = workspace / "docs" / "reviews" / "SUMMARY.md"
        if summary.is_file():
            print(f"[DOC] SUMMARY: {summary.relative_to(workspace)} exists")
        _append_log(workspace, f"[{__import__('datetime').datetime.now().isoformat()}] doc sync -> changed={changed}")
        return 0
    return 1


def cmd_task(args: argparse.Namespace) -> int:
    import datetime

    workspace = _find_workspace(Path.cwd())
    if args.task_action == "create":
        from k3dge.engine.milestone import create_task

        title = args.title
        if not title:
            print("[TASK] create requires a title", file=sys.stderr)
            return 1
        ok, msg, path = create_task(
            workspace,
            title,
            typ=args.type,
            slug=args.slug,
            milestone=args.milestone,
            priority=args.priority or "P2",
        )
        print(f"[TASK] {msg}", file=sys.stderr if not ok else sys.stdout)
        _append_log(workspace, f"[{datetime.datetime.now().isoformat()}] task create -> {msg}")
        return 0 if ok else 1
    if args.task_action == "done":
        from k3dge.engine.milestone import mark_task_done

        raw_pat = args.task_id if args.task_id is not None else args.title
        if not raw_pat:
            print("[TASK] done requires path from 'task list' or unique filename substring", file=sys.stderr)
            return 1
        ok, msg, _ = mark_task_done(workspace, raw_pat)
        print(f"[TASK] {msg}", file=sys.stderr if not ok else sys.stdout)
        _append_log(workspace, f"[{datetime.datetime.now().isoformat()}] task done -> {msg}")
        return 0 if ok else 1
    if args.task_action == "list":
        from k3dge.engine.milestone import list_tasks

        rows = list_tasks(
            workspace,
            milestone_id=args.milestone,
            status=getattr(args, "filter_status", None),
        )
        payload = {
            "ok": True,
            "count": len(rows),
            "tasks": [
                {
                    "path": str(t.path.relative_to(workspace)).replace("\\", "/"),
                    "title": t.title,
                    "status": t.status,
                    "milestone": t.milestone,
                    "priority": t.priority,
                }
                for t in rows
            ],
        }
        if getattr(args, "as_json", False):
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            for item in payload["tasks"]:
                ms = item["milestone"] or "-"
                pr = item["priority"] or "-"
                name = Path(item["path"]).name
                print(f"[{item['status']:11s}] {pr:3s} {ms:4s} {name}  {item['title']}")
            print(f"[TASK] {len(rows)} listed")
        _append_log(
            workspace,
            f"[{datetime.datetime.now().isoformat()}] task list -> count={len(rows)}",
        )
        return 0
    return 1


def cmd_protocol(args: argparse.Namespace) -> int:
    """Deterministic protocol dispatch: pull the operation spec for a task_type."""
    workspace = _find_workspace(Path.cwd())
    action = getattr(args, "protocol_action", None)
    if action == "list":
        from k3dge.engine.protocol import ProtocolResolver

        types = ProtocolResolver(workspace).list_types()
        for t in types:
            print(t)
        print(f"[PROTOCOL] {len(types)} types registered")
        return 0
    if action == "resolve":
        from k3dge.engine.protocol import ProtocolResolver

        target = getattr(args, "path", None)
        if target:
            ref = ProtocolResolver(workspace).resolve_by_path(target)
            if ref is None:
                print(f"[PROTOCOL] no protocol mapped for path '{target}'; proceed under base spec")
                return 0
            print(f"[PROTOCOL] {ref.task_type} (path {target}) -> {ref.rel} (exists={ref.exists})")
            if ref.exists:
                print(ref.path.read_text(encoding="utf-8"))
            return 0
        task_type = getattr(args, "task_type", None)
        if not task_type:
            print("[PROTOCOL] resolve requires --path <file> or a task_type (see 'k3dge protocol list')", file=sys.stderr)
            return 1
        try:
            ref = ProtocolResolver(workspace).resolve(task_type)
        except ProtocolResolutionError as exc:
            print(f"[PROTOCOL] {exc}", file=sys.stderr)
            return 1
        print(f"[PROTOCOL] {ref.task_type} -> {ref.rel} (exists={ref.exists})")
        if ref.exists:
            print(ref.path.read_text(encoding="utf-8"))
        return 0
    if action == "challenge":
        from k3dge.engine.protocol import ProtocolResolver

        target = getattr(args, "path", None)
        task_type = getattr(args, "task_type", None)
        task_id = getattr(args, "task_id", "") or ""
        chal = ProtocolResolver(workspace).challenge(target=target, task_type=task_type, task_id=task_id)
        if chal is None:
            print("[PROTOCOL] no protocol mapped; no challenge required (proceed under base spec)")
            return 0
        print(chal)
        return 0
    if action == "ticket":
        import json as _json

        from k3dge.engine.protocol import ProtocolResolver

        target = getattr(args, "path", None)
        task_type = getattr(args, "task_type", None)
        task_id = getattr(args, "task_id", "") or ""
        ticket_json = getattr(args, "ticket", None)
        resolver = ProtocolResolver(workspace)
        if ticket_json:
            try:
                ticket = _json.loads(ticket_json)
            except Exception as exc:
                print(f"[PROTOCOL] ticket JSON parse failed: {exc}", file=sys.stderr)
                return 1
            errs = resolver.validate_ticket(target=target, task_type=task_type, ticket=ticket, task_id=task_id)
            if errs:
                for e in errs:
                    print(f"[PROTOCOL] {e}")
                return 1
            print("[PROTOCOL] ticket valid")
            return 0
        # checklist mode: show the constraints the agent must bind
        ref = resolver.resolve_by_path(target) if target else (resolver.resolve(task_type) if task_type else None)
        if ref is None:
            print("[PROTOCOL] no protocol mapped; no ticket required (base spec)")
            return 0
        constraints = resolver.expected_constraints(target=target, task_type=task_type) or []
        print(f"[PROTOCOL] protocol '{ref.task_type}' requires binding these constraints:")
        for c in constraints:
            print(f"  - {c}")
        if not constraints:
            print("  (protocol declares no structured constraints; ticket only needs shape)")
        return 0
    if action == "verify":
        import json as _json

        from k3dge.engine.protocol import ProtocolResolver

        target = getattr(args, "path", None)
        task_type = getattr(args, "task_type", None)
        task_id = getattr(args, "task_id", "") or ""
        ticket_json = getattr(args, "ticket", None)
        ticket = None
        if ticket_json:
            try:
                ticket = _json.loads(ticket_json)
            except Exception as exc:
                print(f"[PROTOCOL] ticket JSON parse failed: {exc}", file=sys.stderr)
                return 1
        verdict = ProtocolResolver(workspace).verify(
            target=target, task_type=task_type, ticket=ticket, task_id=task_id
        )
        print(_json.dumps(verdict, ensure_ascii=False, indent=2))
        # Soft gate: never a hard block. Non-zero only on tool error, not on advise.
        return 0
    if action == "report":
        from k3dge.engine.protocol import write_incident

        target = getattr(args, "path", None)
        task_type = getattr(args, "task_type", None)
        task_id = getattr(args, "task_id", "") or ""
        detail = getattr(args, "detail", "") or ""
        if not detail:
            print("[PROTOCOL] report requires --detail <text>", file=sys.stderr)
            return 1
        path = write_incident(workspace, target, task_type, task_id, detail)
        print(f"[PROTOCOL] incident reported: {path.relative_to(workspace)}")
        return 0
    if action == "attend":
        from k3dge.engine import marker
        from k3dge.engine.protocol import ProtocolResolver

        target = getattr(args, "path", None)
        answer = getattr(args, "answer", None)
        task_id = getattr(args, "task_id", "") or ""
        epoch_id = getattr(args, "epoch_id", None)
        if not target or not answer:
            print("[PROTOCOL] attend requires --path <file> --answer <sha>", file=sys.stderr)
            return 1
        resolver = ProtocolResolver(workspace)
        expected = resolver.challenge(target=target, task_id=task_id)
        if expected is None:
            print("[PROTOCOL] no protocol mapped; nothing to attend")
            return 0
        ok, epoch = marker.register_attendance(
            workspace, target, answer=answer, expected=expected, epoch_id=epoch_id
        )
        if ok:
            print(f"[PROTOCOL] attended {target} (epoch {epoch})")
            return 0
        print(f"[PROTOCOL] challenge mismatch: expected {expected}", file=sys.stderr)
        return 1
    print("[PROTOCOL] unknown action", file=sys.stderr)
    return 1


def cmd_init(args: argparse.Namespace) -> int:
    from pathlib import Path

    from k3dge.sync.generator import sync_all
    from k3dge.templates.scaffold import scaffold

    target = Path(args.target).resolve()
    scaffold(target, name=args.name)
    # Generate initial contract hash for first domain
    try:
        sync_all(target)
    except Exception:
        pass
    print(f"[INIT] Successfully initialized k3dge harness in {target}")
    return 0


def _peer_fallback_warn(peer: str, reason: str, fallback: str) -> None:
    """Highlighted warning when an external peer is unavailable and we fall back to default."""
    msg = f"Peer '{peer}' failed ({reason}) → fallback to DEFAULT '{fallback}'"
    # High-visibility: red background + yellow text + plain fallback for non-TTY
    banner = f"\033[1;41m[WARN][HARNESS FALLBACK]\033[0m \033[1;33m{msg}\033[0m"
    print(banner, file=sys.stderr)
    print(f"[WARN][HARNESS FALLBACK] {msg}", file=sys.stderr)


def _peer_fallback(pcfg: dict) -> str:
    """Resolve the terminal fallback descriptor for a peer from its transport chains.

    A peer may carry peer-level `transports` (single-purpose) or `actions.<name>.transports`
    (multi-purpose). The fallback is the last transport's descriptor: a `manual` provider
    yields its `protocol`, a `skip` provider yields "skip".
    """
    chains = []
    if pcfg.get("transports"):
        chains.append(pcfg["transports"])
    for action_cfg in pcfg.get("actions", {}).values():
        ts = action_cfg.get("transports")
        if ts:
            chains.append(ts)
    for transports in chains:
        if not transports:
            continue
        last = transports[-1]
        if last.get("provider") == "manual":
            return last.get("protocol", "audit_default.md")
        if last.get("provider") == "skip":
            return "skip"
    return "audit_default.md"


def cmd_mcp(args: argparse.Namespace) -> int:
    from k3dge.templates.scaffold import ensure_mcp_config

    workspace = _find_workspace(Path.cwd())
    if args.mcp_action == "sync":
        ok_mcp = ensure_mcp_config(workspace)
        if not ok_mcp:
            print("[MCP] .mcp.json skipped due to corruption, see WARN above; not overwriting", file=sys.stderr)
        # Peer merging from pipeline.toml is best-effort; report if pipeline is unreadable
        # tomllib is 3.11+, tomli is fallback for 3.10; neither present → skip peer merging gracefully
        try:
            tomllib_mod = None
            try:
                import tomllib as tomllib_mod  # py 3.11+
            except ImportError:
                try:
                    import tomli as tomllib_mod  # type: ignore[import-not-found]
                except ImportError:
                    tomllib_mod = None
            if tomllib_mod is None:
                _peer_fallback_warn("pipeline", "tomllib/tomli not available (py<3.11 without tomli)", "skip peer merging, keep k3dge only")
            else:
                cfg_path = workspace / ".agent" / "pipeline.toml"
                if cfg_path.is_file():
                    try:
                        cfg = tomllib_mod.loads(cfg_path.read_text(encoding="utf-8"))
                    except Exception as exc:
                        print(f"[MCP] pipeline.toml parse failed: {exc}", file=sys.stderr)
                        return 1
                    # Peer merging: ensure enabled peers have an .mcp.json entry if sibling exists
                    import json as _json

                    mcp_path = workspace / ".mcp.json"
                    try:
                        data = _json.loads(mcp_path.read_text(encoding="utf-8")) if mcp_path.is_file() else {"mcpServers": {}}
                        if not isinstance(data, dict):
                            data = {"mcpServers": {}}
                    except Exception:
                        data = {"mcpServers": {}}
                    if "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
                        data["mcpServers"] = {}
                    changed = False
                    for pid, pcfg in cfg.get("peers", {}).items():
                        if pid == "k3dge":
                            continue
                        if not pcfg.get("enabled", True):
                            continue
                        if pid in data["mcpServers"]:
                            continue
                        # Probe sibling peer (e.g. ../k3dit, ../k3che, ../k3lity)
                        sibling = workspace.parent / pid
                        alt_sibling = workspace / pid
                        probe = sibling if sibling.is_dir() else (alt_sibling if alt_sibling.is_dir() else None)
                        # Deduce module: prefer <pid>.mcp, fallback to <pid>.cli.mcp
                        mod = None
                        if probe is not None:
                            if (probe / "src" / pid / "mcp.py").is_file():
                                mod = f"{pid}.mcp"
                            elif (probe / "src" / pid / "cli" / "mcp.py").is_file():
                                mod = f"{pid}.cli.mcp"
                            elif (probe / "pyproject.toml").is_file():
                                mod = f"{pid}.mcp"
                        if probe is not None and mod is not None:
                            # Auto-add peer entry (best-effort)
                            data["mcpServers"][pid] = {"command": "python", "args": ["-m", mod]}
                            changed = True
                            print(f"[MCP] auto-added peer '{pid}' from sibling {probe} as python -m {mod}", file=sys.stderr)
                        else:
                            fallback = _peer_fallback(pcfg)
                            _peer_fallback_warn(pid, f"sibling not found at {sibling} nor {alt_sibling} or no mcp module", fallback)
                    if changed:
                        try:
                            tmp = mcp_path.with_suffix(".tmp")
                            tmp.write_text(_json.dumps(data, indent=2) + "\n", encoding="utf-8")
                            tmp.replace(mcp_path)
                        except Exception as exc:
                            print(f"[MCP] peer merge write failed: {exc}", file=sys.stderr)
                            return 1
                else:
                    _peer_fallback_warn("pipeline", ".agent/pipeline.toml not found", "keep k3dge only")
        except Exception as exc:
            print(f"[MCP] pipeline handling failed: {exc}", file=sys.stderr)
            return 1
        print(f"[MCP] synced {workspace / '.mcp.json'}")
        return 0
    return 1


def cmd_milestone(args: argparse.Namespace) -> int:
    from k3dge.engine.milestone import run_milestone_alignment, seal_milestone, scan_milestone_tasks

    workspace = _find_workspace(Path.cwd())
    action = args.action
    m_id = args.milestone_id

    if action == "status":
        tasks = scan_milestone_tasks(workspace, m_id)
        if not tasks:
            print(f"[MILESTONE] No tasks found with Milestone: '{m_id}'")
            return 1
        done_cnt = sum(1 for t in tasks if t.status == "done")
        print(f"[MILESTONE {m_id}] Total: {len(tasks)} | Done: {done_cnt} | Pending: {len(tasks) - done_cnt}")
        for t in tasks:
            print(f"  [{t.status.upper():11s}] {t.path.name}")
        _append_log(workspace, f"[{__import__('datetime').datetime.now().isoformat()}] milestone status -> {m_id} total={len(tasks)} done={done_cnt}")
        return 0

    if action == "align":
        ok, msg, _ = run_milestone_alignment(workspace, m_id)
        print(msg)
        _append_log(workspace, f"[{__import__('datetime').datetime.now().isoformat()}] milestone align -> {m_id} ok={ok}")
        # Peer pipeline availability check: highlight fallback to default when external peer missing
        if ok:
            try:
                import json as _js
                tomllib_mod2 = None
                try:
                    import tomllib as tomllib_mod2
                except ImportError:
                    try:
                        import tomli as tomllib_mod2
                    except ImportError:
                        tomllib_mod2 = None
                if tomllib_mod2 is not None:
                    cfg_path2 = workspace / ".agent" / "pipeline.toml"
                    if cfg_path2.is_file():
                        try:
                            cfg2 = tomllib_mod2.loads(cfg_path2.read_text(encoding="utf-8"))
                            mcp_path2 = workspace / ".mcp.json"
                            try:
                                data2 = _js.loads(mcp_path2.read_text(encoding="utf-8")) if mcp_path2.is_file() else {}
                            except Exception:
                                data2 = {}
                            mcp_servers = data2.get("mcpServers", {}) if isinstance(data2, dict) else {}
                            for pid, pcfg in cfg2.get("peers", {}).items():
                                if not pcfg.get("enabled", True):
                                    continue
                                if pid == "k3dge":
                                    continue
                                if pid not in mcp_servers:
                                    fallback = _peer_fallback(pcfg)
                                    _peer_fallback_warn(pid, f"enabled in pipeline.toml but missing in .mcp.json (no sibling or not synced via 'k3dge mcp sync')", fallback)
                        except Exception:
                            pass
            except Exception:
                pass
        if ok and "HUMAN_CHECKPOINT" in msg:
            # Interactive checkpoint: only when stdin is a TTY; 60s timeout, default N
            if sys.stdin.isatty():
                try:
                    import select

                    print("HUMAN_CHECKPOINT: Milestone {} all green, run 5-Pass audit? (y/N, 60s timeout default N): ".format(m_id), end="", flush=True)
                    rlist, _, _ = select.select([sys.stdin], [], [], 60)
                    if rlist:
                        ans = sys.stdin.readline().strip().lower()
                        if ans in ("y", "yes"):
                            print("[CHECKPOINT] User requested audit — create audit task and run k3dit")
                        else:
                            print("[CHECKPOINT] Skipped audit")
                    else:
                        print("\n[CHECKPOINT] Timeout (60s), default N — skipping audit")
                except Exception:
                    pass
            else:
                # Non-interactive (CI/tests): surface checkpoint as log, default N
                print("[CHECKPOINT] Non-interactive, default N — skipping audit")
        return 0 if ok else 1

    if action == "seal":
        ok, msg = seal_milestone(workspace, m_id)
        print(msg)
        _append_log(workspace, f"[{__import__('datetime').datetime.now().isoformat()}] milestone seal -> {m_id} ok={ok}")
        if not ok:
            return 1
        # Auto-bump patch version on successful seal (unless --no-bump)
        if getattr(args, "no_version_bump", False):
            return 0
        try:
            from k3dge.engine.version import append_changelog, bump_version, consume_unreleased

            new_v = bump_version(workspace, part="patch")
            body = consume_unreleased(workspace)
            notes = body if body else f"Seal milestone {m_id}."
            append_changelog(workspace, new_v, notes=notes)
            print(f"[VERSION] auto-bumped to {new_v} and updated CHANGELOG.md")
            _append_log(workspace, f"[{__import__('datetime').datetime.now().isoformat()}] version auto-bump -> {new_v} milestone={m_id}")
        except Exception as exc:
            print(f"[VERSION] auto-bump failed: {exc}", file=sys.stderr)
            # Seal itself succeeded; bump failure is non-blocking warning
        return 0

    return 1


_CONV_RE = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([\w\-.]+\))?!?: .+"
)


def _conventional_ok(msg: str) -> bool:
    return bool(_CONV_RE.match(msg or ""))


def _rel_within_workspace(workspace: Path, p: str) -> Path:
    """SEC-01: resolve a user path and ensure it stays inside the workspace."""
    target = (workspace / p).resolve()
    try:
        target.relative_to(workspace.resolve())
    except ValueError as exc:
        raise ValueError(f"path '{p}' escapes workspace root (SEC-01)") from exc
    return target


def cmd_get(args: argparse.Namespace) -> int:
    import uuid

    from k3dge.engine.protocol import ProtocolResolver

    workspace = _find_workspace(Path.cwd())
    try:
        target = _rel_within_workspace(workspace, args.path)
    except ValueError as exc:
        print(f"[GET] {exc}", file=sys.stderr)
        return 1
    resolver = ProtocolResolver(workspace)
    ref = resolver.resolve_by_path(target)
    if ref is not None:
        print(f"[GET] protocol injected ({ref.task_type}): {ref.rel}")
        if ref.exists:
            print("=" * 60)
            print(ref.path.read_text(encoding="utf-8"))
            print("=" * 60)
    if not target.is_file():
        print(f"[GET] file not found: {args.path}", file=sys.stderr)
        return 1
    print(target.read_text(encoding="utf-8"))
    print(f"[GET] TASK_ID: {uuid.uuid4().hex[:8]}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    from k3dge.engine.search import search

    workspace = _find_workspace(Path.cwd())
    if getattr(args, "path", None):
        # Path-listing mode (replaces bare `find`): list files matching the glob.
        matches = sorted(
            str(p.relative_to(workspace)).replace("\\", "/")
            for p in workspace.glob(args.path)
            if p.is_file()
        )
        for m in matches:
            print(m)
        return 0
    locs = search(workspace, args.query, snippet=not args.no_snippet, context=args.context)
    for loc in locs:
        print(loc.render())
    return 0


def cmd_where(args: argparse.Namespace) -> int:
    from k3dge.engine.search import where

    workspace = _find_workspace(Path.cwd())
    locs = where(workspace, args.symbol)
    if not locs:
        print(f"[WHERE] no symbol '{args.symbol}' in index (run 'k3dge index')", file=sys.stderr)
        return 1
    for loc in locs:
        print(loc.render())
    return 0


def cmd_edit(args: argparse.Namespace) -> int:
    import uuid

    from k3dge.engine.protocol import ProtocolResolver

    workspace = _find_workspace(Path.cwd())
    resolver = ProtocolResolver(workspace)
    rc = 0
    for raw in args.files:
        try:
            target = _rel_within_workspace(workspace, raw)
        except ValueError as exc:
            print(f"[EDIT] {exc}", file=sys.stderr)
            rc = 1
            continue
        rel = str(target.relative_to(workspace)).replace("\\", "/")
        ref = resolver.resolve_by_path(target)
        task_id = uuid.uuid4().hex[:8]
        print(f"[EDIT] session opened: {rel}")
        if ref is not None and ref.require_attend:
            print(f"[EDIT] REQUIRE_ATTEND zone ({ref.task_type}); protocol injected below")
            if ref.exists:
                print("-" * 40)
                print(ref.path.read_text(encoding="utf-8"))
                print("-" * 40)
            print(
                f"[EDIT] after reading, run: k3dge protocol attend --path {rel} "
                f"--task-id {task_id} --answer <sha>"
            )
        else:
            print(f"[EDIT] no protocol required for {rel}")
    return rc


def cmd_put(args: argparse.Namespace) -> int:
    import os

    from k3dge.engine import marker
    from k3dge.engine.protocol import ProtocolResolver

    workspace = _find_workspace(Path.cwd())
    try:
        target = _rel_within_workspace(workspace, args.path)
    except ValueError as exc:
        print(f"[PUT] {exc}", file=sys.stderr)
        return 1
    rel = str(target.relative_to(workspace)).replace("\\", "/")
    resolver = ProtocolResolver(workspace)
    ref = resolver.resolve_by_path(target)
    content = sys.stdin.read()
    if ref is not None and ref.require_attend:
        if not args.answer:
            print(
                f"[PUT] REQUIRE_ATTEND zone ({ref.task_type}) needs --answer <sha> (load-proof)",
                file=sys.stderr,
            )
            return 1
        task_id = args.task_id or ""
        expected = resolver.challenge(target=target, task_id=task_id)
        if args.answer != expected:
            print(
                f"[PUT] challenge mismatch: expected {expected}, got {args.answer}",
                file=sys.stderr,
            )
            return 1
        marker.register_attendance(
            workspace, rel, answer=args.answer, expected=expected, epoch_id=args.epoch_id
        )
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, target)
    print(f"[PUT] wrote {rel}")
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    from k3dge.engine.search import write_symbol_index

    workspace = _find_workspace(Path.cwd())
    out = write_symbol_index(workspace)
    print(f"[INDEX] wrote {out.relative_to(workspace)}")
    return 0


def cmd_end(args: argparse.Namespace) -> int:
    from k3dge.engine import marker

    workspace = _find_workspace(Path.cwd())
    marker.reset_session(workspace)
    print("[END] session cleared (attended_zones + epoch rotated)")
    return 0


def cmd_commit(args: argparse.Namespace) -> int:
    import subprocess

    from k3dge.engine import marker
    from k3dge.engine.evaluator import ConsistencyEngine
    from k3dge.engine.protocol import ProtocolResolver, write_incident

    workspace = _find_workspace(Path.cwd())
    # 1) stage (GIT-01: -- separator isolates filenames)
    if args.all:
        subprocess.run(["git", "add", "-A"], cwd=workspace, check=False)
    if args.files:
        subprocess.run(["git", "add", "--", *args.files], cwd=workspace, check=False)
    # 2) conventional commit message validation
    if not _conventional_ok(args.message):
        print(
            f"[COMMIT] message '{args.message}' is not Conventional Commits (e.g. 'feat: ...')",
            file=sys.stderr,
        )
        return 1
    # 3) single-point attendance check (advisory + L2 incident, not blocking — soft gate)
    staged = ConsistencyEngine(workspace)._staged_files()
    resolver = ProtocolResolver(workspace)
    epoch = marker.ensure_epoch(workspace)
    for f in staged:
        ref = resolver.resolve_by_path(f)
        if ref is not None and ref.require_attend and not marker.is_attended(workspace, f, epoch):
            detail = (
                f"require_attend zone '{f}' ({ref.task_type}) committed without a valid "
                "(zone,task_id) challenge credential"
            )
            print(f"[COMMIT][ADVISORY] {detail}", file=sys.stderr)
            write_incident(workspace, f, ref.task_type, "", detail)
    # 4) gate (blocking)
    report = ConsistencyEngine(workspace).evaluate(staged=True, run_tests=args.with_tests)
    if not report.passed:
        print(report.render())
        return 1
    # 5) commit, bypass hooks (internal check already covered) under sentinel env
    env = dict(__import__("os").environ)
    env["K3DGE_COMMIT_ACTIVE"] = "1"
    res = subprocess.run(
        ["git", "commit", "-m", args.message, "--no-verify"],
        cwd=workspace,
        env=env,
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        print(res.stderr or res.stdout, file=sys.stderr)
        return 1
    print(res.stdout)
    return 0


def cmd_incident(args: argparse.Namespace) -> int:
    import json as _json
    from pathlib import Path as _Path

    from k3dge.engine.protocol import write_incident

    workspace = _find_workspace(Path.cwd())
    if args.from_ci:
        data = _json.loads(_Path(args.from_ci).read_text(encoding="utf-8"))
    else:
        data = _json.loads(sys.stdin.read())
    p = write_incident(
        workspace,
        data.get("path"),
        data.get("task_type"),
        data.get("task_id", ""),
        data.get("detail", ""),
    )
    print(f"[INCIDENT] wrote {p.relative_to(workspace)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="k3dge",
        description="Spec-gate harness for deterministic agent governance",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="run the consistency gate")
    p_check.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    p_check.add_argument(
        "--with-tests", action="store_true", help="also run Verification Matrix tests for touched domains (selective L2)"
    )
    p_check.add_argument(
        "--force-full",
        action="store_true",
        help="validate all registered domains (L0/L1), not only git-touched ones",
    )
    p_check.add_argument(
        "--staged",
        action="store_true",
        help="validate only the git staging area (used by 'k3dge commit')",
    )
    p_check.set_defaults(func=cmd_check)

    p_sync = sub.add_parser("sync", help="regenerate spec contracts from code")
    p_sync.add_argument(
        "--domain",
        dest="domains",
        action="append",
        default=None,
        help="only sync this domain (repeatable)",
    )
    p_sync.set_defaults(func=cmd_sync)

    p_milestone = sub.add_parser("milestone", help="milestone alignment and context compaction")
    p_milestone.add_argument("action", choices=["status", "align", "seal"], help="milestone action")
    p_milestone.add_argument("milestone_id", help="milestone identifier (matches Milestone field in tasks)")
    p_milestone.add_argument(
        "--no-version-bump",
        action="store_true",
        help="for seal: do not auto-bump patch version and changelog",
    )
    p_milestone.set_defaults(func=cmd_milestone)

    p_version = sub.add_parser("version", help="show or bump project version (pyproject.toml ↔ manifest ↔ __init__)")
    p_version.add_argument("version_action", choices=["show", "bump"], help="show current version or bump it")
    g = p_version.add_mutually_exclusive_group()
    g.add_argument("--major", dest="part", action="store_const", const="major", help="bump major (X.0.0)")
    g.add_argument("--minor", dest="part", action="store_const", const="minor", help="bump minor (X.Y.0)")
    g.add_argument("--patch", dest="part", action="store_const", const="patch", help="bump patch (X.Y.Z+1) [default]")
    p_version.add_argument("--set", dest="set_version", default=None, help="set exact version (e.g., 1.2.3)")
    p_version.add_argument("-m", "--message", dest="message", default=None, help="changelog entry message")
    p_version.set_defaults(func=cmd_version, part="patch")

    p_task = sub.add_parser("task", help="task intake")
    p_task.add_argument("task_action", choices=["create", "done", "list"], help="task action")
    p_task.add_argument("title", nargs="?", default=None, help="task title (for create) or task id substring (for done)")
    p_task.add_argument("--type", dest="type", choices=["audit", "feat", "fix", "docs", "chore", "refactor"], default="fix", help="task type (create)")
    p_task.add_argument("--slug", dest="slug", default=None, help="slug (default derived from title, _ separated)")
    p_task.add_argument("--milestone", dest="milestone", default=None, help="milestone id (create: assign; list: filter)")
    p_task.add_argument("--priority", dest="priority", choices=["P0", "P1", "P2", "P3"], default="P2", help="priority (create)")
    p_task.add_argument("--status", dest="filter_status", default=None, help="status filter (list)")
    p_task.add_argument("--json", dest="as_json", action="store_true", help="JSON index (list)")
    p_task.add_argument("task_id", nargs="?", default=None, help="task id substring for done (alternative to title)")
    p_task.set_defaults(func=cmd_task)

    p_doc = sub.add_parser("doc", help="doc generation")
    p_doc.add_argument("doc_action", choices=["sync"], help="doc action")
    p_doc.set_defaults(func=lambda args: cmd_doc(args))

    p_init = sub.add_parser("init", help="initialize k3dge harness in target directory")
    p_init.add_argument("target", nargs="?", default=".", help="target directory (default: current working dir)")
    p_init.add_argument("--name", dest="name", default=None, help="initial domain name (default: directory name)")
    p_init.set_defaults(func=cmd_init)

    p_mcp = sub.add_parser("mcp", help="MCP config")
    p_mcp.add_argument("mcp_action", choices=["sync"], help="mcp action")
    p_mcp.set_defaults(func=cmd_mcp)

    p_protocol = sub.add_parser(
        "protocol",
        help="deterministic protocol dispatch (task_type -> protocol markdown)",
    )
    p_protocol.add_argument("protocol_action", choices=["resolve", "list", "challenge", "ticket", "verify", "report", "attend"], help="protocol action")
    p_protocol.add_argument(
        "task_type",
        nargs="?",
        default=None,
        help="task type to resolve (for 'resolve'/'challenge'; see 'k3dge protocol list')",
    )
    p_protocol.add_argument(
        "--path",
        dest="path",
        default=None,
        help="target file path to resolve by path routing (for 'resolve'/'challenge'); overrides task_type",
    )
    p_protocol.add_argument(
        "--task-id",
        dest="task_id",
        default="",
        help="task id bound into the dynamic challenge / entry ticket (for 'challenge'/'ticket')",
    )
    p_protocol.add_argument(
        "--ticket",
        dest="ticket",
        default=None,
        help="entry ticket JSON to validate (for 'ticket'/'verify'); omit to print the required constraint checklist",
    )
    p_protocol.add_argument(
        "--detail",
        dest="detail",
        default=None,
        help="human-visible deviation description (for 'report')",
    )
    p_protocol.add_argument(
        "--answer",
        dest="answer",
        default=None,
        help="dynamic challenge answer (sha256(normalize(protocol)+task_id)[:12]) for 'attend'",
    )
    p_protocol.add_argument(
        "--epoch-id",
        dest="epoch_id",
        default=None,
        help="explicit epoch id; if omitted marker.py auto-generates uuid4().hex[:8]",
    )
    p_protocol.set_defaults(func=cmd_protocol)

    p_get = sub.add_parser("get", help="controlled read: file content + injected protocol context")
    p_get.add_argument("path", help="repo-relative file path to read")
    p_get.set_defaults(func=cmd_get)

    p_search = sub.add_parser("search", help="controlled search (replaces bare grep/ls)")
    p_search.add_argument("query", help="search term / regex")
    p_search.add_argument("--path", dest="path", default=None, help="glob for path-listing mode (replaces `find`)")
    p_search.add_argument("--no-snippet", action="store_true", help="return path:line coords only")
    p_search.add_argument(
        "--context",
        type=int,
        default=2,
        help="narrow context window half-width (clamped to <=3 to kill noise)",
    )
    p_search.set_defaults(func=cmd_search)

    p_where = sub.add_parser("where", help="symbol-level deterministic addressing (file:line)")
    p_where.add_argument("symbol", help="top-level symbol name")
    p_where.set_defaults(func=cmd_where)

    p_edit = sub.add_parser("edit", help="open a controlled edit session (inject protocol, trigger attend)")
    p_edit.add_argument("files", nargs="+", help="repo-relative file paths")
    p_edit.set_defaults(func=cmd_edit)

    p_put = sub.add_parser("put", help="controlled writeback (attend verify + atomic write)")
    p_put.add_argument("path", help="repo-relative file path to write")
    p_put.add_argument("--answer", dest="answer", default=None, help="challenge answer sha for require_attend zones")
    p_put.add_argument("--task-id", dest="task_id", default="", help="task id bound into the challenge")
    p_put.add_argument("--epoch-id", dest="epoch_id", default=None, help="explicit epoch id")
    p_put.set_defaults(func=cmd_put)

    p_index = sub.add_parser("index", help="rebuild the symbol index (docs/generated/symbol-index.json)")
    p_index.set_defaults(func=cmd_index)

    p_end = sub.add_parser("end", help="end the session: clear attended_zones + rotate epoch")
    p_end.set_defaults(func=cmd_end)

    p_commit = sub.add_parser("commit", help="encapsulated commit: gate + single-point attendance check")
    p_commit.add_argument("files", nargs="*", default=[], help="files to stage (else use --all)")
    p_commit.add_argument("-m", dest="message", required=True, help="conventional commit message")
    p_commit.add_argument("-a", dest="all", action="store_true", help="stage all tracked modifications")
    p_commit.add_argument(
        "--with-tests", action="store_true", help="run Verification Matrix tests during the staged gate"
    )
    p_commit.set_defaults(func=cmd_commit)

    p_incident = sub.add_parser("incident", help="L2 incident generator (from CI JSON)")
    p_incident.add_argument("--from-ci", dest="from_ci", default=None, help="path to JSON payload")
    p_incident.set_defaults(func=cmd_incident)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
