"""封版闸 + 纯归档动作：`seal_preconditions_error`（策略层）+ `seal_milestone`（归档动作）。

Extracted from `engine/milestone.py` (A-1 第十一块); `milestone` re-exports for back-compat.
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


def seal_preconditions_error(workspace: Path, milestone_id: str) -> Optional[str]:
    """策略层：按「硬闸契约」`[checks.seal].preconditions` 求值全部前置闸，返回首个错误（None=全绿）。

    与 `seal_milestone`（纯归档动作）分离：**何时可封＝策略（本函数）**，封板归档＝动作。
    未实现的 id 视为配置错（拒绝，不让声明空转）。
    """
    from k3dge.engine.audit_trigger import audit_closed

    tasks = scan_milestone_tasks(workspace, milestone_id)
    pending = [t for t in tasks if t.status != "done"]
    unfilled = scan_unfilled_guides(workspace)
    gate_fns = {
        "tasks_all_done": lambda: (
            f"Cannot seal milestone '{milestone_id}'. Tasks not done: "
            f"{[t.path.name for t in pending]}" if pending else None
        ),
        "audit_closed": lambda: (
            None if audit_closed(workspace, milestone_id)
            else f"[SEAL REJECTED] Milestone '{milestone_id}' audit not closed（无 12 列报告 / 待修≠0）。"
        ),
        "evidence_chain": lambda: process_audit.evidence_chain_error(workspace, milestone_id),
        "align_pass": lambda: _seal_review_gate(workspace, milestone_id, tasks),
        "guides_filled": lambda: (
            f"[SEAL REJECTED] Unfilled guide stubs detected in docs/guides/: {unfilled}.\n"
            f"  Complete the documentation before milestone seal." if unfilled else None
        ),
        "adrs_all_accepted": lambda: adr_gate.adrs_all_accepted(workspace),
        "adr_landed": lambda: adr_gate.adr_landed(workspace),
    }
    for gid in gates.preconditions(workspace, "seal"):
        fn = gate_fns.get(gid)
        if fn is None:
            return f"[SEAL REJECTED] gate contract references unknown gate id: '{gid}'"
        err = fn()
        if err:
            return err
    return None


def seal_milestone(workspace: Path, milestone_id: str) -> Tuple[bool, str]:
    """纯归档动作：id 合法 + 有任务 + 状态合法 → `_seal_archive`。策略闸在 `seal_preconditions_error`。"""
    id_err = _validate_milestone_id(milestone_id)
    if id_err:
        return False, id_err

    tasks = scan_milestone_tasks(workspace, milestone_id)
    if not tasks:
        return False, f"No tasks to seal for milestone '{milestone_id}'."

    invalid = [t for t in tasks if t.status not in _ALLOWED_STATUS]
    if invalid:
        return False, (
            f"Cannot seal milestone '{milestone_id}'. Invalid Status: "
            f"{[t.path.name for t in invalid]}"
        )

    return _seal_archive(workspace, milestone_id, tasks)
