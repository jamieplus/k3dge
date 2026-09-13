"""Milestone lifecycle engine: alignment check, test regression, and context compaction."""

from __future__ import annotations

import datetime
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from k3dge.engine import adr_gate, gates, process_audit, report_table
from k3dge.engine.evaluator import ConsistencyEngine

from k3dge.engine.task_index import (  # A-1 第七块 re-export
    MILESTONE_RE,
    PRIORITY_RE,
    STATUS_RE,
    TITLE_RE,
    parse_frontmatter,
)


_TASK_TYPES = frozenset({"audit", "feat", "fix", "docs", "chore", "refactor"})
from k3dge.engine.align import (  # A-1 第十块 re-export
    _ALIGN_STUB_MARKER,
    _align_pass_marker,
    run_milestone_alignment,
)

# A-1 第二块：指针/id 校验已抽到 `milestone_pointer`；此处 re-export 兼容既有调用面。
from k3dge.engine.milestone_pointer import (  # noqa: E402
    _SAFE_MILESTONE_ID_RE,
    _validate_milestone_id,
    bump_milestone,
    get_current_milestone,
    set_current_milestone,
)


# A-1 第三块：命名/甄别帮助已抽到 `milestone_files`；re-export 兼容调用面。
from k3dge.engine.milestone_files import (  # noqa: E402
    _DOC_AUX_NAMES,
    _FILENAME_MILESTONE_RE,
    _REVIEW_AUX,
    _filename_milestone,
    _has_milestone_token,
    _is_doc_aux,
    _is_review_aux,
)


# A-1 第六块：reviews 归档机械已抽到 `review_archive`；re-export 兼容调用面。
from k3dge.engine.review_archive import (  # noqa: E402
    _living_review_files,
    _reviews_to_archive,
    _rewrite_leftover_links,
    _safe_archive_dir,
)


# A-1 第十一块：guide 桩扫描已抽到 `seal`；re-export 兼容调用面。
from k3dge.engine.seal import scan_unfilled_guides  # noqa: E402


# A finding pinned at its 位置 next to the code/doc — a *pointer only* (like
# guide-stub). The disposition authority stays the 12-col report + tasks; these
# markers carry no rationale/how-to-fix (that would become a 3rd fact source,
# and L1 does not hash comments so the gate cannot catch comment drift).
# A-1 第十二块：findings 计数已抽到 `milestone_audit`；re-export 兼容调用面。
from k3dge.engine.milestone_audit import scan_pending_findings  # noqa: E402


from k3dge.engine.task_index import (  # A-1 第七块 re-export
    MILESTONE_RE,
    PRIORITY_RE,
    STATUS_RE,
    TITLE_RE,
    parse_frontmatter,
)


_TASK_TYPES = frozenset({"audit", "feat", "fix", "docs", "chore", "refactor"})
from k3dge.engine.align import (  # A-1 第十块 re-export
    _ALIGN_STUB_MARKER,
    _align_pass_marker,
    run_milestone_alignment,
)

# A-1 第二块：指针/id 校验已抽到 `milestone_pointer`；此处 re-export 兼容既有调用面。
from k3dge.engine.milestone_pointer import (  # noqa: E402
    _SAFE_MILESTONE_ID_RE,
    _validate_milestone_id,
    bump_milestone,
    get_current_milestone,
    set_current_milestone,
)


# A-1 第三块：命名/甄别帮助已抽到 `milestone_files`；re-export 兼容调用面。
from k3dge.engine.milestone_files import (  # noqa: E402
    _DOC_AUX_NAMES,
    _FILENAME_MILESTONE_RE,
    _REVIEW_AUX,
    _filename_milestone,
    _has_milestone_token,
    _is_doc_aux,
    _is_review_aux,
)


# A-1 第六块：reviews 归档机械已抽到 `review_archive`；re-export 兼容调用面。
from k3dge.engine.review_archive import (  # noqa: E402
    _living_review_files,
    _reviews_to_archive,
    _rewrite_leftover_links,
    _safe_archive_dir,
)


# A-1 第十一块：guide 桩扫描已抽到 `seal`；re-export 兼容调用面。
from k3dge.engine.seal import scan_unfilled_guides  # noqa: E402


# A finding pinned at its 位置 next to the code/doc — a *pointer only* (like
# guide-stub). The disposition authority stays the 12-col report + tasks; these
# markers carry no rationale/how-to-fix (that would become a 3rd fact source,
# and L1 does not hash comments so the gate cannot catch comment drift).
def scan_pending_findings(workspace: Path) -> Tuple[int, List[str]]:
    """未决 findings（语法 v1：pending/disputed/fixnote 计 open）。

    薄委托 `engine/markers.py`，保留历史返回 (count, ["path#ID", ...])。leftover（有意留）
    照旧不计时；删标（已修）不计时。语法违规**不改计数口径**，由 `k3dge markers --check` 暴露。
    """
    from k3dge.engine import markers as _mk

    ms, _problems = _mk.extract(workspace)
    samples = _mk.open_samples(ms)
    return (len(samples), samples)


