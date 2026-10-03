"""Shared workspace-status synthesis for CLI ``status`` and MCP ``k3dge_status``.

Both surfaces call :func:`workspace_status` so the MCP tool never re-scans tasks or
re-filters drift (ADR-0001 decision 6 / ADR-0008). One implementation, isomorphic output.
"""
from __future__ import annotations

import json
import sys
import re
from pathlib import Path
from typing import Any, Dict, Optional

from k3dge.engine.evaluator import ConsistencyEngine
from k3dge.engine.manifest import Manifest, ManifestError
from k3dge.engine.milestone_files import _is_doc_aux
from k3dge.engine.state_machine import TaskState
from k3dge.engine.task_index import TITLE_RE, parse_frontmatter

#: done 词表单源（ocr2-180）：不得在这里再硬编码一份 "done"。
_DONE_VALUE = TaskState.DONE.value


def cache_observability(workspace: Path) -> Optional[Dict[str, Any]]:
    """service 角色遥测，**只供展示**（peer contract §0：永不进判定链）。

    门 = 工作区存在 `.k3che/`（廉价存在探测，不解析其内容格式）；数据一律走
    角色自己的 stats 工具信封。skip/失败 ⇒ None，status 照常绿。
    """
    if not (workspace / ".k3che").is_dir():
        return None
    try:
        from k3dge.engine.pipeline_runner import run_action

        # 只供展示的遥测 ⇒ 不许按缺省 60s/跳去跑整条传输链（status 是被 harness 高频调的读面）
        res = run_action(workspace, "cache.stats", timeout_default=10)
        if not res.ok or res.provider != "mcp":
            return None
        env = json.loads(res.payload or "")
    except Exception:  # pragma: no cover - 观测件绝不拖垮 status
        return None
    if not isinstance(env, dict) or not env.get("ok"):
        return None
    return {k: env[k] for k in ("total", "hits", "hit_rate", "indexed", "persisted") if k in env}


