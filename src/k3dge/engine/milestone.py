"""Milestone lifecycle engine: alignment check, test regression, and context compaction."""

from __future__ import annotations

import datetime
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from k3dge.engine.evaluator import ConsistencyEngine

STATUS_RE = re.compile(r"-\s+\*\*Status\*\*:\s*([\w-]+)", re.IGNORECASE)
MILESTONE_RE = re.compile(r"-\s+\*\*Milestone\*\*:\s*([^\n\r]+)", re.IGNORECASE)
GUIDE_STUB_RE = re.compile(r"<!--\s*k3dge:guide-stub\s*-->", re.IGNORECASE)
_ALLOWED_STATUS = frozenset({"idea", "deferred", "in-progress", "done"})
_SAFE_MILESTONE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_ALIGN_STUB_MARKER = "<!-- k3dge:align-stub -->"


def _align_pass_marker(milestone_id: str) -> str:
    return f"<!-- k3dge:align-pass:{milestone_id} -->"


def _validate_milestone_id(milestone_id: str) -> Optional[str]:
    """Return an error message if `milestone_id` is unsafe as a path component."""
    if not milestone_id or not _SAFE_MILESTONE_ID_RE.fullmatch(milestone_id):
        return (
            f"Invalid milestone id '{milestone_id}': use a letter/digit start, "
            "then letters, digits, '.', '_' or '-' only (no path separators)."
        )
    return None


def _has_milestone_token(text: str, milestone_id: str) -> bool:
    """True iff `milestone_id` appears as a path/word token, not a substring of a longer id.

    `M1` must not match `M10` in filenames (`2026-08-23-M10-align.md`) or SUMMARY text.
    """
    if not milestone_id:
        return False
    return (
        re.search(
            rf"(?:^|[-_./\s]){re.escape(milestone_id)}(?:[-_./\s]|$)",
            text,
        )
        is not None
    )


def scan_unfilled_guides(workspace: Path) -> List[str]:
    """Names of guide stubs in docs/guides/ still carrying `<!-- k3dge:guide-stub -->`."""
    guides_dir = workspace / "docs" / "guides"
    if not guides_dir.exists():
        return []
    return [
        g.name
        for g in sorted(guides_dir.glob("*.md"))
        if GUIDE_STUB_RE.search(g.read_text(encoding="utf-8"))
    ]


@dataclass(frozen=True)
class MilestoneTask:
    path: Path
    slug: str
    status: str
    milestone: str


def scan_milestone_tasks(workspace: Path, milestone_id: str) -> List[MilestoneTask]:
    tasks_dir = workspace / "docs" / "tasks"
    if not tasks_dir.exists():
        return []

    matched: List[MilestoneTask] = []
    for p in sorted(tasks_dir.glob("*.md")):
        if p.name == "README.md":
            continue
        content = p.read_text(encoding="utf-8")
        s_m = STATUS_RE.search(content)
        m_m = MILESTONE_RE.search(content)
        
        status = s_m.group(1).lower() if s_m else "unknown"
        m_id = m_m.group(1).strip() if m_m else ""

        if m_id == milestone_id:
            matched.append(MilestoneTask(path=p, slug=p.stem, status=status, milestone=m_id))
    return matched


def run_milestone_alignment(workspace: Path, milestone_id: str) -> Tuple[bool, str, List[MilestoneTask]]:
    id_err = _validate_milestone_id(milestone_id)
    if id_err:
        return False, id_err, []

    tasks = scan_milestone_tasks(workspace, milestone_id)
    if not tasks:
        return False, f"No tasks found for milestone '{milestone_id}' under docs/tasks/", []

    invalid = [t for t in tasks if t.status not in _ALLOWED_STATUS]
    if invalid:
        listing = "\n".join(f"  - {t.path.name} (status: {t.status})" for t in invalid)
        return False, f"Invalid Status (not idea|deferred|in-progress|done):\n{listing}", tasks

    pending = [t for t in tasks if t.status != "done"]
    if pending:
        msg = f"Cannot align milestone '{milestone_id}'. {len(pending)} pending tasks:\n" + "\n".join(
            f"  - {t.path.name} (status: {t.status})" for t in pending
        )
        return False, msg, tasks

    # 1. Full Matrix = 同一套 ConsistencyEngine（force_full，不复制 L2）
    report = ConsistencyEngine(workspace).evaluate(run_tests=True, force_full=True)
    if not report.passed:
        return False, f"Regression tests failed during milestone alignment:\n{report.render()}", tasks

    # 2. 生成极简对齐评审报告
    today = datetime.date.today().isoformat()
    review_file = workspace / "docs" / "reviews" / f"{today}-{milestone_id}-align.md"
    if not review_file.exists():
        review_file.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"# 里程碑对齐与验收报告: {milestone_id}",
            _ALIGN_STUB_MARKER,
            _align_pass_marker(milestone_id),
            "",
            f"- **Date**: {today}",
            "- **Regression**: PASS (k3dge milestone align Full Matrix)",
            f"- **Completed Tasks**: {len(tasks)}",
            "",
            "## 1. 目标达成清单",
            "",
        ]
        for t in tasks:
            lines.append(f"- [x] `{t.path.name}`")
        lines.extend([
            "",
            "## 2. 重构准入评估",
            "> 仅在存在阻塞后续扩展的设计缺陷时启动重构；常规情况下跳过大重构。",
            "",
            "- [ ] 是否存在阻塞后续阶段的架构/接口缺陷？(Yes/No)",
            "- [ ] 是否存在超出阈值的深层嵌套坏味道？(Yes/No)",
            "- 处置结论: 跳过重构直接封板 / 触发定向微调",
            "",
            "## 3. 验收结论",
            "目标达成，契约一致，准予封板压缩。",
            "",
        ])
        review_file.write_text("\n".join(lines), encoding="utf-8")

    # 3. 指南完成度扫描（预警非阻断）：docs/guides/ 残留的 TODO 桩在 seal 时会被硬拦
    unfilled = scan_unfilled_guides(workspace)
    note = ""
    if unfilled:
        note = (
            " WARNING: unfilled guide stubs (will block seal): "
            + ", ".join(unfilled)
        )

    return True, f"Milestone '{milestone_id}' aligned successfully. Review template: {review_file.relative_to(workspace)}.{note}", tasks


