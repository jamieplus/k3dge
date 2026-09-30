"""k3dge command-line interface."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import List, Optional, Sequence

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


def _collect_hints(workspace: Path) -> list:
    """本轮全部处理点（**不打印、不写盘**）：生命周期 + 工作区 + 规约化三类。"""
    from k3dge.engine import nextstep
    from k3dge.engine.milestone_pointer import get_current_milestone

    steps = []
    ns = _lifecycle_next(workspace)
    if ns is not None:
        steps.append(ns)
    steps.extend(_workspace_hints(workspace))
    try:
        # 可确定修的规约偏差 ⇒ 主动动作（ADR-0022 §2.2：内容规约化，封板前做完）
        from k3dge.engine import doc_fix

        dev = doc_fix.scan(workspace)
        if dev:
            ns = nextstep.NextStep.from_state("doc_fix", get_current_milestone(workspace) or "")
            ns.fact = (ns.fact or "").replace("<n>", str(len(dev))).replace(
                "<rules>", "、".join(sorted({d["rule"] for d in dev})))
            steps.append(ns)
    except Exception:
        pass
    return steps


def _emit_all_hints(workspace: Path, stream) -> None:
    """多处理点：按 priority 排序后统一打印 + 侧车写全量（`primary` ＝ 最小 priority）。

    实测场景：`k3dge check` 同轮可命中 `pending_findings`(1) + `doc_fix`(2) + `seal_ready`(4)
    ⇒ 旧实现各自 `emit`，stdout 顺序＝代码顺序、侧车只剩最后一条。
    """
    from k3dge.engine import nextstep

    nextstep.emit_all(workspace, _collect_hints(workspace), stream=stream)


def _emit_workspace_hints(workspace: Path, stream) -> None:
    from k3dge.engine import nextstep

    for h in _workspace_hints(workspace):
        nextstep.emit(workspace, h, stream=stream)


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
        _emit_all_hints(workspace, sys.stderr)   # 三类汇总，按 priority 排序
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
        # 陈述事实：契约无变化 ≠ 本轮没写盘（docs-index 每次 sync 都会重生，见 sync_docs_index）。
        print("[SYNC] No spec contract changes (derived docs/index are rewritten only when stale).")
        _append_log(workspace, f"[{datetime.datetime.now().isoformat()}] sync -> no-contract-changes")
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
            # 版号已前进、CHANGELOG 没写 ⇒ 漂移态不得记成"成功"（CI/hook/`k3dge commit` 看到 0 会以为同步完成，ocr-178）。
            print(f"[VERSION] bumped to {new_v} but changelog failed: {exc}", file=sys.stderr)
            print(f"[VERSION] 需人工补 CHANGELOG 段 {new_v}（或回退 bump）", file=sys.stderr)
            return 1
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
        from k3dge.engine.pure_refs import (
            is_screenable_new_doc,
            record_screen_ack,
            screen_target_exists,
        )

        rel = args.path.strip().replace("\\", "/")
        while rel.startswith("./"):
            rel = rel[2:]
        if not is_screenable_new_doc(rel):
            print(f"[DOC] 不在排查面（确定性流程生成 / aux / archive / 非 docs）：{rel}")
            return 0
        into = getattr(args, "into", None)
        if into and not screen_target_exists(workspace, into):
            # 回执声称"并入 X"，X 必须存在——否则记的是不存在的去向（C 线残渣）
            print(f"[DOC] --into 指向的文件不存在：{into}", file=sys.stderr)
            return 1
        ack = record_screen_ack(workspace, rel, into=into)
        concl = f"merged-into {args.into}" if getattr(args, "into", None) else "new-no-overlap"
        print(f"[DOC] 排查回执已记（{concl}）：{ack.relative_to(workspace)}")
        print(f"      {rel} 本次提交放行；回执是 ephemeral（.protocol-ack/，不入库）")
        _append_log(workspace, f"[{__import__('datetime').datetime.now().isoformat()}] doc screen -> {rel} -> {concl}")
        return 0
    if action == "fix":
        # 主动动作：按闭集规则规范化受管文档（幂等；--dry-run 只报不改）
        from k3dge.engine import doc_fix

        dry = bool(getattr(args, "dry_run", False))
        report = doc_fix.apply(workspace, dry_run=dry)
        n = len(report["fixed"])
        files = report["changed_files"]
        print(f"[DOC] {'dry-run：将修' if dry else '已修'} {n} 处（{len(files)} 个文件）"
              + ("" if dry else "；请 review diff 后提交"))
        for f in report["fixed"][:20]:
            print(f"  - [{f['rule']}] {f['path']}")
        if len(report["fixed"]) > 20:
            print(f"  … {len(report['fixed']) - 20} more")
        if report.get("remaining"):
            print(f"  ! {report['remaining']} 处检测到但未能改（需人处理）")
        _append_log(workspace, f"[{__import__('datetime').datetime.now().isoformat()}] doc fix -> fixed={n} dry_run={dry}")
        return 0 if not report.get("remaining") else 1
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
        from k3dge.engine.task_write import _similar_task_hints
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
    workspace = _find_workspace(Path.cwd())
    tok = args.job_or_milestone
    if args.audit_action != "bundle":
        print("[AUDIT] 对等审计线动词（submit/status/show/advance/materialize/close）已退休"
              "（2026-09-26）：k3dit 是本地命令行工具 ⇒ 用 `k3dge audit bundle --run`。", file=sys.stderr)
        return 1
    from k3dge.engine import audit_bundle as ab

    bundle = Path(tok) if tok else Path(getattr(args, "bundle_out", "") or (workspace / ".k3dit" / "bundle"))
    if getattr(args, "run", False) or not (bundle / "manifest.json").is_file():
        out_dir = Path(getattr(args, "bundle_out", "") or bundle)
        _m = getattr(args, "bundle_mode", "full") or "full"
        _tmo = int(getattr(args, "bundle_timeout", 0) or 0) or (7200 if _m == "full" else 3600)
        ran = ab.run_path_audit(workspace, out_dir, mode=_m,
                                pins=getattr(args, "bundle_pins", "inplace") or "inplace",
                                scope=getattr(args, "bundle_scope", "") or "", timeout=_tmo)
        print(json.dumps({"stage": "run", "out": str(out_dir), "rc": ran.get("rc"), "ok": ran.get("ok"),
                          "payload": ran.get("payload"), "detail": ran.get("detail")}, ensure_ascii=False))
        if not ran.get("ok"):
            # **抢救**（用户裁定：超时也要出报告）：工具被掐断 ⇒ `k3dit hall export --latest` 出"未完成导出"包
            _salv = ab.salvage_bundle(workspace, out_dir)
            _dig = ab.write_run_digest(out_dir, stage=("salvage-ok" if _salv.get("ok") else "run-failed"),
                                       rc=ran.get("rc"), detail=(ran.get("detail") or "")[:400],
                                       salvage_rc=_salv.get("rc"), salvage_detail=_salv.get("detail", ""))
            print(json.dumps({"stage": "salvage", "ok": _salv.get("ok"), "rc": _salv.get("rc"),
                              "digest": _dig, "detail": _salv.get("detail", "")}, ensure_ascii=False),
                  file=sys.stderr)
            if not _salv.get("ok"):
                return 1
        bundle = out_dir
    target = Path(getattr(args, "into", "") or workspace).resolve()
    res = ab.consume(target, bundle, dry_run=bool(getattr(args, "dry_run", False)),
                     expect_input=str(target),
                     # 纯审计包 status=partial 是设计（钉留树）⇒ 不要求闭环
                     require_closed=(getattr(args, "bundle_mode", "full") or "full") != "audit-only",
                     accept_baseline_drift=getattr(args, "bundle_drift", "") or "",
                     exclude=getattr(args, "bundle_exclude", None) or [],
                     landing=getattr(args, "bundle_landing", "partial") or "partial")
    # **入口唯一＝效果唯一**（ADR-0025 §2.9.6）：手动入口与封板腿共用 `land_report`，
    # 否则"同一模块同一参数"只是形式——手动跑完报告不落盘、不提交（此前如此），判定面看不到产物。
    landed = {}
    # **补丁没落成，就不落报告**：报告里的「已修 N」是**产出方对自己场地的处置**，修复没进本仓时把它落进
    # `docs/reviews/` 会被判定面当成"本仓已修"（真跑实测：落补丁失败仍落了 26 行"24 已修"的报告并提交）。
    # 证据不丢：包留在 out，拒绝信息里给出路径。
    # 只在"**验包通过 + 补丁落成**"时落报告：验包失败或空转轮（未产出判定）⇒ 报告留在包内，
    # `docs/reviews/` 只放**审计结果**，不放"这轮什么都没产出"的运行痕迹。
    _no_apply = not (bool(res.get("ok")) and bool((res.get("apply") or {}).get("ok")))
    if not getattr(args, "dry_run", False) and not _no_apply:
        # 里程碑 id **必须**来自显式参数（缺省 `local`，与 k3dit 的约定一致）：绝不能用**包路径**当 id
        #（真跑实测：`/tmp/ctl` 被 `persist_external_audit_report` 拒 ⇒ 钉已落、报告没落、提交没做）。
        _ap = res.get("apply") or {}
        _note = ""
        if _ap.get("strategy") == "three-way-merge":
            _note = (f"> **落地方式**：`git apply` 与当前主干冲突 ⇒ **三路合并**（base＝包的可重放基线）落树；"
                     f"落库后校验（`post_apply_check`）通过。"
                     + (f"\n> **排除**：{', '.join(_ap.get('excluded') or [])}"
                        f"（其修复与主干/现测试冲突，**未落**，需人工重做）。" if _ap.get("excluded") else ""))
        landed = ab.land_report(target, (getattr(args, "bundle_milestone", "") or "local"), bundle,
                                extra_files=list(_ap.get("files") or []),
                                why=f"手动入口 包 {str(ab.bundle_digest(bundle))[:12]}", note=_note,
                                excluded=list(_ap.get("excluded") or []))
    if _no_apply:
        print(f"[AUDIT] 补丁未落（{(res.get('apply') or {}).get('error')}）⇒ **不落报告**："
              f"报告留在包内 {bundle}", file=sys.stderr)
    print(json.dumps({**res, "landed": landed}, ensure_ascii=False))
    _append_log(workspace, f"[{__import__('datetime').datetime.now().isoformat()}] audit bundle "
                           f"{bundle} ok={res.get('ok')} dry={bool(getattr(args, 'dry_run', False))} "
                           f"report={landed.get('report', '')} commit={landed.get('commit', '')}")
    if landed and not landed.get("ok"):
        print(f"[AUDIT] 落报告/提交失败：{landed.get('error')} {landed.get('detail') or ''}", file=sys.stderr)
        return 1
    return 0 if res.get("ok") else 1


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

    if action == "seal-check":
        # 只读：打印全量封板前置清单（不执行任何动作）；有未过项 ⇒ 退 1
        from k3dge.engine.seal import render_checklist, unmet_seal_preconditions

        print(render_checklist(workspace, m_id))
        # durable 证据（ADR-0004 §2.1.10）：判据只认 git 事实（边界 tag + 封版提交 trailer）；
        # 本地账（audit_jobs/audit_checklist）是运行态投影 ⇒ 冲突以 git 为准。此处只陈述事实，
        # 不是闸（报告是可选产物），所以它**不影响**退出码。

        from k3dge.engine.audit_flow import audit_evidence

        ev = audit_evidence(workspace, m_id)
        tag = ev["tag"][:12] if ev["tag"] else "-"
        print(f"[EVIDENCE] 边界 tag {m_id} = {tag}；封版记录 "
              f"{'齐（' + ', '.join(f'{k}={v}' for k, v in ev['trailers'].items()) + '）' if ev['sealed'] else '缺'}"
              f" —— 本地账不作判据（git 事实优先）")
        _append_log(workspace, f"[{__import__('datetime').datetime.now().isoformat()}] milestone seal-check -> {m_id} unmet={len(unmet_seal_preconditions(workspace, m_id))}")
        return 1 if unmet_seal_preconditions(workspace, m_id) else 0

    if action == "reassign":
        # 重挂（ADR-0004 §2.1.9：B 之后的改动归下一个里程碑）：只改票的里程碑事实
        #（frontmatter + 文件名 M 段，同一次两处同改；闸 TASK_MILESTONE_MISMATCH 兜底）
        from k3dge.engine.task_write import reassign_milestone

        to_ms = getattr(args, "to_milestone", None)
        if not to_ms:
            print("[TASK] reassign 需要 --to <new-milestone>", file=sys.stderr)
            return 1
        dry = bool(getattr(args, "dry_run", False))
        ok, lines = reassign_milestone(workspace, m_id, to_ms, dry_run=dry)
        for line in lines:
            print(f"[TASK] {line}")
        _append_log(workspace, f"[{__import__('datetime').datetime.now().isoformat()}] milestone reassign {m_id} -> {to_ms} dry={dry} ok={ok}")
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
        from k3dge.engine.milestone_audit import persist_external_audit_report

        path = persist_external_audit_report(workspace, m_id, raw, kind=getattr(args, "kind", "audit") or "audit")
        print(f"[AUDIT] persisted external audit report -> {path}")
        print("[AUDIT] 只补证据（ADR-0004 §2.1.10）：不推进版号、不触发封板——"
              "版号前进只认审计正常返回（seal 相位 2）。")
        _append_log(workspace, f"[{__import__('datetime').datetime.now().isoformat()}] milestone audit-submit -> {m_id} -> {path}")
        _emit_lifecycle_next(workspace, sys.stdout)
        return 0

    if action == "audit":
        # 独立审计入口（ADR-0004 §2.1.9：审计＝封板主体，seal 相位 2 走同一函数）：只跑审计**不封板**。
        # ⚠️ 2026-09-27 真跑发现：棘轮形状退休时删掉了这里的调用，只剩 `print(msg)` ⇒ 入口**悬空**
        #   （`k3dge milestone audit M0` 抛 UnboundLocalError `msg`，审计腿根本没跑）。悬空入口＝声明了没人接。
        from k3dge.engine.milestone_audit import run_audit_flow

        status, msg = run_audit_flow(workspace, m_id, prompter=_Prompt.default())
        print(msg)
        _append_log(workspace, f"[{__import__('datetime').datetime.now().isoformat()}] milestone audit -> {m_id} status={status}")
        _emit_lifecycle_next(workspace, sys.stdout)
        return 0 if status.startswith("audited") else 1

    if action == "seal":
        # 版号前进在**相位 3**（审计正常返回之后，ADR-0004 §2.1.9/§2.1.11）：
        # 不再由 CLI 在流程返回后另跑一次 bump——那会把"版号时机"与"审计返回"错开。
        status, msg = run_seal_flow(
            workspace,
            m_id,
            prompter=_Prompt.default(),
            skip_enter_prompt=getattr(args, "yes", False),
            no_version_bump=getattr(args, "no_version_bump", False),
        )
        print(msg)
        _append_log(workspace, f"[{__import__('datetime').datetime.now().isoformat()}] milestone seal -> {m_id} status={status}")
        if status == "sealed" or status == "seal_declined":
            return 0
        return 1

    return 1


_CONV_RE = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([\w\-.]+\))?!?: .+"
)


def _conventional_ok(msg: str) -> bool:
    return bool(_CONV_RE.match(msg or ""))


#: **错写**（正确名＝k3dge；不存在叫这个名字的仓）。唯一合法出现＝**在引用这个错写本身**（反引号跨度），
#: 因为检测器、测试与文档必须能写它。裸写（无反引号）一律提示——没有"历史名"这回事。
_OLD_NAME = "k3ge"
_OLD_NAME_QUOTED = re.compile(r"`[^`]*k3ge[^`]*`")


def old_name_warnings(msg: str) -> List[str]:
    """提交信息里**裸写**了错写名 ⇒ 返回可疑行（调用方只提示，不阻断）。

    只提示不阻断的理由：检测器/测试/文档必须能提到这个字符串（用反引号标注即豁免），阻断会挡住必要引用。
    实测危害：2026-09-26 一天内它被写进 4 条提交信息。
    """
    out: List[str] = []
    for line in (msg or "").splitlines():
        if _OLD_NAME not in line:
            continue
        if _OLD_NAME_QUOTED.search(line):
            continue
        out.append(line.strip())
    return out


from k3dge.engine import attest as _attest

_ATTEST_PREFIX = _attest.PREFIX


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
        # 绝对或非法 pattern（`/etc/*`）在 pathlib 里以 ValueError / NotImplementedError 抛出，
        # 且抛在 `SEC-01` 收敛（_rel_within_workspace）**之前** ⇒ 旧代码直接崩栈。
        try:
            candidates = list(workspace.glob(args.path))
        except (ValueError, NotImplementedError, re.error) as exc:
            print(f"[SEARCH] 非法 --path glob '{args.path}': {exc}", file=sys.stderr)
            return 1
        for p in candidates:
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
    # 1) conventional commit message validation（**先校验再动 index**：失败时不留半暂存态，ocr-029）
    if not _conventional_ok(args.message):
        print(
            f"[COMMIT] message '{args.message}' is not Conventional Commits (e.g. 'feat: ...')",
            file=sys.stderr,
        )
        return 1
    # 2) stage (GIT-01: -- separator isolates filenames)；**判 returncode**：暂存失败必须退，
    #    否则后续 `evaluate(staged=True)` 会对残留/空暂存区跑闸、再提交出用户没打算提交的内容。
    _add_argvs = []
    if args.all:
        _add_argvs.append(["git", "add", "-A"])
    if args.files:
        _add_argvs.append(["git", "add", "--", *args.files])
    for _argv in _add_argvs:
        _r = subprocess.run(_argv, cwd=workspace, check=False, capture_output=True, text=True)
        if _r.returncode != 0:
            print(_r.stderr or _r.stdout, file=sys.stderr)
            return 1
    # 3) gate (blocking)：先跑**staged 范围**的一致性集（hook 跑的是 worktree 范围；
    #    两者不同源）。内层只覆盖 `evaluator` 的判据集；引用/名实/markdown/排查闸**不在这里**，
    #    由第 5 步的 live hook 承担 ⇒ 不得再用 --no-verify 跳过它。
    report = ConsistencyEngine(workspace).evaluate(staged=True, run_tests=args.with_tests)
    if not report.passed:
        print(report.render())
        return 1
    # 5) commit：**不跳过 hook**（历史前科：这里曾用 --no-verify，理由写“hook 只会重跑同一个
    #    gate”——实际 hook 跑得更多，doc-gate/schema/引用/排查闸 全在 hook 里，绕过它等于
    #    新文档的引用面无人验，PRE-01 实例）。同理**不得改成 `git commit --no-verify`**。
    #    自附 attestation trailer：hook 的 commit-msg 会看到已有该行而不再重复附。
    msg = _attest.append_to_message(workspace, args.message)   # 内部按 LINE_RE 判合法性（子串判断可被伪造/过期，ocr-200）
    res = subprocess.run(
        ["git", "commit", "-m", msg],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        print(res.stderr or res.stdout, file=sys.stderr)
        return 1
    print(res.stdout)  # git 自己那份摘要（stdout）
    # 2026-09-21：git 把 **hook 的 stdout 接到 stderr**（实测：`git commit` 摘要走 stdout、
    # 闸输出走 stderr）⇒ 只看 res.stdout 会把 doc-gate/schema/check 三层输出吞掉。
    if res.stderr.strip():
        print(res.stderr, file=sys.stderr)
    return 0


def cmd_commit_attest(args: argparse.Namespace) -> int:
    """Print the attestation trailer line for the live commit-msg hook to append."""
    print(_attest.line(_find_workspace(Path.cwd())))
    return 0


def cmd_verify_attest(args: argparse.Namespace) -> int:
    """Verify a commit's attestation token (used by CI). Every commit is in scope; no skip list."""
    ok, msg = _attest.verify_commit(_find_workspace(Path.cwd()), args.commit)
    print(msg, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


def cmd_check_msg(args: argparse.Namespace) -> int:
    from pathlib import Path

    msg = Path(args.file).read_text(encoding="utf-8").strip()
    for _ln in old_name_warnings(msg):
        print(f"[COMMIT] 疑似错写 '{_OLD_NAME}'（正确名＝k3dge；要引用它请加反引号）：{_ln}",
              file=sys.stderr)
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
    # 与 `_read_submit_input` 同口径：交互 tty 直接读 stdin 会**永久阻塞**（hook/CI 场景没人喂输入，ocr-180）。
    if args.from_ci:
        try:
            raw = _Path(args.from_ci).read_text(encoding="utf-8")
        except OSError as exc:
            print(f"[INCIDENT] --from-ci 读不到（{args.from_ci}）：{exc}", file=sys.stderr)
            return 1
    elif sys.stdin.isatty():
        print("[INCIDENT] 需要 JSON 载荷：--from-ci <file> 或 `cat payload.json | k3dge incident ...`", file=sys.stderr)
        return 1
    else:
        raw = sys.stdin.read()
    try:
        data = _json.loads(raw)
    except ValueError as exc:
        print(f"[INCIDENT] 载荷不是合法 JSON：{exc}", file=sys.stderr)
        return 1
    if not isinstance(data, dict):
        print(f"[INCIDENT] 载荷必须是 JSON 对象，收到 {type(data).__name__}", file=sys.stderr)
        return 1
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
        # Persistent next-step hints (single source: engine.nextstep)；多处理点按 priority 排序
        _emit_all_hints(workspace, sys.stdout)
    return 0


# k3dit:leftover value-22 体积属实，但本轮有意留：按 A-1 分块逐程消化，本窗无法验证搬迁
    # 判读不驳：`wc -l src/k3dge/cli/main.py` = 1350，仍超 1000 行健康线（M7 quality Q-7 同口径）。
    # 不本轮改的理由（how）：
    # 1. 本窗是审计纯净版，**没有 tests/**；`cmd_*` + `build_parser` 外迁是跨文件 import 搬迁，
    #    无测试可证 CLI 出口不回归（`status/next` 三出口同构那类断言都在主仓 tests 里）。
    # 2. 该债按 A-1「上帝模块逐程消化」走：`engine/` 下 prompt/task_write/seal_flow/milestone_audit
    #    等件即先例（各自 docstring 记「Extracted from engine/milestone.py A-1 第 N 块」）；
    #    M7 quality Q-7 对同一体积债的裁定是「债已入登记票逐程消化；不接受整体销账」。
    # 3. 拆 CLI 面同时动 `cli/main.py` 与 `cli/mcp.py` 的公开符号 ⇒ 必须与 spec/契约哈希同批
    #    `k3dge sync`（AGENTS.md §12），超出这一张发现单的范围，需要独立里程碑 task。
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
    p_milestone.add_argument("action", choices=["status", "align", "seal", "audit", "checklist", "audit-submit", "seal-check", "reassign"], help="milestone action")
    p_milestone.add_argument("milestone_id", help="milestone identifier (matches Milestone field in tasks)")
    p_milestone.add_argument("--to", dest="to_milestone",
                            help="reassign: new milestone id (e.g. M11)")
    p_milestone.add_argument("--dry-run", dest="dry_run", action="store_true",
                            help="reassign: preview without touching files")
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
    p_doc_fix = doc_sub.add_parser(
        "fix",
        help="按闭集规则规范化受管文档（幂等；--dry-run 预览）——解 seal 前置 docs_normalized",
    )
    p_doc_fix.add_argument("--dry-run", dest="dry_run", action="store_true", help="只报不改")
    p_doc_fix.set_defaults(func=cmd_doc)
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

    p_aud = sub.add_parser("audit", help="审计（本地工具 k3dit）：bundle＝产包/消费（ADR-0025 §2.9.6；工作区=CWD）")
    p_aud.add_argument("audit_action",
                       choices=["submit", "status", "show", "advance", "materialize", "close", "bundle"],
                       help="bundle＝产包/消费（本地工具 k3dit）；其余六动词**已退休**（会明确拒绝并指路）")
    p_aud.add_argument("job_or_milestone", nargs="?", default="", help="status/show/materialize:job_id 或里程碑；advance:线名；close:milestone")
    p_aud.add_argument("--run", action="store_true",
                       help="bundle：先跑 k3dit 路径入口产包再消费（缺省只消费已存在的包）")
    p_aud.add_argument("--pins", dest="bundle_pins", choices=["inplace", "artifact"], default="inplace",
                       help="bundle：钉的落地形态（inplace＝钉留树 / artifact＝钉只随包）")
    p_aud.add_argument("--landing", dest="bundle_landing", choices=["closed-only", "partial", "all"],
                       default="partial",
                       help="bundle：未关项怎么落（closed-only 不落 / partial 只剔其 hunk / all 全落并标升级）")
    p_aud.add_argument("--timeout", dest="bundle_timeout", type=int, default=0,
                       help="bundle：工具调用的墙钟预算（秒；0＝按模式缺省：full 2h / audit-only 1h）")
    p_aud.add_argument("--accept-baseline-drift", dest="bundle_drift", default="",
                       help="bundle：显式接受基线漂移（给理由；仅当漂移文件不被补丁触及）")
    p_aud.add_argument("--exclude", dest="bundle_exclude", action="append", default=[],
                       help="bundle：显式排除某个文件（可重复）——例如该修复与现测试期望冲突")
    p_aud.add_argument("--milestone", dest="bundle_milestone", default="",
                       help="bundle：落报告用的里程碑 id（缺省 local；**不要**用包路径）")
    p_aud.add_argument("--scope", dest="bundle_scope", default="",
                       help="bundle：送审范围（逗号分隔，相对仓根；空＝k3dit 缺省）")
    p_aud.add_argument("--mode", dest="bundle_mode", choices=["audit-only", "full"], default="full",
                       help="bundle --run：k3dit 模式（缺省 full＝判读+修+复核）")
    p_aud.add_argument("--bundle-out", default="", help="bundle --run：产包目录（缺省 .k3dit/bundle）")
    p_aud.add_argument("--dry-run", action="store_true",
                       help="bundle：只验契约与 `git apply --check`，不落补丁")
    p_aud.add_argument("--into", default="", help="bundle：落补丁的目标目录（缺省=当前工作区）")
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

    p_commit = sub.add_parser("commit", help="convenience commit: staged gate + live git hooks + attestation sign")
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
    try:
        # 一轮开始的边界：清空侧车，否则上一条命令的处理点会留到这一轮
        # （观测件：失败不得影响任何命令）
        from k3dge.engine import nextstep

        nextstep.begin_run(_find_workspace(Path.cwd()))
    except Exception:
        pass
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