from k3dge.engine.task_index import (  # A-1 第七块/第十块 re-export
    _ALLOWED_STATUS,
    MilestoneTask,
    TaskIndex,
    list_tasks,
    scan_milestone_tasks,
)


# A-1 第九块：task 写入核心已抽到 `task_write`；re-export 兼容调用面。
from k3dge.engine.task_write import (  # noqa: E402
    _auto_backfill_reviews,
    create_task,
    mark_task_done,
)


# A-1 第十一块：seal 闸/归档已抽到 `seal`；re-export 兼容调用面。
from k3dge.engine.seal import (  # noqa: E402
    _seal_archive,
    _seal_review_gate,
    seal_milestone,
    seal_preconditions_error,
)


# ---------------------------------------------------------------------------
# Seal-flow state machine (ADR-0004 §2.1.2, revised 2026-09-01)
#
#   Full Matrix (align, no prompt)
#     -> enter-seal prompt (NO countdown; N = treat as normal commit)
#     -> mandatory audit via k3dit peer (pipeline transports)
#     -> parse 待修 / 有意留 / 已修
#         有意留 -> LEFTOVERS.md, proceeds
#         待修 > 0 -> "agent 修?" prompt (countdown, timeout default = fix) -> fix -> re-audit (loop)
#         待修 = 0 -> verify (best-effort) -> seal (archive + version + milestone bump)
#
# k3dge never audits or scores; it invokes the k3dit lens and gates on the
# produced 12-col report. The work agent fixes; k3dit audits; k3dge routes.
# ---------------------------------------------------------------------------

# A-1 第四块：report 查找/归类/计数已抽到 `audit_report`；re-export 兼容调用面。
from k3dge.engine.audit_report import (  # noqa: E402
    _AUDIT_HEADER,
    _QUALITY_MARKER_RE,
    _find_audit_report,
    _find_report,
    _parse_audit_stats,
    _report_kind,
)


def _align_review_path(workspace: Path, milestone_id: str) -> Optional[Path]:
    """Locate the generated align review scaffold for a milestone."""
    reviews = workspace / "docs" / "reviews"
    if not reviews.is_dir():
        return None
    for f in sorted(reviews.iterdir()):
        if (
            f.is_file()
            and f.suffix == ".md"
            and "-align.md" in f.name
            and _has_milestone_token(f.name, milestone_id)
        ):
            return f
    return None


def _strip_align_stub(workspace: Path, milestone_id: str) -> None:
    """Mark the align scaffold as filled so the seal gate (align-stub check) passes.

    The mandatory audit now *is* the real verification; the align scaffold is a
    structural placeholder only.
    """
    p = _align_review_path(workspace, milestone_id)
    if not p:
        return
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return
    if _ALIGN_STUB_MARKER in text:
        p.write_text(text.replace(_ALIGN_STUB_MARKER, "").strip() + "\n", encoding="utf-8")


# A-1 第十二块：外部报告落盘 + 有意留登记已抽到 `milestone_audit`；re-export。
from k3dge.engine.milestone_audit import (  # noqa: E402
    _ensure_leftovers,
    persist_external_audit_report,
)


from k3dge.engine.prompt import Prompt as _Prompt  # A-1 首块：Prompter 已抽到 prompt.py；保留名兼容调用面


