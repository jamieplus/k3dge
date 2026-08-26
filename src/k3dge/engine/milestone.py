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
PRIORITY_RE = re.compile(r"-\s+\*\*Priority\*\*:\s*(\S+)", re.IGNORECASE)
TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
GUIDE_STUB_RE = re.compile(r"<!--\s*k3dge:guide-stub\s*-->", re.IGNORECASE)
_ALLOWED_STATUS = frozenset({"idea", "deferred", "in-progress", "done"})
_TASK_TYPES = frozenset({"audit", "feat", "fix", "docs", "chore", "refactor"})
_SAFE_MILESTONE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_ALIGN_STUB_MARKER = "<!-- k3dge:align-stub -->"


def _align_pass_marker(milestone_id: str) -> str:
    return f"<!-- k3dge:align-pass:{milestone_id} -->"


def _milestone_file(workspace: Path) -> Path:
    return workspace / ".agent" / "milestone"


def get_current_milestone(workspace: Path) -> str:
    """Current milestone cursor, default M0; stored in .agent/milestone."""
    p = _milestone_file(workspace)
    if p.is_file():
        try:
            v = p.read_text(encoding="utf-8").strip()
            if v and _SAFE_MILESTONE_ID_RE.fullmatch(v):
                return v
        except (OSError, UnicodeDecodeError):
            pass
    return "M0"


def set_current_milestone(workspace: Path, milestone_id: str) -> None:
    err = _validate_milestone_id(milestone_id)
    if err:
        raise ValueError(err)
    p = _milestone_file(workspace)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(milestone_id + "\n", encoding="utf-8")


def bump_milestone(workspace: Path) -> str:
    """M0 → M1 → M2 …; writes new cursor and returns it."""
    cur = get_current_milestone(workspace)
    m = re.match(r"^M(\d+)$", cur)
    if m:
        nxt = f"M{int(m.group(1)) + 1}"
    else:
        # Fallback: treat any id as base, suffix -next (should not happen for M* flow)
        nxt = f"{cur}-next"
    set_current_milestone(workspace, nxt)
    return nxt


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
    out: List[str] = []
    for g in sorted(guides_dir.glob("*.md")):
        try:
            text = g.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            out.append(g.name)
            continue
        if GUIDE_STUB_RE.search(text):
            out.append(g.name)
    return out


@dataclass(frozen=True)
class MilestoneTask:
    path: Path
    slug: str
    status: str
    milestone: str


@dataclass(frozen=True)
class TaskIndex:
    """Top-level docs/tasks/*.md index row. Archive is out of scan horizon."""

    path: Path
    title: str
    status: str
    milestone: str
    priority: str


