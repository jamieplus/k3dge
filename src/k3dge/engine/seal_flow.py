"""封板流程状态机（`run_seal_flow`）+ align 收尾 helper。

Extracted from `engine/milestone.py` (A-1 第十三块).
`nextstep`/`audit_closed`/`prune_finished`/`get_version` imported lazily (avoid cycles).
"""
from __future__ import annotations

import datetime
from pathlib import Path
from typing import Optional, Tuple

from k3dge.engine import gates
from k3dge.engine.align import _ALIGN_STUB_MARKER, run_milestone_alignment
from k3dge.engine.milestone_files import _has_milestone_token
from k3dge.engine.prompt import Prompt as _Prompt
from k3dge.engine.seal import seal_milestone, seal_preconditions_error


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


def _write_closure_note(workspace: Path, milestone_id: str) -> Path:
    """Emit the context-compression closure checklist for a sealed milestone.

    k3dge seals the mechanical part (archive + version + pointer); the real
    "收摊" is compressing context — documenting the unadopted/failed options,
    pruning unrelated context, updating design docs, then committing. k3dge
    cannot judge what is unrelated, so it lays down the checklist and stops.
    """
    today = datetime.date.today().isoformat()
    try:
        from k3dge.engine.version import _next_version, get_version

        cur = get_version(workspace) or "?"
        # seal 成功后 cmd 层 auto-bump patch（`--no-version-bump` 例外）；此处记**终版**，
        # 不记 bump 前值（否则收摊清单版本恒落后一拍）。
        sealed_version = _next_version(cur, "patch", None) if cur != "?" else "?"
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
                f"{today}\tseal\tseal {milestone_id}\t审计闭环（合并审计模块单份 12 列，待修=0）\t{audit_reports}\t{sealed_version}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return p


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
    really "要不要压缩上下文并收摊". status ∈ {sealed, seal_declined, audit_needed}.
    """
    from k3dge.engine import nextstep
    from k3dge.engine.audit_trigger import audit_closed

    prompt = prompter or _Prompt.default()

    if "audit_closed" in gates.preconditions(workspace, "seal") and not audit_closed(workspace, milestone_id):
        msg = f"Milestone {milestone_id}: 未审计（待修未归零或无 12 列报告），不可封板。"
        _ns = nextstep.NextStep.from_state("audit_needed", milestone_id)
        nextstep.persist(workspace, _ns)
        return "audit_needed", msg + "\n" + _ns.render_cli()

    # enter-seal prompt — NO countdown; N = keep milestone open. Skipped with --yes.
    if not skip_enter_prompt and not prompt.ask(
        f"里程碑 {milestone_id} 审计已闭环，封板？", default_yes=False
    ):
        msg = f"Milestone {milestone_id}: seal declined — 不封，里程碑继续挂着。"
        _ns = nextstep.NextStep.from_state("seal_declined", milestone_id)
        nextstep.persist(workspace, _ns)
        return "seal_declined", msg + "\n" + _ns.render_cli()

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
            _ns = nextstep.next_for_rejection(milestone_id, msg)
            nextstep.persist(workspace, _ns)
            return "rejected", msg + "\n" + _ns.render_cli()
        ok, out = fn()
        if not ok:
            _ns = nextstep.next_for_rejection(milestone_id, out)
            nextstep.persist(workspace, _ns)
            return "rejected", out + "\n" + _ns.render_cli()
        msg += out
    from k3dge.engine import events
    events.emit(workspace, "sealed", milestone=milestone_id)
    _ns = nextstep.NextStep.from_state("sealed", milestone_id)
    nextstep.persist(workspace, _ns)
    return "sealed", msg + "\n" + _ns.render_cli()
