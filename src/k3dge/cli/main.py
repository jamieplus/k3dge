"""k3dge command-line interface."""

from __future__ import annotations

import argparse
import json
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


def _harness_fallback_warn(harness: str, reason: str, fallback: str) -> None:
    """Highlighted warning when external harness fails and we fall back to default."""
    msg = f"Harness '{harness}' failed ({reason}) → fallback to DEFAULT '{fallback}'"
    # High-visibility: red background + yellow text + plain fallback for non-TTY
    banner = f"\033[1;41m[WARN][HARNESS FALLBACK]\033[0m \033[1;33m{msg}\033[0m"
    print(banner, file=sys.stderr)
    print(f"[WARN][HARNESS FALLBACK] {msg}", file=sys.stderr)


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
                _harness_fallback_warn("pipeline", "tomllib/tomli not available (py<3.11 without tomli)", "skip peer merging, keep k3dge only")
            else:
                cfg_path = workspace / ".agent" / "pipeline.toml"
                if cfg_path.is_file():
                    try:
                        cfg = tomllib_mod.loads(cfg_path.read_text(encoding="utf-8"))
                    except Exception as exc:
                        print(f"[MCP] pipeline.toml parse failed: {exc}", file=sys.stderr)
                        return 1
                    # Peer merging: ensure enabled harnesses have an .mcp.json entry if sibling exists
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
                    for hid, hcfg in cfg.get("harnesses", {}).items():
                        if hid == "k3dge":
                            continue
                        if not hcfg.get("enabled", True):
                            continue
                        if hid in data["mcpServers"]:
                            continue
                        # Probe sibling harness (e.g. ../k3dit, ../k3che, ../k3lity)
                        sibling = workspace.parent / hid
                        alt_sibling = workspace / hid
                        probe = sibling if sibling.is_dir() else (alt_sibling if alt_sibling.is_dir() else None)
                        # Deduce module: prefer <hid>.mcp, fallback to <hid>.cli.mcp
                        mod = None
                        if probe is not None:
                            if (probe / "src" / hid / "mcp.py").is_file():
                                mod = f"{hid}.mcp"
                            elif (probe / "src" / hid / "cli" / "mcp.py").is_file():
                                mod = f"{hid}.cli.mcp"
                            elif (probe / "pyproject.toml").is_file():
                                mod = f"{hid}.mcp"
                        if probe is not None and mod is not None:
                            # Auto-add peer entry (best-effort)
                            data["mcpServers"][hid] = {"command": "python", "args": ["-m", mod]}
                            changed = True
                            print(f"[MCP] auto-added peer '{hid}' from sibling {probe} as python -m {mod}", file=sys.stderr)
                        else:
                            fallback = hcfg.get("manual_protocol", "docs/protocols/audit_default.md")
                            _harness_fallback_warn(hid, f"sibling not found at {sibling} nor {alt_sibling} or no mcp module", fallback)
                    if changed:
                        try:
                            tmp = mcp_path.with_suffix(".tmp")
                            tmp.write_text(_json.dumps(data, indent=2) + "\n", encoding="utf-8")
                            tmp.replace(mcp_path)
                        except Exception as exc:
                            print(f"[MCP] peer merge write failed: {exc}", file=sys.stderr)
                            return 1
                else:
                    _harness_fallback_warn("pipeline", ".agent/pipeline.toml not found", "keep k3dge only")
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
        # Harness pipeline availability check: highlight fallback to default when external harness missing
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
                            for hid, hcfg in cfg2.get("harnesses", {}).items():
                                if not hcfg.get("enabled", True):
                                    continue
                                if hid == "k3dge":
                                    continue
                                if hid not in mcp_servers:
                                    _harness_fallback_warn(hid, f"enabled in pipeline.toml but missing in .mcp.json (no sibling or not synced via 'k3dge mcp sync')", hcfg.get("manual_protocol", "audit_default.md"))
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

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
