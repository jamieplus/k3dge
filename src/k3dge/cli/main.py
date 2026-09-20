"""k3dge command-line interface."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional, Sequence

from k3dge.engine import gate_facts
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


from k3dge.cli.mcp_peers import (
    _load_tomllib,
    _warn_missing_peer_servers,
    cmd_mcp_probe,
    cmd_mcp_sync,
)

def _find_workspace(start: Optional[Path] = None, workspace_path: Optional[str] = None) -> Path:
    if workspace_path:
        p = Path(workspace_path).resolve()
        root = p if p.is_dir() else p.parent
        # 越界显式化（ADR-0006）：MCP 服务进程集 K3DGE_MCP_ROOT=启动 CWD；此参数默认须落在
        # 服务根之内——否则一个任意 workspace_path 就旁路了窗/仓物理隔离（ADR-0025 §2.7）。
        # 非 MCP 直调（CLI/测试）不设该 env，保持原语义。
        mcp_root = os.environ.get("K3DGE_MCP_ROOT", "").strip()
        allow_external = os.environ.get("K3DGE_ALLOW_EXTERNAL_WORKSPACE") == "1"
        if mcp_root and not allow_external:
            base = Path(mcp_root).resolve()
            if not (root == base or root.is_relative_to(base)):
                raise ValueError(
                    f"workspace_path 越出 MCP 服务根：{root} 不在 {base} 之内；"
                    "跨仓须显式设 K3DGE_ALLOW_EXTERNAL_WORKSPACE=1（ADR-0006）"
                )
        return root
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
                # 给进程的闭集投影（ADR-0026 §2.2）：档位 + 事实，无文案、无分支余地
                "severity": gate_facts.severity(v.rule_id),
                **({"detail": v.detail} if v.detail is not None else {}),
            }
            for v in report.violations
        ],
    }


def _workspace_hints(workspace: Path) -> list:
    """Cross-cutting [NEXT] hints from the current change set.

    These are triggers the hard gate deliberately does NOT fail on, but which
    have a file-level signal: src/ changed without overview.md touched, or a new
    top-level src/ domain not registered in manifest. Single source: the option
    text lives in engine.nextstep.STATE_OPTIONS (same table as AGENTS.md §12).
    """
    from k3dge.engine import nextstep
    from k3dge.engine.milestone_pointer import get_current_milestone

    try:
        import json as _json
        import subprocess

        out = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=workspace, capture_output=True, text=True, timeout=10,
        )
        files = [ln[3:].strip() for ln in out.stdout.splitlines() if ln.strip()]
    except Exception:
        return []
    if not files:
        return []
    mid = get_current_milestone(workspace)
    hints = []
    # Normalize: untracked dirs come back as "src/foo/" (trailing slash).
    src_changed = [f.rstrip("/") for f in files if f.startswith("src/")]
    # overview.md staleness is folded into the audit-suggestion reasons
    # (compute_audit_suggestion), so it is NOT emitted as a standalone hint here.
    # New domain: a concrete src/<domain>/... path not under any known src dir.
    # A bare "src" (whole tree untracked) is NOT a new domain — skip it.
    try:
        manifest = _json.loads((workspace / ".agent" / "manifest.json").read_text(encoding="utf-8"))
        known = {d.get("src") for d in manifest.get("domains", {}).values() if isinstance(d, dict)}
    except Exception:
        known = set()
    if known:
        new_top = set()
        for f in src_changed:
            segs = f.split("/")
            if len(segs) < 2 or not segs[1]:  # bare "src" (whole tree untracked) is not a domain
                continue
            top = "/".join(segs[:2])  # e.g. "src/k3dge" or "src/newdom"

            def _known(t: str) -> bool:
                # known if t equals, is under, OR is an ancestor of a domain src dir
                return any(
                    t == ks or t.startswith(ks + "/") or ks.startswith(t + "/")
                    for ks in known if ks
                )

            if _known(top):
                continue
            new_top.add(top)
        if new_top:
            hints.append(nextstep.NextStep.from_state("new_domain", mid))
    return hints


def _emit_workspace_hints(workspace: Path, stream) -> None:
    from k3dge.engine import nextstep

    for h in _workspace_hints(workspace):
        nextstep.emit(workspace, h, stream=stream)


def _emit_doc_audit_hint(workspace: Path, stream) -> None:
    # T-01: `check` is a static hard gate and never calls the lens. Doc-audit is a
    # NON-BLOCKING follow-up after the gate — surface it here, do not run it inline.
    try:
        from k3dge.engine import nextstep
        from k3dge.engine.doc_audit import _changed_docs
        from k3dge.engine.milestone_pointer import get_current_milestone

        if _changed_docs(workspace):
            nextstep.emit(workspace, nextstep.NextStep.from_state("doc_audit", get_current_milestone(workspace)), stream=stream)
    except Exception:
        pass


def cmd_doc_audit(args: argparse.Namespace) -> int:
    """Non-blocking post-check doc authoring audit: report (k3dit) + milestone task."""
    from k3dge.engine.doc_audit import run_doc_audit

    workspace = _find_workspace(Path.cwd())
    status, msg = run_doc_audit(workspace, io=sys.stderr)
    print(f"[DOC-AUDIT] {msg}")
    _append_log(workspace, f"[{__import__('datetime').datetime.now().isoformat()}] doc-audit -> {status}")
    return 0  # non-blocking by design (runs after check, never inside it)


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
    # Seal-eligibility hint: once the hard gate passes AND the current milestone's
    # top-level tasks are all done, surface it so the operator can choose to seal.
    # Non-blocking and informational only (ADR-0004 §2.1.2 revised).
    if code == 0:
        _emit_lifecycle_next(workspace, sys.stderr)
        _emit_workspace_hints(workspace, sys.stderr)
        _emit_doc_audit_hint(workspace, sys.stderr)
    return code


def _read_submit_input(args: argparse.Namespace) -> str:
    """Read audit-report content from --file, stdin '-', or stdin."""
    src = getattr(args, "file", None)
    if src and src != "-":
        p = Path(src)
        if not p.is_file():
            print(f"[ERROR] --file 不存在：{src}", file=sys.stderr)
            raise SystemExit(2)
        return p.read_text(encoding="utf-8")
    if src == "-":
        return sys.stdin.read()
    # No --file: read stdin if it is piped, else empty.
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


def _lifecycle_next(workspace: Path):
    """Single source of the audit/seal next-step (mirrors ADR-0004 §2.1.7).

    Order: audit closed -> seal_ready; else quant trigger -> audit_suggested.
    Returns None when nothing is warranted (empty window / zero tasks / no trigger).
    """
    # Single source moved to cli.status.lifecycle_next so the JSON/MCP exits agree
    # with this human line (ADR-0008). Imported lazily: cli.main imports cli.status.
    from k3dge.cli.status import lifecycle_next

    return lifecycle_next(workspace)


def _emit_lifecycle_next(workspace: Path, stream) -> None:
    from k3dge.engine import nextstep

    ns = _lifecycle_next(workspace)
    if ns is not None:
        nextstep.emit(workspace, ns, stream=stream)


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
    # sync handles the contract hash; overview.md is still manual — remind if the
    # change set touched src/ without overview.md.
    _emit_workspace_hints(workspace, sys.stdout)
    return 0


def cmd_extractor(args: argparse.Namespace) -> int:
    """Generate (`sync`) or inspect (`list`) `.agent/extractors/` language plugins."""
    from k3dge.engine import extractor_gen

    workspace = _find_workspace(Path.cwd())
    if args.extractor_action == "list":
        try:
            for line in extractor_gen.describe_extractors(workspace):
                print(line)
        except extractor_gen.ExtractorConfigError as exc:
            print(f"[EXTRACTOR] config error: {exc}", file=sys.stderr)
            return 1
        return 0
    # sync
    try:
        report = extractor_gen.sync_extractors(workspace)
    except extractor_gen.ExtractorConfigError as exc:
        print(f"[EXTRACTOR] config error: {exc}", file=sys.stderr)
        return 1
    for name in report["written"]:
        print(f"[EXTRACTOR] wrote .agent/extractors/{name}.py")
    for name in report["pruned"]:
        print(f"[EXTRACTOR] pruned stale .agent/extractors/{name}")
    for name, pip_cmd in report["missing"]:
        print(f"[EXTRACTOR] '{name}' needs grammar package: {pip_cmd}", file=sys.stderr)
    if not report["written"] and not report["pruned"]:
        print("[EXTRACTOR] plugins up to date.")
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
    action = getattr(args, "doc_action", None)
    if action == "list":
        from k3dge.engine.doc_catalog import list_docs

        rows = list_docs(
            workspace,
            typ=getattr(args, "doc_type", None),
            ident=getattr(args, "doc_id", None),
            q=getattr(args, "q", None),
            include_archive=getattr(args, "include_archive", False),
            include_retired=getattr(args, "include_retired", False),
        )
        if getattr(args, "as_json", False):
            print(json.dumps({"ok": True, "count": len(rows), "docs": rows}, indent=2, ensure_ascii=False))
        else:
            if getattr(args, "include_archive", False):
                print("[DOC] 低权威层：archive/ 仅为低权威留档，判定以现行视图为准")
            if getattr(args, "include_retired", False):
                print("[DOC] 退役面：obsolete/ 与退役账本（号已永久退役，无墓碑文件的看账本表）")
            if not rows:
                print("[DOC] no matches")
            for c in rows:
                mark = "\t[retired]" + (f" → {c['dest']}" if c.get("dest") else "") if c.get("retired") else ""
                print(f"{c['id']}\t{c['path']}\t{c['title']}{mark}")
        return 0
    if action == "where":
        from k3dge.engine.doc_catalog import where_doc

        rows = where_doc(workspace, args.ident)
        if getattr(args, "as_json", False):
            print(json.dumps({"ok": True, "count": len(rows), "docs": rows}, indent=2, ensure_ascii=False))
        else:
            for c in rows:
                print(c["path"])
            if not rows:
                print(f"[DOC] not found: {args.ident}", file=sys.stderr)
                return 1
        return 0
    if action == "grep":
        from k3dge.engine.doc_catalog import grep_docs

        rows = grep_docs(
            workspace,
            args.query,
            typ=getattr(args, "doc_type", None),
            line=getattr(args, "line", False),
            include_archive=getattr(args, "include_archive", False),
        )
        if getattr(args, "as_json", False):
            print(json.dumps({"ok": True, "count": len(rows), "hits": rows}, indent=2, ensure_ascii=False))
        else:
            if getattr(args, "include_archive", False):
                print("[DOC] 低权威层：archive/ 仅为低权威留档，判定以现行视图为准")
            if not rows:
                print("[DOC] no matches")
            for h in rows:
                if "line" in h:
                    print(f"{h['path']}:{h['line']}")
                else:
                    print(h["path"])
        return 0
    if action == "screen":
        # 新建受管文档的排查回执：判定归 agent（进程判不了语义覆盖），此处只记事实。
        from k3dge.engine.pure_refs import is_screenable_new_doc, record_screen_ack

        rel = args.path.strip().replace("\\", "/")
        while rel.startswith("./"):
            rel = rel[2:]
        if not is_screenable_new_doc(rel):
            print(f"[DOC] 不在排查面（确定性流程生成 / aux / archive / 非 docs）：{rel}")
            return 0
        ack = record_screen_ack(workspace, rel, into=getattr(args, "into", None))
        concl = f"merged-into {args.into}" if getattr(args, "into", None) else "new-no-overlap"
        print(f"[DOC] 排查回执已记（{concl}）：{ack.relative_to(workspace)}")
        print(f"      {rel} 本次提交放行；回执是 ephemeral（.protocol-ack/，不入库）")
        _append_log(workspace, f"[{__import__('datetime').datetime.now().isoformat()}] doc screen -> {rel} -> {concl}")
        return 0
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
        _append_log(workspace, f"[{__import__('datetime').datetime.now().isoformat()}] doc sync -> changed={changed}")
        return 0
    return 1


def cmd_task(args: argparse.Namespace) -> int:
    import datetime

    workspace = _find_workspace(Path.cwd())
    if args.task_action == "create":
        from k3dge.engine.doc_audit import _similar_task_hints
        from k3dge.engine.task_write import create_task

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
        if ok and path is not None:
            hints = _similar_task_hints(workspace, title, exclude=path)
            if hints:
                # 档位与文案查声明面（gate_facts），CLI 不自己写散文；候选是事实，逐条列
                print(gate_facts.render("DUP_CHECK", {"count": len(hints)}), file=sys.stdout)
                print("  candidates:", file=sys.stdout)
                for hp, ht in hints:
                    print(f"    - {hp}" + (f" — {ht}" if ht else ""), file=sys.stdout)
        _append_log(workspace, f"[{datetime.datetime.now().isoformat()}] task create -> {msg}")
        return 0 if ok else 1
    if args.task_action == "done":
        from k3dge.engine.task_write import mark_task_done

        raw_pat = args.task_id if args.task_id is not None else args.title
        if not raw_pat:
            print("[TASK] done requires path from 'task list' or unique filename substring", file=sys.stderr)
            return 1
        ok, msg, _ = mark_task_done(workspace, raw_pat)
        print(f"[TASK] {msg}", file=sys.stderr if not ok else sys.stdout)
        _append_log(workspace, f"[{datetime.datetime.now().isoformat()}] task done -> {msg}")
        if ok:
            # Turning point: completing the batch is a *quantitative* event ->
            # suggest an audit (not seal); seal appears only after the audit closes.
            _emit_lifecycle_next(workspace, sys.stdout)
        return 0 if ok else 1
    if args.task_action == "list":
        from k3dge.engine.task_index import list_tasks

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
    except Exception as exc:
        print(f"[WARN] init: sync_all failed ({exc}); run 'k3dge sync' in {target} manually", file=sys.stderr)
    print(f"[INIT] Successfully initialized k3dge harness in {target}")
    return 0


def cmd_mcp(args: argparse.Namespace) -> int:
    workspace = _find_workspace(Path.cwd())
    if args.mcp_action == "sync":
        return cmd_mcp_sync(workspace)
    if args.mcp_action == "probe":
        return cmd_mcp_probe(args, workspace)
    return 1


def cmd_audit(args: argparse.Namespace) -> int:
    """审计线动词（工作区=CWD）：submit 锁线建单 / status 问对端 / show 读本地账 /
    advance 提版重钉基线 / materialize 只读物化 / close 取回落盘（closure merge 自动附带）。"""
    from k3dge.engine import audit_flow

    workspace = _find_workspace(Path.cwd())
    tok = args.job_or_milestone
    if args.audit_action == "submit":
        r = audit_flow.submit_audit(workspace, args.milestone, targets=args.target or None)
    elif args.audit_action == "status":
        r = audit_flow.peer_status(workspace, tok)
    elif args.audit_action == "show":
        r = audit_flow.show_job(workspace, tok or "")
    elif args.audit_action == "materialize":
        r = audit_flow.materialize(workspace, tok or "", getattr(args, "oid", "") or "",
                                   getattr(args, "dest", "") or "")
    elif args.audit_action == "advance":
        r = audit_flow.advance_line(workspace, tok or "adhoc",
                                    by=getattr(args, "by", "") or "manual")  # 提版+重钉+推 present
    else:
        r = audit_flow.collect_audit(workspace, tok, args.job or None)
    print(json.dumps({k: v for k, v in r.items() if k in
                      ("ok", "state", "failed", "detail", "job_id", "jobs", "counts", "pending",
                       "baseline_ok", "report", "merge", "commit", "baseline", "by", "repinned",
                       "present_pushed", "pushed", "rev", "dest", "recent_downgrades",
                       "error", "message")},
                     ensure_ascii=False))
    return 0 if r.get("ok") else 1


def cmd_markers(args: argparse.Namespace) -> int:
    """树侧 findings 一览：三锚点计数、语法违规、结项判据（只读；从不改写）。"""
    import sys as _sys

    from k3dge.engine.markers import closure_ok, counts, extract, open_samples

    workspace = _find_workspace(Path.cwd())
    ms, problems = extract(workspace)
    c = counts(ms)
    ok_close, detail = closure_ok(ms)
    if getattr(args, "json", False):
        print(json.dumps({"counts": c, "blockers": detail["blockers"], "problems": problems,
                          "samples": open_samples(ms), "closure_ok": ok_close,
                          "markers": [
                              {"file": x.file, "line": x.line, "kind": x.kind, "id": x.id,
                               "scope": x.scope, "note": x.note}
                              for x in ms
                          ]},
                         indent=2, ensure_ascii=False))
    else:
        print(f"findings: pending={c['pending']} disputed={c['disputed']} fixnote={c['fixnote']} "
              f"leftover={c['leftover']} | open={c['open']}")
        for s_ in open_samples(ms)[:20]:
            print(f"  - {s_}")
        for pr in problems[:20]:
            print(f"  PROBLEM {pr}", file=_sys.stderr)
        if not problems:
            print("语法/锚点校验：无违规")
    if getattr(args, "check", False):
        return 1 if problems else 0
    return 0



def cmd_milestone(args: argparse.Namespace) -> int:
    from k3dge.engine import nextstep
    from k3dge.engine.align import run_milestone_alignment
    from k3dge.engine.milestone_audit import persist_external_audit_report, run_audit_flow
    from k3dge.engine.prompt import Prompt as _Prompt
    from k3dge.engine.seal import seal_milestone
    from k3dge.engine.seal_flow import run_seal_flow
    from k3dge.engine.task_index import scan_milestone_tasks

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
        if ok:
            # align done + all tasks closed => suggest AUDIT (not seal).
            _emit_lifecycle_next(workspace, sys.stdout)
        else:
            # Failure -> action (do not proceed to seal).
            nextstep.emit(workspace, nextstep.next_for_rejection(m_id, msg), stream=sys.stdout)
        _append_log(workspace, f"[{__import__('datetime').datetime.now().isoformat()}] milestone align -> {m_id} ok={ok}")
        # Peer pipeline availability check: highlight fallback to default when external peer missing
        if ok:
            try:
                tomllib_mod2 = _load_tomllib()
                if tomllib_mod2 is not None:
                    cfg_path2 = workspace / ".agent" / "pipeline.toml"
                    if cfg_path2.is_file():
                        cfg2 = tomllib_mod2.loads(cfg_path2.read_text(encoding="utf-8"))
                        _warn_missing_peer_servers(workspace, cfg2)
            except Exception:
                pass
        return 0 if ok else 1

    if action == "checklist":
        from k3dge.engine import audit_checklist

        data = audit_checklist.build_checklist(workspace, m_id)
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    if action == "audit-submit":
        raw = _read_submit_input(args)
        if not raw or not raw.strip():
            print("[AUDIT] no content provided (use --file <path> or pipe via stdin '-')", file=sys.stderr)
            return 1
        path = persist_external_audit_report(workspace, m_id, raw, kind=getattr(args, "kind", "audit") or "audit")
        print(f"[AUDIT] persisted external audit report -> {path}")
        _append_log(workspace, f"[{__import__('datetime').datetime.now().isoformat()}] milestone audit-submit -> {m_id} -> {path}")
        # Landed report may close the audit loop -> unlock the seal question.
        _emit_lifecycle_next(workspace, sys.stdout)
        return 0

    if action == "audit":
        status, msg = run_audit_flow(workspace, m_id, prompter=_Prompt.default())
        print(msg)
        _append_log(workspace, f"[{__import__('datetime').datetime.now().isoformat()}] milestone audit -> {m_id} status={status}")
        return 0 if status == "audited" else 1

    if action == "seal":
        status, msg = run_seal_flow(
            workspace,
            m_id,
            prompter=_Prompt.default(),
            skip_enter_prompt=getattr(args, "yes", False),
        )
        print(msg)
        _append_log(workspace, f"[{__import__('datetime').datetime.now().isoformat()}] milestone seal -> {m_id} status={status}")
        if status != "sealed":
            # seal_declined (normal commit) or audit_needed/rejected -> no version bump
            return 0 if status == "seal_declined" else 1
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


_ATTEST_PREFIX = "k3dge-commit: "
_ATTEST_DEFAULT_SECRET = "k3dge-local-attest-v1"
_ATTEST_WORDLIST = [
    "aura", "brick", "cedar", "delta", "ember", "flux", "glyph", "haven",
    "iris", "jolt", "kiwi", "lumen", "moss", "nexus", "onyx", "prism",
    "quill", "rune", "sage", "tide", "umber", "vault", "wisp", "xenon",
    "yarn", "zephyr",
]


def _attest_secret() -> str:
    return os.environ.get("K3DGE_ATTEST_SECRET") or _ATTEST_DEFAULT_SECRET


def _attest_tree_hash(workspace: Path) -> str:
    import subprocess

    return subprocess.run(
        ["git", "write-tree"], cwd=workspace, capture_output=True, text=True
    ).stdout.strip()


def _attest_utc_minute(when_iso: str) -> datetime | None:
    """Parse an ISO committer/generator stamp into an aware UTC datetime (naive = UTC)."""
    from datetime import datetime, timezone

    ts = (when_iso or "").strip()
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00").replace("z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _attest_window(when_iso: str) -> str:
    # code-1: `%cI` carries the committer's local offset while generation stamps UTC;
    # cut the minute window *after* normalising to UTC or the two sides never agree.
    dt = _attest_utc_minute(when_iso)
    if dt is None:
        return when_iso[:16]  # unparsable legacy stamp: keep the old slice
    return dt.strftime("%Y-%m-%dT%H:%M")  # minute precision — binds the token to a time window


def _attest_windows(when_iso: str) -> list:
    """Candidate windows: the commit minute plus the minute before it.

    The token is minted *before* `git commit` runs, so a stamp taken at HH:MM:59.9
    can land in a commit dated HH:MM+1:00; accepting only the exact minute made that
    boundary race fail verification.
    """
    from datetime import timedelta

    dt = _attest_utc_minute(when_iso)
    if dt is None:
        return [when_iso[:16]]
    base = dt.replace(second=0, microsecond=0)
    return [base.strftime("%Y-%m-%dT%H:%M"), (base - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M")]


def _attest_token(workspace: Path, when_iso: str) -> str:
    secret = _attest_secret()
    tree = _attest_tree_hash(workspace)
    window = _attest_window(when_iso)
    digest = hashlib.sha256(f"{secret}|{window}|{tree}".encode()).hexdigest()
    return _ATTEST_WORDLIST[int(digest, 16) % len(_ATTEST_WORDLIST)]


def _attest_line(workspace: Path) -> str:
    """Lightweight commit attestation: who + when + time-bound dictionary token.

    The token = word(hash(secret + minute-window + tree)). It proves the line came
    from the governed path *if* the secret is set via K3DGE_ATTEST_SECRET (raw
    `git commit` has no secret to compute it). Without the env secret it falls back
    to a built-in constant — a deterrent, not a proof. CI recomputes and compares.
    """
    import getpass
    import subprocess
    from datetime import datetime, timezone

    who = ""
    try:
        who = subprocess.run(
            ["git", "config", "user.name"], cwd=workspace, capture_output=True, text=True
        ).stdout.strip()
    except Exception:
        who = ""
    if not who:
        who = getpass.getuser()
    when = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    token = _attest_token(workspace, when)
    return f"{_ATTEST_PREFIX}{who} @ {when} #{token}"


def _rel_within_workspace(workspace: Path, p: str) -> Path:
    """SEC-01: resolve a user path and ensure it stays inside the workspace."""
    target = (workspace / p).resolve()
    try:
        target.relative_to(workspace.resolve())
    except ValueError as exc:
        raise ValueError(f"path '{p}' escapes workspace root (SEC-01)") from exc
    return target


def cmd_search(args: argparse.Namespace) -> int:
    from k3dge.engine.search import search

    workspace = _find_workspace(Path.cwd())
    if getattr(args, "path", None):
        # Path-listing mode: list files matching the glob (scoped alternative to `find`).
        matches = []
        for p in workspace.glob(args.path):
            try:
                safe = _rel_within_workspace(workspace, str(p))
            except ValueError:
                continue  # SEC-01: `../*` or symlink escape -> drop
            if safe.is_file():
                matches.append(safe.relative_to(workspace.resolve()).as_posix())
        for m in sorted(matches):
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


def cmd_index(args: argparse.Namespace) -> int:
    from k3dge.engine.search import write_symbol_index

    workspace = _find_workspace(Path.cwd())
    out = write_symbol_index(workspace)
    print(f"[INDEX] wrote {out.relative_to(workspace)}")
    return 0


def cmd_commit(args: argparse.Namespace) -> int:
    import subprocess

    from k3dge.engine.evaluator import ConsistencyEngine

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
    # 3) gate (blocking)
    report = ConsistencyEngine(workspace).evaluate(staged=True, run_tests=args.with_tests)
    if not report.passed:
        print(report.render())
        return 1
    # 5) commit; --no-verify bypasses the live hook (which would re-run the same gate).
    #    Self-attach the attestation trailer so k3dge commits are signed like hook commits.
    msg = args.message
    if _ATTEST_PREFIX not in msg:
        msg = f"{msg}\n\n{_attest_line(workspace)}"
    res = subprocess.run(
        ["git", "commit", "-m", msg, "--no-verify"],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        print(res.stderr or res.stdout, file=sys.stderr)
        return 1
    print(res.stdout)
    return 0


def cmd_commit_attest(args: argparse.Namespace) -> int:
    """Print the attestation trailer line for the live commit-msg hook to append."""
    print(_attest_line(_find_workspace(Path.cwd())))
    return 0


_ATTEST_RE = re.compile(r"^k3dge-commit: (.+?) @ (.+?) #([a-z]+)$")


def cmd_verify_attest(args: argparse.Namespace) -> int:
    """Verify a commit's attestation token (used by CI)."""
    import subprocess

    workspace = _find_workspace(Path.cwd())
    h = args.commit
    tree = subprocess.run(
        ["git", "rev-parse", f"{h}^{{tree}}"], cwd=workspace, capture_output=True, text=True
    ).stdout.strip()
    when_iso = subprocess.run(
        ["git", "show", "-s", "--format=%cI", h], cwd=workspace, capture_output=True, text=True
    ).stdout.strip()
    body = subprocess.run(
        ["git", "log", "-1", "--format=%B", h], cwd=workspace, capture_output=True, text=True
    ).stdout
    m = None
    for line in body.splitlines():
        m = _ATTEST_RE.match(line.strip())
        if m:
            break
    if not m:
        print(f"[ATTEST] commit {h} missing attestation line", file=sys.stderr)
        return 1
    who, when, token = m.group(1), m.group(2), m.group(3)
    secret = _attest_secret()
    expected = [
        _ATTEST_WORDLIST[
            int(hashlib.sha256(f"{secret}|{w}|{tree}".encode()).hexdigest(), 16)
            % len(_ATTEST_WORDLIST)
        ]
        for w in _attest_windows(when)
    ]
    if token not in expected:
        print(
            f"[ATTEST] commit {h} token mismatch (got '{token}', expected '{expected[0]}') "
            f"-- attestation was not produced by the governed path",
            file=sys.stderr,
        )
        return 1
    print(f"[ATTEST] commit {h} OK ({who} @ {when})")
    return 0