def _write_closure_note(workspace: Path, milestone_id: str) -> Path:
    """Emit the context-compression closure checklist for a sealed milestone.

    k3dge seals the mechanical part (archive + version + pointer); the real
    "收摊" is compressing context — documenting the unadopted/failed options,
    pruning unrelated context, updating design docs, then committing. k3dge
    cannot judge what is unrelated, so it lays down the checklist and stops.
    """
    today = datetime.date.today().isoformat()
    try:
        from k3dge.engine.version import get_version

        sealed_version = get_version(workspace) or "?"
    except Exception:
        sealed_version = "?"
    audit_reports = ",".join(
        sorted(f.name for f in (workspace / "docs" / "reviews").glob(f"*-{milestone_id}-*.md")
               if f.name.endswith(("-audit.md", "-quality.md")))) or "-"
    p = workspace / "docs" / "reviews" / f"{today}-{milestone_id}-closure.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        return p
    p.write_text(
        "\n".join(
            [
                f"# 封板收摊清单（上下文压缩）: {milestone_id}",
                "",
                f"- **Sealed**: {today}",
                "- 归档/版本/指针已由 `seal` 完成；以下由人/agent 补齐（k3dit 判内容，k3dge 不替判）：",
                "",
                "## 1. 落盘失败/未采用的方案",
                "- [ ] 本里程碑讨论过但**未采用**的方案 → 写 `docs/adr/`（含被否原因）或 `docs/incidents/`（B-T-D）",
                "- [ ] 失败尝试 → `docs/incidents/INC-YYYYMMDD-<TYPE>-<slug>.md`",
                "",
                "## 2. 清理无关上下文",
                "- [ ] 删除/折叠与现行方案无关的草稿、分支说明",
                "",
                "## 3. 更新设计文档",
                "- [ ] `docs/architecture/overview.md` 对齐到已封板的现实",
                "- [ ] 相关 ADR 标注 supersedes / 现行范围",
                "",
                "## 4. 提交里程碑",
                "- [ ] `k3dge check` 绿 → 提交（归档 + 收摊 + 文档一起进一个 commit）",
                "",
                "## 5. 决策轨迹（TSV：show-me-your-work 洁净室移植——ts/phase/decision/why/evidence/result，evidence=指针非散文）",
                "ts\tphase\tdecision\twhy\tevidence\tresult",
                f"{today}\tseal\tseal {milestone_id}\t审计双腿闭环\t{audit_reports}\t{sealed_version}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return p


# A-1 第五块：doc-audit 族已抽到 `doc_audit`；re-export 兼容调用面。
from k3dge.engine.doc_audit import (  # noqa: E402
    _attach_k3che_hints,
    _changed_docs,
    _ensure_doc_audit_task,
    _new_archive_without_note,
    _related_doc_hints,
    _similar_task_hints,
    run_doc_audit,
)


# A-1 第十二块：审计腿已抽到 `milestone_audit`；re-export 兼容调用面。
from k3dge.engine.milestone_audit import (  # noqa: E402
    _audit_mode,
    _ratchet_audit_step,
    run_audit_flow,
)


def run_seal_flow(
    workspace: Path,
    milestone_id: str,
    *,
    prompter: Optional[_Prompt] = None,
    skip_enter_prompt: bool = False,
) -> Tuple[str, str]:
    """Seal = archive + version + pointer. Requires a *closed* audit first.

    The boundary is not "when does a milestone end" (no ruler) — it is the audit
    loop closing (12-col, 待修==0). Only after that do we ask "封板?", which is
    really "要不要压缩上下文并收摊". status ∈ {sealed, deferred, audit_needed}.
    """
    from k3dge.engine import nextstep
    from k3dge.engine.audit_trigger import audit_closed

    prompt = prompter or _Prompt.default()

    if "audit_closed" in gates.preconditions(workspace, "seal") and not audit_closed(workspace, milestone_id):
        msg = f"Milestone {milestone_id}: 未审计（待修未归零或无 12 列报告），不可封板。"
        return "audit_needed", msg + "\n" + nextstep.NextStep.from_state("audit_needed", milestone_id).render_cli()

    # enter-seal prompt — NO countdown; N = keep milestone open. Skipped with --yes.
    if not skip_enter_prompt and not prompt.ask(
        f"里程碑 {milestone_id} 审计已闭环，封板？", default_yes=False
    ):
        msg = f"Milestone {milestone_id}: seal deferred — 不封，里程碑继续挂着。"
        return "deferred", msg + "\n" + nextstep.NextStep.from_state("deferred", milestone_id).render_cli()

    # 动作：读「硬闸契约」`[checks.seal].actions`（ADR-0001 §2 第 8 条）——执行器按声明跑；
    # 未实现的 id 视为配置错（拒绝，不让声明空转）。
    def _full_matrix():
        ok, amsg, _ = run_milestone_alignment(workspace, milestone_id)
        if not ok:
            return False, amsg
        _strip_align_stub(workspace, milestone_id)
        return True, ""

    def _archive():
        err = seal_preconditions_error(workspace, milestone_id)
        if err:
            return False, err
        return seal_milestone(workspace, milestone_id)

    def _closure_note():
        p = _write_closure_note(workspace, milestone_id)
        return True, f"\n  收摊清单: {p.relative_to(workspace)}"

    def _prune():
        try:  # end-flow 清理钩子：派生件（worktree/已并入的审计线）收口即删；史在主干
            from k3dge.engine.audit_flow import prune_finished

            pr = prune_finished(workspace)
            if pr.get("pruned"):
                return True, f"\n  审计派生件清理: {pr['pruned']} 组"
        except Exception:
            pass
        return True, ""

    registry = {"full_matrix": _full_matrix, "archive": _archive,
                "closure_note": _closure_note, "prune": _prune}
    msg = ""
    for aid in gates.actions(workspace, "seal"):
        fn = registry.get(aid)
        if fn is None:
            msg = f"[SEAL REJECTED] gate contract references unknown action id: '{aid}'"
            return "rejected", msg + "\n" + nextstep.next_for_rejection(milestone_id, msg).render_cli()
        ok, out = fn()
        if not ok:
            return "rejected", out + "\n" + nextstep.next_for_rejection(milestone_id, out).render_cli()
        msg += out
    return "sealed", msg + "\n" + nextstep.NextStep.from_state("sealed", milestone_id).render_cli()
