"""封版闸 + 纯归档动作：`seal_preconditions_error`（策略层）+ `seal_milestone`（归档动作）。

Extracted from `engine/milestone.py` (A-1 第十一块).
`audit_closed` imported lazily (audit_trigger imports milestone → avoid cycle).
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import List, Optional, Tuple

from k3dge.engine import adr_gate, gates, process_audit
from k3dge.engine.align import _ALIGN_STUB_MARKER, _align_pass_marker
from k3dge.engine.milestone_files import _has_milestone_token
from k3dge.engine.milestone_pointer import _validate_milestone_id, bump_milestone
from k3dge.engine.review_archive import (
    _reviews_to_archive,
    _rewrite_leftover_links,
    _safe_archive_dir,
)
from k3dge.engine.task_index import _ALLOWED_STATUS, MilestoneTask, scan_milestone_tasks

GUIDE_STUB_RE = re.compile(r"<!--\s*k3dge:guide-stub\s*-->", re.IGNORECASE)


def scan_unfilled_guides(workspace: Path) -> List[str]:
    """Names of guide stubs in docs/guides/ still carrying `<!-- k3dge:guide-stub -->`."""
    guides_dir = workspace / "docs" / "guides"
    if not guides_dir.exists():
        return []
    out: List[str] = []
    for g in sorted(guides_dir.glob("*.md")):
        if g.name == "AUTHORING.md":   # 说明书讲桩是元文本，不是桩本身（doc-catalog 先例同形）
            continue
        try:
            text = g.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            out.append(g.name)
            continue
        if GUIDE_STUB_RE.search(text):
            out.append(g.name)
    return out


def _seal_review_gate(workspace: Path, milestone_id: str, tasks: List[MilestoneTask]) -> Optional[str]:
    """Gate 1: a filled audit review listing every task. Returns rejection msg or None."""
    reviews_dir = workspace / "docs" / "reviews"
    matching_reviews = []
    stub_reviews = []
    missing_pass = []
    incomplete_reviews: list[Path] = []
    pass_mark = _align_pass_marker(milestone_id)
    if reviews_dir.exists():
        for f in reviews_dir.iterdir():
            if not f.is_file() or not _has_milestone_token(f.name, milestone_id):
                continue
            try:
                content = f.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if not content.strip():
                continue
            if _ALIGN_STUB_MARKER in content:
                stub_reviews.append(f)
                continue
            if pass_mark not in content:
                missing_pass.append(f)
                continue
            # 验收：正文必须列出该里程碑下全部 done 任务名（防空报告）
            missing_tasks = [t for t in tasks if t.path.name not in content]
            if missing_tasks:
                incomplete_reviews.append(f)
                continue
            matching_reviews.append(f)
    if matching_reviews:
        return None
    if stub_reviews:
        return (
            f"[SEAL REJECTED] Review for milestone '{milestone_id}' is still an align stub.\n"
            f"  Remove `{_ALIGN_STUB_MARKER}` after filling docs/reviews/ (keep `{pass_mark}`)."
        )
    if missing_pass:
        return (
            f"[SEAL REJECTED] Review for milestone '{milestone_id}' has no align-pass marker.\n"
            f"  Run 'k3dge milestone align {milestone_id}' (writes `{pass_mark}`) then fill the stub."
        )
    if incomplete_reviews:
        return (
            f"[SEAL REJECTED] Review for milestone '{milestone_id}' does not list all tasks.\n"
            f"  Missing in {incomplete_reviews[0].name}: {[t.path.name for t in tasks if t.path.name not in incomplete_reviews[0].read_text(encoding='utf-8')]}"
        )
    return (
        f"[SEAL REJECTED] Missing audit review document for milestone '{milestone_id}'.\n"
        f"  Run 'k3dge milestone align {milestone_id}' and fill docs/reviews/ before sealing."
    )


def _seal_archive(workspace: Path, milestone_id: str, tasks: List[MilestoneTask]) -> Tuple[bool, str]:
    """Move tasks/reviews into archive (collision-checked, rollback on failure) + bump."""
    reviews_dir = workspace / "docs" / "reviews"
    pass_mark = _align_pass_marker(milestone_id)
    task_archive, err = _safe_archive_dir(workspace, "tasks", milestone_id)
    if task_archive is None:
        return False, err
    review_archive, err = _safe_archive_dir(workspace, "reviews", milestone_id)
    if review_archive is None:
        return False, err
    to_archive_reviews = _reviews_to_archive(reviews_dir, milestone_id, pass_mark)
    collisions = [t.path.name for t in tasks if (task_archive / t.path.name).exists()]
    collisions.extend(rev.name for rev in to_archive_reviews if (review_archive / rev.name).exists())
    if collisions:
        return False, (
            f"Cannot seal milestone '{milestone_id}': archive target already exists: {collisions}"
        )
    leftover_path = reviews_dir / "LEFTOVERS.md"
    leftover_orig: str | None = None
    if leftover_path.is_file():
        try:
            leftover_orig = leftover_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            leftover_orig = None
    task_archive.mkdir(parents=True, exist_ok=True)
    if to_archive_reviews:
        review_archive.mkdir(parents=True, exist_ok=True)
    moved_records: list[tuple[Path, Path]] = []
    try:
        for t in tasks:
            target = task_archive / t.path.name
            shutil.move(str(t.path), str(target))
            moved_records.append((target, t.path))
        for rev in to_archive_reviews:
            target = review_archive / rev.name
            shutil.move(str(rev), str(target))
            moved_records.append((target, rev))
            _rewrite_leftover_links(workspace, rev.name, f"archive/{milestone_id}/{rev.name}")
    except Exception as exc:
        if leftover_orig is not None:
            try:
                leftover_path.write_text(leftover_orig, encoding="utf-8")
            except OSError:
                pass
        rollback_errors: list[str] = []
        for current, original in reversed(moved_records):
            try:
                shutil.move(str(current), str(original))
            except Exception as rb_exc:
                rollback_errors.append(f"{current} -> {original}: {rb_exc}")
        if rollback_errors:
            return False, (
                f"Failed to seal milestone '{milestone_id}': {exc}; "
                f"rollback incomplete: {rollback_errors}"
            )
        return False, f"Failed to seal milestone '{milestone_id}', rolled back: {exc}"
    review_note = (
        f" and {len(to_archive_reviews)} reviews to docs/reviews/archive/{milestone_id}/"
        if to_archive_reviews
        else ""
    )
    sealed = (
        f"Sealed milestone '{milestone_id}'. Archived {len(tasks)} tasks to "
        f"docs/tasks/archive/{milestone_id}/{review_note}."
    )
    try:
        nxt = bump_milestone(workspace)
        return True, f"{sealed} Next milestone: {nxt}"
    except Exception:
        return True, f"{sealed} (milestone bump failed)"


def _docs_normalized_error(workspace: Path) -> Optional[str]:
    """`docs_normalized` 前置闸：docs 可确定修的规约偏差必须归零（ADR-0022 §2.2 🅰1.4）。

    为何是**前置闸**而不是 seal 的动作：规约化若在审计闭环之后改文档，刚闭环的审计证据
    （审的是旧文档）就失效了 ⇒ 必须在封板前做完，由 `k3dge doc fix`（[NEXT] 引导的主动动作）
    完成；seal 只验"做没做"。语义类偏差（要读懂内容的）不在此闸，归里程碑轮的外部透镜。
    """
    from k3dge.engine import doc_fix

    dev = doc_fix.scan(workspace)
    if not dev:
        return None
    rules = sorted({d["rule"] for d in dev})
    return (f"[SEAL REJECTED] docs/ 有 {len(dev)} 处可确定修的规约偏差（{', '.join(rules)}）；"
            f"先跑 `k3dge doc fix`（可加 --dry-run 预览），再封板。")


def seal_preconditions_error(workspace: Path, milestone_id: str) -> Optional[gates.Rejection]:
    """策略层：按「硬闸契约」`[checks.seal].preconditions` 求值全部前置闸，返回首个拒绝（None=全绿）。

    返回 `gates.Rejection`（str 子类）：消息文本不变，额外携带闭集 `gate_id`（＝契约里
    声明的闸 id），供 `nextstep.GATE_NEXT` 表驱动派发——消费方不再从文案里搜关键词。

    与 `seal_milestone`（纯归档动作）分离：**何时可封＝策略（本函数）**，封板归档＝动作。
    未实现的 id 视为配置错（拒绝，不让声明空转）。
    """
    from k3dge.engine.audit_trigger import audit_closed

    from k3dge.engine import nodes

    tasks = scan_milestone_tasks(workspace, milestone_id)
    pending = [t for t in tasks if t.status != "done"]
    unfilled = scan_unfilled_guides(workspace)
    gate_fns = {
        "tasks_all_done": lambda _ctx: (
            f"Cannot seal milestone '{milestone_id}'. Tasks not done: "
            f"{[t.path.name for t in pending]}" if pending else None
        ),
        "audit_closed": lambda _ctx: (
            None if audit_closed(workspace, milestone_id)
            else f"[SEAL REJECTED] Milestone '{milestone_id}' audit not closed（无 12 列报告 / 待修≠0）。"
        ),
        "evidence_chain": lambda _ctx: process_audit.evidence_chain_error(workspace, milestone_id),
        "align_pass": lambda _ctx: _seal_review_gate(workspace, milestone_id, tasks),
        "guides_filled": lambda _ctx: (
            f"[SEAL REJECTED] Unfilled guide stubs detected in docs/guides/: {unfilled}.\n"
            f"  Complete the documentation before milestone seal." if unfilled else None
        ),
        "adrs_all_accepted": lambda _ctx: adr_gate.adrs_all_accepted(workspace),
        "adr_landed": lambda _ctx: adr_gate.adr_landed(workspace),
        "docs_normalized": lambda _ctx: _docs_normalized_error(workspace),
    }
    ctx = {"workspace": workspace, "milestone_id": milestone_id,
           "tasks": tasks, "pending": pending, "unfilled": unfilled}
    ok, out = nodes.run_phase(workspace, "seal", "preconditions", gate_fns, ctx)
    return None if ok else out


def seal_milestone(workspace: Path, milestone_id: str) -> Tuple[bool, str]:
    """纯归档动作：id 合法 + 有任务 + 状态合法 → `_seal_archive`。策略闸在 `seal_preconditions_error`。"""
    id_err = _validate_milestone_id(milestone_id)
    if id_err:
        return False, gates.Rejection("milestone_id_invalid", id_err)

    tasks = scan_milestone_tasks(workspace, milestone_id)
    if not tasks:
        from k3dge.engine.task_index import premature_archive_hint

        return False, gates.Rejection(
            "no_tasks",
            premature_archive_hint(workspace, milestone_id)
            or f"No tasks to seal for milestone '{milestone_id}'.",
        )

    invalid = [t for t in tasks if t.status not in _ALLOWED_STATUS]
    if invalid:
        return False, gates.Rejection(
            "invalid_task_status",
            f"Cannot seal milestone '{milestone_id}'. Invalid Status: "
            f"{[t.path.name for t in invalid]}",
        )

    ok, out = _seal_archive(workspace, milestone_id, tasks)
    if ok:
        return True, out
    return False, gates.rejection(out, "archive_failed")