def cmd_check_msg(args: argparse.Namespace) -> int:
    from pathlib import Path

    msg = Path(args.file).read_text(encoding="utf-8").strip()
    if not _conventional_ok(msg):
        print(
            f"[COMMIT] message is not Conventional Commits (e.g. 'feat: ...')",
            file=sys.stderr,
        )
        return 1
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


def cmd_status(args: argparse.Namespace) -> int:
    """Read-only synthesized workspace state (delegates to cli.status.workspace_status)."""
    import sys

    from k3dge.cli.status import workspace_status

    workspace = _find_workspace()
    status_obj = workspace_status(workspace)
    if not status_obj.get("ok", True):
        print(f"[STATUS] {status_obj.get('error')}: {status_obj.get('message')}", file=sys.stderr)
        return 1
    if getattr(args, "json", False):
        print(json.dumps(status_obj, indent=2, ensure_ascii=False))
    else:
        print(f"Domains: {', '.join(status_obj['domains'])}")
        print(f"Gate: {'PASS' if status_obj['gate_passed'] else 'FAIL'}")
        if status_obj["drift"]:
            print("Contract drift:")
            for d in status_obj["drift"]:
                print(f"  - {d['domain']}: {d['symbol_diff']}")
        else:
            print("Contract drift: none")
        print(
            f"Pipeline: {'configured' if status_obj['pipeline']['configured'] else 'absent'}"
            + (f" ({len(status_obj['pipeline']['issues'])} issue(s))" if status_obj["pipeline"]["issues"] else "")
        )
        if status_obj["unfinished_tasks"]:
            from k3dge.engine import gates as _gates

            tasks = status_obj["unfinished_tasks"]
            cap = int(_gates.get(workspace, "output", "default_lines"))
            shown = tasks if getattr(args, "deep", False) else tasks[:cap]
            print(f"Unfinished tasks ({len(tasks)}):")
            for t in shown:
                print(f"  - [{t['status'] or '?'}] {t['title']}")
            if len(tasks) > len(shown):
                print(f"  … {len(tasks) - len(shown)} more (k3dge status --deep)")
        else:
            print("Unfinished tasks: none")
        dag = status_obj.get("task_dag") or {}
        dangling = dag.get("blocking_dangling") or {}
        closed_refs = dangling.get("closed") or []
        unknown_refs = dangling.get("unknown") or []
        if closed_refs or unknown_refs or (dag.get("blocking_cycles") or {}).get("cyclic"):
            print("blocking 观测（事实，不判定）：")
            if (dag.get("blocking_cycles") or {}).get("cyclic"):
                print(f"  - 有互阻环：{(dag.get('blocking_cycles') or {}).get('detail')}")
            for r in closed_refs:
                print(f"  - 指向已关票，引用该清：{r}")
            for r in unknown_refs:
                print(f"  - 指向不存在的票：{r}")
        cache = status_obj.get("cache")
        if cache:
            hr = cache.get("hit_rate")
            print(
                "Cache (k3che): "
                f"{cache.get('total', 0)} queries, hits {cache.get('hits', 0)}"
                + (f", hit_rate {round(hr, 2)}" if isinstance(hr, (int, float)) else "")
                + (f", indexed {cache.get('indexed')}" if cache.get("indexed") is not None else "")
                + " —— 观测展示，不参与任何判定",
                file=sys.stdout,
            )
        # Persistent one-line next-step hint (single source: engine.nextstep).
        _emit_lifecycle_next(workspace, sys.stdout)
        _emit_workspace_hints(workspace, sys.stdout)
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

    p_extractor = sub.add_parser("extractor", help="language extractor plugins (generate/list)")
    p_extractor.add_argument("extractor_action", choices=["sync", "list"], help="extractor action")
    p_extractor.set_defaults(func=cmd_extractor)

    p_milestone = sub.add_parser("milestone", help="milestone alignment and context compaction")
    p_milestone.add_argument("action", choices=["status", "align", "seal", "audit", "checklist", "audit-submit"], help="milestone action")
    p_milestone.add_argument("milestone_id", help="milestone identifier (matches Milestone field in tasks)")
    p_milestone.add_argument(
        "--no-version-bump",
        action="store_true",
        help="for seal: do not auto-bump patch version and changelog",
    )
    p_milestone.add_argument(
        "--file",
        default=None,
        help="for audit-submit: path to the audit report file; '-' or omitted reads stdin",
    )
    p_milestone.add_argument(
        "--kind",
        choices=["audit", "quality"],
        default="audit",
        help="for audit-submit: report stream (`audit`; `quality` is a legacy kind for pre-merge reports)",
    )
    p_milestone.add_argument(
        "--yes",
        action="store_true",
        help="for seal: skip the enter-seal prompt and enter the flow immediately (audit still mandatory)",
    )
    p_milestone.set_defaults(func=cmd_milestone)

    p_doc_audit = sub.add_parser(
        "doc-audit",
        help="non-blocking doc authoring audit that runs AFTER check: k3dit report + milestone task",
    )
    p_doc_audit.set_defaults(func=cmd_doc_audit)

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

    p_doc = sub.add_parser("doc", help="doc catalog (list/where), body grep (path only), screen, sync")
    doc_sub = p_doc.add_subparsers(dest="doc_action", required=True)
    p_doc_sync = doc_sub.add_parser("sync", help="regenerate specs + generated docs")
    p_doc_sync.set_defaults(func=cmd_doc)
    p_doc_list = doc_sub.add_parser("list", help="thin catalog cards (no bodies); do not grep docs/")
    p_doc_list.add_argument("--type", dest="doc_type", default=None, help="docs/<type>/ filter")
    p_doc_list.add_argument("--id", dest="doc_id", default=None, help="exact id (ADR-0001, INC-...)")
    p_doc_list.add_argument("-q", dest="q", default=None, help="substring on id/title/tokens")
    p_doc_list.add_argument("--include-archive", action="store_true")
    p_doc_list.add_argument("--include-retired", dest="include_retired", action="store_true",
                            help="含退役面（obsolete/ 文件 + 退役账本表；默认只列现行）")
    p_doc_list.add_argument("--json", dest="as_json", action="store_true")
    p_doc_list.set_defaults(func=cmd_doc)
    p_doc_where = doc_sub.add_parser("where", help="resolve a doc id to path")
    p_doc_where.add_argument("ident", help="ADR-0001 / INC-... / task stem")
    p_doc_where.add_argument("--json", dest="as_json", action="store_true")
    p_doc_where.set_defaults(func=cmd_doc)
    p_doc_grep = doc_sub.add_parser(
        "grep",
        help="scan doc bodies; print path (or path:line with --line); never snippets",
    )
    p_doc_grep.add_argument("query", help="regex; invalid patterns used as literals")
    p_doc_grep.add_argument("--type", dest="doc_type", default=None)
    p_doc_grep.add_argument("--line", action="store_true", help="include line numbers; still no text")
    p_doc_grep.add_argument("--include-archive", action="store_true")
    p_doc_grep.add_argument("--json", dest="as_json", action="store_true")
    p_doc_grep.set_defaults(func=cmd_doc)
    p_doc_screen = doc_sub.add_parser(
        "screen",
        help="新建受管文档的重复/覆盖排查回执（解 pre-commit 的 DOC_NEW_UNSCREENED 阻断）",
    )
    p_doc_screen.add_argument("path", help="新建文档路径（docs/<type>/<file>.md）")
    p_doc_screen.add_argument("--into", default=None, help="若结论是并入：目标文档路径")
    p_doc_screen.set_defaults(func=cmd_doc)

    p_init = sub.add_parser("init", help="initialize k3dge harness in target directory")
    p_init.add_argument("target", nargs="?", default=".", help="target directory (default: current working dir)")
    p_init.add_argument("--name", dest="name", default=None, help="initial domain name (default: directory name)")
    p_init.set_defaults(func=cmd_init)

    p_mcp = sub.add_parser("mcp", help="MCP config")
    p_mcp.add_argument("mcp_action", choices=["sync", "probe"], help="mcp action")
    p_mcp.add_argument("--timeout", type=int, default=20, help="probe: per-server handshake timeout (s)")
    p_mcp.add_argument("--json", dest="json", action="store_true", help="probe: emit JSON")

    p_mk = sub.add_parser("markers", help="审计钉一览（只读：计数/违规/结项判据）")
    p_mk.add_argument("--json", action="store_true")
    p_mk.add_argument("--check", action="store_true", help="有语法/锚点违规时退出码 1（供 CI）")
    p_mk.set_defaults(func=cmd_markers)

    p_aud = sub.add_parser("audit", help="审计线棘轮：submit/status/show/advance/materialize/close（ADR-0025；工作区=CWD）")
    p_aud.add_argument("audit_action", choices=["submit", "status", "show", "advance", "materialize", "close"])
    p_aud.add_argument("job_or_milestone", nargs="?", default="", help="status/show/materialize:job_id 或里程碑；advance:线名；close:milestone")
    p_aud.add_argument("--milestone", default="", help="submit：挂里程碑 id")
    p_aud.add_argument("--target", action="append", default=[], help="submit：送检路径（可多次）")
    p_aud.add_argument("--job", default="", help="close：指定 job id（默认取该里程碑最新在办单）")
    p_aud.add_argument("--by", default="manual", help="advance：调用方身份（hall/修席窗/人），落账可审计")
    p_aud.add_argument("--oid", default="", help="materialize：版本（缺=在办单基线）")
    p_aud.add_argument("--dest", default="", help="materialize：物化目录（默认 .k3dge/mat/<单>/<oid12>）")
    p_aud.set_defaults(func=cmd_audit)
    p_mcp.set_defaults(func=cmd_mcp)

    p_search = sub.add_parser("search", help="controlled search (scoped, narrow-context alternative to grep/find)")
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

    p_index = sub.add_parser("index", help="rebuild the symbol index (docs/generated/symbol-index.json)")
    p_index.set_defaults(func=cmd_index)

    p_commit = sub.add_parser("commit", help="convenience commit: gate + attestation sign")
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

    p_status = sub.add_parser(
        "status",
        help="synthesized workspace state: domains / drift / pipeline / unfinished tasks",
    )
    p_status.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    p_status.add_argument("--deep", action="store_true",
                          help="show full unfinished task list (default: first 10, ADR-0008 §2)")
    p_status.set_defaults(func=cmd_status)

    # Hidden hooks used by the live git hooks (scripts/pre-commit, scripts/commit-msg).
    # Not advertised: they give raw `git commit` the same convention + attestation
    # coverage as `k3dge commit`, making `k3dge commit` a pure convenience wrapper.
    p_cm = sub.add_parser("check-msg", help=argparse.SUPPRESS)
    p_cm.add_argument("--file", dest="file", required=True, help="path to commit message file")
    p_cm.set_defaults(func=cmd_check_msg)
    p_catt = sub.add_parser("commit-attest", help=argparse.SUPPRESS)
    p_catt.set_defaults(func=cmd_commit_attest)
    p_vatt = sub.add_parser("verify-attest", help=argparse.SUPPRESS)
    p_vatt.add_argument("--commit", dest="commit", required=True, help="commit hash/tree-ish")
    p_vatt.set_defaults(func=cmd_verify_attest)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