def lifecycle_next(workspace: Path) -> Any:
    """The single NextStep for this workspace, or None (ADR-0008 routing source).

    Lives here — not in `cli/main.py` — because `workspace_status` must put the same
    value on both exits: human `[NEXT]`, ``status --json`` `.next`, and MCP
    `k3dge_status`. Precedence stays pending_findings > seal_ready > audit_suggested.

    `seal_ready` 的判据＝**预审**（票全 done + 形式闸齐，ADR-0004 §2.1.9 相位 1），与 `seal`
    自己的门槛同源（`seal.unmet_seal_preconditions`）；**审计状态不参与**——审计是 seal 相位 2
    自己跑的，不是"先审好才谈封"的前置闸。
    """
    from k3dge.engine import nextstep
    from k3dge.engine.audit_trigger import compute_audit_suggestion
    from k3dge.engine.milestone_audit import scan_pending_findings
    from k3dge.engine.milestone_pointer import get_current_milestone
    from k3dge.engine.seal import unmet_seal_preconditions

    try:
        mid = get_current_milestone(workspace)
        count, samples = scan_pending_findings(workspace)
        if count > 0:
            return nextstep.NextStep.from_state(
                "pending_findings", mid, pending=count, reasons=[f"标记: {s}" for s in samples[:5]]
            )
        # 一次算清再交给 `seal_ready_for`（它内部原本会**再扫一遍**票与前置闸；status 是高频读面）
        from k3dge.engine.task_index import scan_milestone_tasks

        unmet = unmet_seal_preconditions(workspace, mid)
        if not unmet:
            # 零 task 空窗不建议封（ADR-0004 §2.1.4）；M10 封完指针到 M11 曾立刻 seal_ready。
            tasks = scan_milestone_tasks(workspace, mid)
            if tasks:
                return nextstep.seal_ready_for(workspace, mid, unmet=unmet, tasks=tasks)
        suggested, reasons = compute_audit_suggestion(workspace)
        if suggested:
            return nextstep.NextStep.from_state("audit_suggested", mid, reasons=reasons)
        return None
    except Exception as exc:  # routing 不得拖垮 status，但**也不得把"坏了"渲染成"没待办"（389）**
        print(f"[STATUS] WARN: [NEXT] 路由异常（{type(exc).__name__}: {exc}）⇒ 本轮不投影处理点",
              file=sys.stderr)
        # `None` 与"确实没待办"是同一个值，机器面（`--json` `.next` / MCP）无法区分 ⇒
        # 投专用态，harness 可据此告警而不是静默当"没事"（ocr2-178）。
        try:
            mid = get_current_milestone(workspace)
        except Exception:
            mid = ""
        return nextstep.NextStep.from_state(
            "routing_error", mid, reasons=[f"{type(exc).__name__}: {exc}"]
        )


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

    try:
        report = ConsistencyEngine(workspace).evaluate()
        drift = [
            {"domain": v.domain, "symbol_diff": (v.detail or {}).get("symbol_diff")
             if isinstance(v.detail, dict) else None}
            for v in report.violations
            if v.rule_id == "CONTRACT_DRIFT"
        ]
    except Exception as exc:
        # 核心扫描（evaluate/drift 展平）抛了 ⇒ 按 docstring 承诺回 error 形，
        # 不让 traceback 逸出（MCP `_err` 闭集会被打破，ocr2-179）。
        return {"ok": False, "error": "StatusScanFailed",
                "message": f"consistency scan failed ({type(exc).__name__}: {exc})"}
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
            except (OSError, UnicodeDecodeError):
                continue   # 坏编码的 task 文件只跳过这一张，不让 status 整体崩栈（ocr-032）
            try:
                fm = parse_frontmatter(txt) or {}
            except Exception:
                fm = {}
            m = re.search(r"-\s+\*\*Status\*\*:\s*([\w-]+)", txt, re.IGNORECASE)
            # 值必须小写比较（`parse_frontmatter` 只 lower 键，`Status: Done` 在这里会≠done ⇒ 与引擎
            # `_scan_task_dir` 判定漂移，同一票 status/`[NEXT]`/MCP 三个出口给相反结论，ocr-188）
            status = str(fm.get("status") or (m.group(1) if m else "") or "unknown").strip().lower()
            if status != _DONE_VALUE:
                # 标题复用引擎单源 TITLE_RE（`^#\s+(.+)$` MULTILINE）：原 `#\s*(.+)` 无锚定，
                # 会命中二级标题/代码注释里的 `#`，三处出口标题不一致（ocr-189）。
                tm = re.search(TITLE_RE, txt)
                unfinished.append(
                    {
                        "task": p.stem,
                        "title": (tm.group(1).strip() if tm else p.stem),
                        "status": status,
                    }
                )

    from k3dge.engine import state_machine, task_dag

    try:
        dag = task_dag.summary(workspace)
    except Exception as exc:
        dag = {"error": f"task_dag failed ({type(exc).__name__}: {exc})"}
    try:
        sm = state_machine.summary()
    except Exception as exc:
        sm = {"error": f"state_machine failed ({type(exc).__name__}: {exc})"}
    try:
        ns = lifecycle_next(workspace)
    except Exception as exc:  # 双保险：lifecycle_next 内部已自保，这里只防签名漂移
        print(f"[STATUS] WARN: [NEXT] 投影失败（{type(exc).__name__}: {exc})", file=sys.stderr)
        ns = None

    return {
        "domains": sorted(manifest.domains),
        "gate_passed": report.passed,
        "modified_domains": list(report.modified_domains),
        "drift": drift,
        "pipeline": pipeline,
        "unfinished_tasks": unfinished,
        "task_dag": dag,
        "state_machine": sm,
        "next": (ns.render_mcp() if ns is not None else None),
        "cache": cache_observability(workspace),
    }