def list_tasks(
    workspace: Path,
    milestone_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[TaskIndex]:
    """Index living task files (not archive/, not README). Filters are exact matches."""
    tasks_dir = workspace / "docs" / "tasks"
    if not tasks_dir.exists():
        return []
    want_status = status.lower().strip() if status else None
    want_ms = milestone_id.strip() if milestone_id else None
    out: List[TaskIndex] = []
    for p in sorted(tasks_dir.glob("*.md")):
        if p.name == "README.md":
            continue
        try:
            content = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        s_m = STATUS_RE.search(content)
        m_m = MILESTONE_RE.search(content)
        p_m = PRIORITY_RE.search(content)
        t_m = TITLE_RE.search(content)
        st = s_m.group(1).lower() if s_m else "unknown"
        m_id = m_m.group(1).strip() if m_m else ""
        if want_ms is not None and m_id != want_ms:
            continue
        if want_status is not None and st != want_status:
            continue
        title = t_m.group(1).strip() if t_m else p.stem
        pri = p_m.group(1).strip() if p_m else ""
        out.append(TaskIndex(path=p, title=title, status=st, milestone=m_id, priority=pri))
    return out


def scan_milestone_tasks(workspace: Path, milestone_id: str) -> List[MilestoneTask]:
    return [
        MilestoneTask(path=t.path, slug=t.path.stem, status=t.status, milestone=t.milestone)
        for t in list_tasks(workspace, milestone_id=milestone_id)
    ]


def create_task(
    workspace: Path,
    title: str,
    *,
    typ: str = "fix",
    slug: Optional[str] = None,
    milestone: Optional[str] = None,
    priority: str = "P2",
) -> Tuple[bool, str, Optional[Path]]:
    """Write a living task file. Returns (ok, message, path)."""
    if typ not in _TASK_TYPES:
        return False, f"invalid type '{typ}'", None
    raw_slug = (slug if slug is not None else title).strip()
    norm = re.sub(r"[^A-Za-z0-9]+", "_", raw_slug).strip("_")
    if not norm:
        return False, "slug must contain alphanumeric characters", None
    if milestone is None:
        try:
            milestone = get_current_milestone(workspace)
        except Exception:
            milestone = None
    date = datetime.date.today().isoformat()
    if milestone:
        fname = f"{date}-{milestone}-{typ}-{norm}.md"
    else:
        fname = f"{date}-{typ}-{norm}.md"
    target = workspace / "docs" / "tasks" / fname
    if target.exists():
        return False, f"already exists: {target.relative_to(workspace)}", target
    target.parent.mkdir(parents=True, exist_ok=True)
    milestone_line = f"- **Milestone**: {milestone}\n" if milestone else ""
    content = (
        f"# {title}\n\n"
        f"- **Status**: idea\n"
        f"{milestone_line}"
        f"- **Priority**: {priority}\n"
        f"- **Date**: {date}\n\n"
        f"## 已确认意图\n{title}\n\n"
        f"## 可检索摘要\n{title}\n\n"
        f"## 上下文/切入点\n{title}\n"
    )
    target.write_text(content, encoding="utf-8")
    return True, f"created {target.relative_to(workspace)}", target


def mark_task_done(workspace: Path, ident: str) -> Tuple[bool, str, Optional[Path]]:
    """Mark one living task done. Prefer exact path from list_tasks; else unique filename substring."""
    ident = ident.strip().replace("\\", "/")
    if not ident:
        return False, "done requires a path or unique filename substring", None
    tasks_dir = workspace / "docs" / "tasks"
    archive_dir = tasks_dir / "archive"
    if not tasks_dir.is_dir():
        return False, "docs/tasks/ missing", None
    target: Optional[Path] = None
    raw = Path(ident)
    cand = raw if raw.is_absolute() else (workspace / ident)
    try:
        resolved = cand.resolve()
        resolved.relative_to(tasks_dir.resolve())
        # 阻断对 archive/ 目录内任务的修改（不可变性）
        if archive_dir.exists():
            try:
                resolved.relative_to(archive_dir.resolve())
                return False, f"cannot modify archived task: {ident}", None
            except ValueError:
                pass
        if resolved.is_file() and resolved.name != "README.md":
            target = resolved
    except (ValueError, OSError):
        target = None
    if target is None:
        name_only = Path(ident).name
        matches = [
            p
            for p in sorted(tasks_dir.glob("*.md"))
            if p.name != "README.md" and (ident in p.name or ident in p.stem or name_only == p.name)
        ]
        if not matches:
            return False, f"no task matching '{ident}'", None
        if len(matches) > 1:
            names = ", ".join(p.name for p in matches)
            return False, f"multiple matches for '{ident}': {names}", None
        target = matches[0]
    try:
        content = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return False, str(exc), target
    if re.search(r"-\s+\*\*Status\*\*:\s*done\b", content, re.IGNORECASE):
        return True, f"already done: {target.name}", target
    new_content = re.sub(r"-\s+\*\*Status\*\*:\s*[\w-]+", "- **Status**: done", content, count=1)
    if new_content == content:
        return False, f"no Status field in {target.name}", target
    target.write_text(new_content, encoding="utf-8")
    if not target.name.endswith(".done.md"):
        new_path = target.parent / (target.name[:-3] + ".done.md")
        if not new_path.exists():
            target.rename(new_path)
            target = new_path
    return True, f"marked done: {target.name}", target


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

    msg = (
        f"[ALIGN] Full Matrix verification PASS for milestone '{milestone_id}'.\n"
        f"  Created review scaffold: docs/reviews/{today}-{milestone_id}-align.md\n"
        f"HUMAN_CHECKPOINT: Milestone {milestone_id} 全绿，是否执行 5-Pass 专项审计？(y/N, 60s 超时默认 N)"
    )
    if note:
        msg += note
    return True, msg, tasks


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

    # 闸机 1: 必须存在填完的审计报告（align 自动桩 <!-- k3dge:align-stub --> 不算）且正文列出全部任务
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
        if incomplete_reviews:
            return False, (
                f"[SEAL REJECTED] Review for milestone '{milestone_id}' does not list all tasks.\n"
                f"  Missing in {incomplete_reviews[0].name}: {[t.path.name for t in tasks if t.path.name not in incomplete_reviews[0].read_text(encoding='utf-8')]}"
            )
        return False, (
            f"[SEAL REJECTED] Missing audit review document for milestone '{milestone_id}'.\n"
            f"  Run 'k3dge milestone align {milestone_id}' and fill docs/reviews/ before sealing."
        )

    # 闸机 2: docs/reviews/SUMMARY.md 必须已登记该里程碑（完整 token，防 M1⊂M10）
    summary_file = reviews_dir / "SUMMARY.md"
    try:
        summary_text = summary_file.read_text(encoding="utf-8") if summary_file.exists() else ""
    except UnicodeDecodeError:
        return False, (
            f"[SEAL REJECTED] docs/reviews/SUMMARY.md is not UTF-8.\n"
            f"  Fix encoding then re-run seal."
        )
    if not summary_file.exists() or not _has_milestone_token(summary_text, milestone_id):
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

    # Bump cursor M0→M1… for next round (script-controlled, docs generated via sync if needed)
    try:
        nxt = bump_milestone(workspace)
        return True, f"Sealed milestone '{milestone_id}'. Archived {len(tasks)} tasks to docs/tasks/archive/{milestone_id}/. Next milestone: {nxt}"
    except Exception:
        return True, f"Sealed milestone '{milestone_id}'. Archived {len(tasks)} tasks to docs/tasks/archive/{milestone_id}/. (milestone bump failed)"