def seal_milestone(workspace: Path, milestone_id: str) -> Tuple[bool, str]:
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

    pending = [t for t in tasks if t.status != "done"]
    if pending:
        return False, f"Cannot seal milestone '{milestone_id}'. Tasks not done: {[t.path.name for t in pending]}"

    reviews_dir = workspace / "docs" / "reviews"

    # 闸机 1: 必须存在填完的审计报告（align 自动桩 <!-- k3dge:align-stub --> 不算）
    matching_reviews = []
    stub_reviews = []
    missing_pass = []
    pass_mark = _align_pass_marker(milestone_id)
    if reviews_dir.exists():
        for f in reviews_dir.iterdir():
            if not f.is_file() or not _has_milestone_token(f.name, milestone_id):
                continue
            content = f.read_text(encoding="utf-8")
            if not content.strip():
                continue
            if _ALIGN_STUB_MARKER in content:
                stub_reviews.append(f)
                continue
            if pass_mark not in content:
                missing_pass.append(f)
                continue
            matching_reviews.append(f)
    if not matching_reviews:
        if stub_reviews:
            return False, (
                f"[SEAL REJECTED] Review for milestone '{milestone_id}' is still an align stub.\n"
                f"  Remove `{_ALIGN_STUB_MARKER}` after filling docs/reviews/ (keep `{pass_mark}`)."
            )
        if missing_pass:
            return False, (
                f"[SEAL REJECTED] Review for milestone '{milestone_id}' has no align-pass marker.\n"
                f"  Run 'k3dge milestone align {milestone_id}' (writes `{pass_mark}`) then fill the stub."
            )
        return False, (
            f"[SEAL REJECTED] Missing audit review document for milestone '{milestone_id}'.\n"
            f"  Run 'k3dge milestone align {milestone_id}' and fill docs/reviews/ before sealing."
        )

    # 闸机 2: docs/reviews/SUMMARY.md 必须已登记该里程碑（完整 token，防 M1⊂M10）
    summary_file = reviews_dir / "SUMMARY.md"
    if not summary_file.exists() or not _has_milestone_token(
        summary_file.read_text(encoding="utf-8"), milestone_id
    ):
        return False, (
            f"[SEAL REJECTED] docs/reviews/SUMMARY.md not updated with '{milestone_id}'.\n"
            f"  Append the audit summary for the review to SUMMARY.md."
        )

    # 闸机 3: docs/guides/ 不得残留 k3dge:guide-stub
    unfilled = scan_unfilled_guides(workspace)
    if unfilled:
        return False, (
            f"[SEAL REJECTED] Unfilled guide stubs detected in docs/guides/: {unfilled}.\n"
            f"  Complete the documentation before milestone seal."
        )

    archive_root = (workspace / "docs" / "tasks" / "archive").resolve()
    archive_dir = (archive_root / milestone_id).resolve()
    try:
        archive_dir.relative_to(archive_root)
    except ValueError:
        return False, f"Invalid milestone id '{milestone_id}': archive path escapes docs/tasks/archive/"

    archive_dir.mkdir(parents=True, exist_ok=True)

    moved_records: list[tuple[Path, Path]] = []
    try:
        for t in tasks:
            target = archive_dir / t.path.name
            shutil.move(str(t.path), str(target))
            moved_records.append((target, t.path))
    except Exception as exc:
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

    return True, f"Sealed milestone '{milestone_id}'. Archived {len(tasks)} tasks to docs/tasks/archive/{milestone_id}/"
