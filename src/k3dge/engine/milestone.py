# k3dit:leftover A-1 @file 上帝模块 1547 行（6+ 关注点），拆分另立票
"""Milestone lifecycle engine: alignment check, test regression, and context compaction."""

from __future__ import annotations

import datetime
import json
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


def parse_frontmatter(content: str) -> dict[str, str]:
    """Strict frontmatter parser: only `---` block at start, YAML-like `key: value`.

    Avoids `Markdown as Database` anti-pattern where body text containing
    `- **Status**:` is mis-captured. Pure stdlib, no external dep.
    """
    meta: dict[str, str] = {}
    lines = content.splitlines()
    if len(lines) >= 2 and lines[0].strip() == "---":
        for line in lines[1:]:
            if line.strip() == "---":
                break
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip().lower()] = v.strip()
    return meta
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


def _changelog_draft_path(workspace: Path) -> Path:
    return workspace / ".agent" / "changelog_draft.md"


def _append_to_unreleased(workspace: Path, task_path: Path) -> bool:
    """Append task's title to CHANGELOG.md ## [Unreleased] under the correct Keep a Changelog subsection.

    Returns True on success or no-op, False on failure (with stderr warning).
    """
    try:
        changelog = workspace / "CHANGELOG.md"
        if not changelog.is_file():
            return True
        content = task_path.read_text(encoding="utf-8") if task_path.is_file() else ""
        title_m = TITLE_RE.search(content)
        title = title_m.group(1).strip() if title_m else task_path.stem
        # Map task type to Keep a Changelog section
        type_m = re.search(r"docs/tasks/\d{4}-\d{2}-\d{2}-(?:M\d+-)?([a-z]+)-", str(task_path))
        task_type = type_m.group(1) if type_m else "fix"
        type_map = {"feat": "Added", "fix": "Fixed", "audit": "Fixed", "docs": "Changed", "chore": "Changed", "refactor": "Changed"}
        section = type_map.get(task_type, "Fixed")
        text = changelog.read_text(encoding="utf-8")
        unreleased = "## [Unreleased]"
        idx = text.find(unreleased)
        if idx == -1:
            return True
        next_idx = text.find("## [", idx + len(unreleased))
        unreleased_block = text[idx:next_idx] if next_idx != -1 else text[idx:]
        if title in unreleased_block:
            return True
        # Find or create the subsection header within Unreleased
        section_header = f"### {section}"
        sec_idx = text.find(section_header, idx, next_idx if next_idx != -1 else len(text))
        entry = f"- {title}\n"
        if sec_idx != -1:
            # Insert after the section header's next line
            header_end = text.find("\n", sec_idx) + 1
            # Find next section or next version
            next_sec = text.find("### ", header_end)
            next_ver = text.find("## [", header_end)
            insert_at = next_sec if next_sec != -1 and (next_ver == -1 or next_sec < next_ver) else next_ver
            if insert_at == -1 or (next_idx != -1 and insert_at > next_idx):
                insert_at = next_idx if next_idx != -1 else len(text)
            new_text = text[:insert_at] + entry + text[insert_at:]
        else:
            # Create new subsection after Unreleased header
            header_end = text.find("\n", idx) + 1
            if header_end == 0:
                header_end = idx + len(unreleased) + 1
            new_text = text[:header_end] + f"\n{section_header}\n{entry}" + text[header_end:]
        from k3dge.engine.version import _atomic_write

        _atomic_write(changelog, new_text)
        return True
    except Exception as exc:
        import sys

        print(f"[WARN] _append_to_unreleased failed for {task_path.name}: {exc}", file=sys.stderr)
        return False


def _auto_backfill_reviews(workspace: Path, task_path: Path, task_title: str, milestone: str | None) -> None:
    """Best-effort auto-backfill for audit reviews when a task is marked done.

    - Finds `docs/reviews/*.md` whose 9-col table has a `待修` row whose `问题描述` contains the task title (or ID in task filename)
    - Flips `状态` to `已修` and `处置` to `已修 → <task file>` for that row
    - Appends/updates `## 回填` section with the task (idempotent)
    Never raises; prints WARN on failure (P3 light, not blocking).
    """
    import sys

    try:
        reviews_dir = workspace / "docs" / "reviews"
        if not reviews_dir.is_dir():
            return
        # Derive a searchable token from task: title words and file stem
        title_token = task_title.strip()
        stem_token = task_path.stem  # e.g. 2026-08-27-M6-fix-fix_AGENTS_route_05...
        # Milestone of the task, if any, narrows the review set
        milestone_token = (milestone or "").strip()
        for review_path in sorted(reviews_dir.glob("*.md")):
            if _is_review_aux(review_path.name):
                continue
            try:
                text = review_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            # Heuristic: only consider reviews that look like an audit (have 9-col header)
            if "ID|严重度|优先级|类型|问题描述|位置|状态|处置|验证" not in text.replace(" ", "").replace("|", "|"):
                # Quick check for required headers without strict whitespace
                if "ID" not in text or "问题描述" not in text or "状态" not in text:
                    continue
            # If task has a milestone, require the review to mention it (avoid cross-milestone noise)
            if milestone_token and not _has_milestone_token(text, milestone_token):
                # For k8d3e-a78 style reviews, milestone may be in tasks, not in review header;
                # fall back to title-token matching without milestone filter
                if title_token not in text and stem_token[:20] not in text:
                    continue
            lines = text.splitlines()
            header_idx = -1
            header_cols: list[str] | None = None
            for i, raw in enumerate(lines):
                stripped = raw.strip()
                if not stripped.startswith("|"):
                    continue
                cols = [c.strip() for c in stripped.strip("|").split("|")]
                # Skip separator line
                if cols and all(set(c.replace(":", "").replace("-", "").strip()) == set() or set(c) <= {"-", ":"} for c in cols):
                    continue
                # Detect 9-col header
                if "ID" in cols and "问题描述" in cols and "状态" in cols:
                    header_idx = i
                    header_cols = cols
                    break
            if header_idx == -1 or header_cols is None:
                continue
            # Find column indices
            try:
                id_idx = header_cols.index("ID")
                desc_idx = header_cols.index("问题描述")
                status_idx = header_cols.index("状态")
                disp_idx = header_cols.index("处置")
            except ValueError:
                continue
            changed = False
            fid = ""   # 表无匹配行时的绑定兜底（原 'fid' in locals() 探测属作用域耦合）
            new_lines = lines[:]
            for i in range(header_idx + 2, len(lines)):
                raw = lines[i]
                if not raw.strip().startswith("|"):
                    # End of table
                    break
                cols = [c.strip() for c in raw.strip("|").split("|")]
                if len(cols) != len(header_cols):
                    continue
                status = cols[status_idx]
                if status != "待修":
                    continue
                desc = cols[desc_idx]
                fid = cols[id_idx]
                # Match if task title is in desc, or fid in task stem, or desc words in title
                hit = False
                if title_token and title_token[:15] and title_token[:15] in desc:
                    hit = True
                elif fid and fid in stem_token:
                    hit = True
                elif desc and desc[:15] in title_token:
                    hit = True
                if not hit:
                    continue
                # Flip status and disposition
                cols[status_idx] = "已修"
                # Ensure disposition contains 已修
                disp = cols[disp_idx]
                if "已修" not in disp:
                    cols[disp_idx] = f"已修 → {task_path.name}（{disp[:40]}）" if disp else f"已修 → {task_path.name}"
                new_lines[i] = "| " + " | ".join(cols) + " |"
                changed = True
            if not changed:
                continue
            # Append/ensure ## 回填 section (quoted to avoid k3dit second-table check)
            backfill_marker = f"> | {fid or 'ID'} |"
            # Check if a backfill section already mentions this task
            if task_path.name not in text:
                # Find or create ## 回填 section at end
                if "## 回填" not in text:
                    new_lines.append("")
                    new_lines.append("## 回填 — 自动（`k3dge task done`）")
                    new_lines.append("")
                    new_lines.append(f"> | {fid if 'fid' in locals() and fid else 'ID'} | 待修 | 已修 | {task_path.name} | 自动回填 |")
                    new_lines.append(f"> | 已修 → {task_path.name} |")
                else:
                    # Append to existing 回填 block (after its header)
                    for j, ln in enumerate(new_lines):
                        if ln.strip().startswith("## 回填"):
                            # Insert after the header's next non-empty line
                            insert_at = j + 1
                            # Skip blank lines after header
                            while insert_at < len(new_lines) and not new_lines[insert_at].strip():
                                insert_at += 1
                            # Find end of existing quoted backfill lines
                            k = insert_at
                            while k < len(new_lines) and new_lines[k].lstrip().startswith(">"):
                                k += 1
                            new_lines.insert(k, f"> | {task_path.name} | 已修 | 自动回填 |")
                            break
            review_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            print(f"[INFO][REVIEW BACKFILL] {review_path.name}: {fid} → 已修 ({task_path.name})", file=sys.stderr)
    except Exception as exc:
        import sys

        print(f"[WARN][REVIEW BACKFILL] failed for {task_path.name}: {exc}", file=sys.stderr)


def _has_milestone_token(text: str, milestone_id: str) -> bool:
    """True iff `milestone_id` appears as a path/word token, not a substring of a longer id.

    `M1` must not match `M10` in filenames (`2026-08-23-M10-align.md`) or review body text.
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


# Docs that live inside a docs/<type>/ directory but are never content items:
# scaffolding/authoring files. Single source — task scanning and review scanning
# used to keep their own copies and drifted (AUTHORING.md leaked into `task list`).
_DOC_AUX_NAMES = frozenset({"README.md", "AUTHORING.md", "_template.md"})


def _is_doc_aux(name: str) -> bool:
    """True for structural files inside docs/<type>/ that are never items."""
    return name in _DOC_AUX_NAMES or name.startswith(".")


_REVIEW_AUX = _DOC_AUX_NAMES | frozenset({"LEFTOVERS.md", "leftovers.md"})
_FILENAME_MILESTONE_RE = re.compile(r"(?:^|[._-])(M\d+)(?:[._-]|$)", re.IGNORECASE)


def _is_review_aux(name: str) -> bool:
    return name in _REVIEW_AUX or name.startswith(".")


def _filename_milestone(name: str) -> str | None:
    m = _FILENAME_MILESTONE_RE.search(name)
    return m.group(1) if m else None


def _living_review_files(reviews_dir: Path) -> List[Path]:
    if not reviews_dir.is_dir():
        return []
    return sorted(
        f for f in reviews_dir.iterdir() if f.is_file() and f.suffix == ".md" and not _is_review_aux(f.name)
    )


def _reviews_to_archive(reviews_dir: Path, milestone_id: str, pass_mark: str) -> List[Path]:
    """Living reports for this milestone: filename token, or align-pass marker in body.

    Files named for another milestone stay at top-level.
    """
    out: List[Path] = []
    for path in _living_review_files(reviews_dir):
        named = _filename_milestone(path.name)
        if named and named != milestone_id:
            continue
        if _has_milestone_token(path.name, milestone_id):
            out.append(path)
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if pass_mark in text:
            out.append(path)
    return out


def _rewrite_leftover_links(workspace: Path, filename: str, new_href: str) -> None:
    leftovers = workspace / "docs" / "reviews" / "LEFTOVERS.md"
    if not leftovers.is_file():
        return
    try:
        text = leftovers.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return
    updated = text.replace(f"]({filename})", f"]({new_href})")
    updated = updated.replace(f"](./{filename})", f"]({new_href})")
    if updated != text:
        leftovers.write_text(updated, encoding="utf-8")


def _safe_archive_dir(workspace: Path, kind: str, milestone_id: str) -> Tuple[Optional[Path], str]:
    """Return (dir, error). dir is None on path escape."""
    root = (workspace / "docs" / kind / "archive").resolve()
    dest = (root / milestone_id).resolve()
    try:
        dest.relative_to(root)
    except ValueError:
        return None, (
            f"Invalid milestone id '{milestone_id}': archive path escapes docs/{kind}/archive/"
        )
    return dest, ""


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
        if _is_doc_aux(p.name):
            continue
        try:
            content = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        fm = parse_frontmatter(content)
        if fm:
            st = fm.get("status", "unknown").lower()
            m_id = fm.get("milestone", "").strip()
            pri = fm.get("priority", "").strip()
            t_m = TITLE_RE.search(content)
            title = t_m.group(1).strip() if t_m else p.stem
        else:
            s_m = STATUS_RE.search(content)
            m_m = MILESTONE_RE.search(content)
            p_m = PRIORITY_RE.search(content)
            t_m = TITLE_RE.search(content)
            st = s_m.group(1).lower() if s_m else "unknown"
            m_id = m_m.group(1).strip() if m_m else ""
            pri = p_m.group(1).strip() if p_m else ""
            title = t_m.group(1).strip() if t_m else p.stem
        if want_ms is not None and m_id != want_ms:
            continue
        if want_status is not None and st != want_status:
            continue
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
    report: Optional[str] = None,
) -> Tuple[bool, str, Optional[Path]]:
    """Write a living task file. Returns (ok, message, path).

    `report` (ADR-0022): a `docs/reviews/<file>.md` pointer binding this task to an
    audit report — 1 report = 1 task. When set, `mark_task_done` requires the report
    to reach 待修==0 before the task can close.
    """
    if typ not in _TASK_TYPES:
        return False, f"invalid type '{typ}'", None
    if milestone is not None:
        err = _validate_milestone_id(milestone)
        if err:
            return False, err, None
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
    # Frontmatter (strict) + human-readable body (backward compat)
    fm_lines = ["---", f"status: idea"]
    if milestone:
        fm_lines.append(f"milestone: {milestone}")
    fm_lines.append(f"priority: {priority}")
    fm_lines.append(f"date: {date}")
    if report:
        fm_lines.append(f"report: {report}")
    fm_lines.append("---")
    fm_block = "\n".join(fm_lines)
    milestone_line = f"- **Milestone**: {milestone}\n" if milestone else ""
    report_line = f"- **Report**: `{report}`\n" if report else ""
    content = (
        f"{fm_block}\n\n"
        f"# {title}\n\n"
        f"- **Status**: idea\n"
        f"{milestone_line}"
        f"- **Priority**: {priority}\n"
        f"- **Date**: {date}\n"
        f"{report_line}"
        f"\n"
        f"## 已确认意图\n{title}\n\n"
        f"## 可检索摘要\n{title}\n\n"
        f"## 上下文/切入点\n{title}\n"
    )
    target.write_text(content, encoding="utf-8")
    return True, f"created {target.relative_to(workspace)}", target


def _task_report_pointer(content: str) -> str:
    """A task's bound report path (frontmatter `report:` or body `- **Report**:`)."""
    fm = parse_frontmatter(content)
    rep = (fm.get("report") or "").strip()
    if not rep:
        m = re.search(r"-\s+\*\*Report\*\*:\s*`?([^`\n]+?)`?\s*$", content, re.MULTILINE)
        rep = m.group(1).strip() if m else ""
    return rep


def _report_open_findings(workspace: Path, report_rel: str) -> Optional[List[str]]:
    """待修 IDs still open in a report; None if the report can't be read (don't block)."""
    p = workspace / report_rel
    if not p.is_file():
        return None
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return _parse_audit_stats(text).get("_ids_待修", [])


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
        if resolved.is_file() and not _is_doc_aux(resolved.name):
            target = resolved
    except (ValueError, OSError):
        target = None
    if target is None:
        name_only = Path(ident).name
        matches = [
            p
            for p in sorted(tasks_dir.glob("*.md"))
            if not _is_doc_aux(p.name) and (ident in p.name or ident in p.stem or name_only == p.name)
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
    fm = parse_frontmatter(content)
    # ADR-0022: a task bound to an audit report can only close when that report has
    # no open 待修 findings (1 report = 1 task; closing the task == audit closure).
    report_rel = _task_report_pointer(content)
    already_done = (fm.get("status", "").lower() == "done") or bool(
        re.search(r"-\s+\*\*Status\*\*:\s*done\b", content, re.IGNORECASE)
    )
    if report_rel and not already_done:
        pending = _report_open_findings(workspace, report_rel)
        if pending:
            return False, (
                f"报告 {report_rel} 仍有 {len(pending)} 条待修（{', '.join(pending[:8])}）；"
                f"先把这些行改成 已修/有意留 再关 task"
                f"（特别大的单条可在 `处置` 写 `转 sub-task <id>` 例外拆出）。"
            ), target
    if fm and "status" in fm:
        # Strict frontmatter path
        if fm.get("status", "").lower() == "done":
            return True, f"already done: {target.name}", target
        # Replace frontmatter status: done
        new_content = re.sub(r"(?m)^status:\s*.*$", "status: done", content, count=1)
        # Also keep body sync for human readability
        new_content = re.sub(r"-\s+\*\*Status\*\*:\s*[\w-]+", "- **Status**: done", new_content, count=1)
        if new_content == content:
            return False, f"no Status field in {target.name}", target
        target.write_text(new_content, encoding="utf-8")
    else:
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
    # Directly append human summary to CHANGELOG.md Unreleased (no separate draft file)
    ok_append = _append_to_unreleased(workspace, target)
    if not ok_append:
        import sys

        print(f"[WARN] mark_task_done: CHANGELOG update failed for {target.name}", file=sys.stderr)
    # Auto-backfill audit reviews (light, not blocking)
    try:
        # Extract title/milestone for backfill matching
        t_content = target.read_text(encoding="utf-8")
        t_m = TITLE_RE.search(t_content)
        t_title = t_m.group(1).strip() if t_m else target.stem
        fm2 = parse_frontmatter(t_content)
        t_ms = fm2.get("milestone", "").strip() if fm2 else ""
        if not t_ms:
            mm = MILESTONE_RE.search(t_content)
            t_ms = mm.group(1).strip() if mm else ""
        _auto_backfill_reviews(workspace, target, t_title, t_ms)
    except Exception:
        pass
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
        f"  Milestone is seal-eligible. Audit is mandatory before seal "
        f"(k3dge milestone seal -> enter-seal prompt -> k3dit.actions.audit)."
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

    # 闸机 2: docs/guides/ 不得残留 k3dge:guide-stub
    unfilled = scan_unfilled_guides(workspace)
    if unfilled:
        return False, (
            f"[SEAL REJECTED] Unfilled guide stubs detected in docs/guides/: {unfilled}.\n"
            f"  Complete the documentation before milestone seal."
        )

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

_AUDIT_HEADER = "ID|日期|严重度|优先级|类型|问题描述|位置|状态|处置|验证|复审|验收"


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


_QUALITY_MARKER_RE = re.compile(r"k3dge:kind:\s*quality", re.IGNORECASE)


def _report_kind(name: str, text: str) -> str:
    """Classify a 12-col report as 'quality' (k3lity) or 'audit' (k3dit)."""
    if _QUALITY_MARKER_RE.search(text) or "-quality" in name.lower():
        return "quality"
    return "audit"


def _find_report(workspace: Path, milestone_id: str, kind: str = "audit"):
    """Return (path, text) of the most recent 12-col report of the given kind."""
    reviews = workspace / "docs" / "reviews"
    if not reviews.is_dir():
        return None
    candidates = []
    for f in reviews.iterdir():
        if not (f.is_file() and f.suffix == ".md" and not _is_review_aux(f.name)):
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if _AUDIT_HEADER.replace(" ", "") not in text.replace(" ", ""):
            continue
        if _report_kind(f.name, text) != kind:
            continue
        if milestone_id and not _has_milestone_token(text, milestone_id):
            fn_ms = _filename_milestone(f.name)
            if fn_ms and fn_ms != milestone_id:
                continue
        candidates.append((f.stat().st_mtime, f, text))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1], candidates[0][2]


def _find_audit_report(workspace: Path, milestone_id: str):
    """Most recent audit (k3dit) report. Back-compat wrapper for kind='audit'."""
    return _find_report(workspace, milestone_id, "audit")


def persist_external_audit_report(
    workspace: Path,
    milestone_id: str,
    content: str,
    scope: str = "external",
    kind: str = "audit",
) -> Path:
    """Persist a human/agent-submitted audit report as the canonical on-disk report.

    External audit sources (a human pasting a report into the dialog, or an agent
    forwarding one) must be landed under docs/reviews/ so the seal flow can gate on
    it via `_find_audit_report` / `_parse_audit_stats`. If the content lacks the
    12-col header, a canonical header is prepended so downstream parsing works; the
    latest submission for a (milestone, scope) overwrites any prior one.
    """
    reviews = workspace / "docs" / "reviews"
    reviews.mkdir(parents=True, exist_ok=True)
    norm = (content or "").replace(" ", "")
    if _AUDIT_HEADER.replace(" ", "") not in norm:
        header = (
            f"# 外部审计报告（人工提交，milestone {milestone_id}）\n\n"
            "| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
        )
        content = header + (content.strip() + "\n" if content.strip() else "")
    today = datetime.date.today().isoformat()
    if kind == "quality" and not _QUALITY_MARKER_RE.search(content):
        content = f"<!-- k3dge:kind: quality -->\n{content}"
    suffix = "quality" if kind == "quality" else "audit"
    path = reviews / f"{today}-{milestone_id}-{scope}-{suffix}.md"
    path.write_text(content.strip() + "\n", encoding="utf-8")
    return path


def _parse_audit_stats(text: str) -> dict:
    """Count 待修 / 有意留 / 已修 rows in a 12-col audit table."""
    counts = {"待修": 0, "有意留": 0, "已修": 0, "total": 0}
    lines = text.splitlines()
    header_idx = -1
    header_cols = None
    for i, raw in enumerate(lines):
        s = raw.strip()
        if not s.startswith("|"):
            continue
        cols = [c.strip() for c in s.strip("|").split("|")]
        if cols and set("".join(cols)) <= set("-: ") and any(set(c) for c in cols):
            continue  # separator row
        if "ID" in cols and "状态" in cols:
            header_idx = i
            header_cols = cols
            break
    if header_idx == -1 or header_cols is None:
        return counts
    try:
        status_idx = header_cols.index("状态")
        id_idx = header_cols.index("ID")
    except ValueError:
        return counts
    for raw in lines[header_idx + 1 :]:
        s = raw.strip()
        if not s.startswith("|"):
            break
        cols = [c.strip() for c in s.strip("|").split("|")]
        if len(cols) != len(header_cols):
            continue
        status = cols[status_idx]
        if status in counts:
            counts[status] += 1
            counts["total"] += 1
            counts.setdefault("_ids_" + status, []).append(cols[id_idx])
    return counts


def _ensure_leftovers(workspace: Path, text: str, report_path: Path) -> None:
    """Append 有意留 rows to docs/reviews/LEFTOVERS.md (idempotent by row ID)."""
    counts = _parse_audit_stats(text)
    if counts["有意留"] == 0:
        return
    ids = counts.get("_ids_有意留", [])
    if not ids:
        return
    leftover_path = workspace / "docs" / "reviews" / "LEFTOVERS.md"
    existing = leftover_path.read_text(encoding="utf-8") if leftover_path.is_file() else ""
    new_lines = []
    for rid in ids:
        marker = f"| {rid} |"
        if marker in existing or marker in "\n".join(new_lines):
            continue
        new_lines.append(f"> | {rid} | 有意留 | 见 {report_path.name} |")
    if not new_lines:
        return
    block = "\n".join(new_lines) + "\n"
    if "## 有意留" not in existing:
        block = "\n## 有意留（审计有意保留，非待修）\n" + block
    leftover_path.write_text(existing + block, encoding="utf-8")


class _Prompt:
    """Tiny interactive prompter; testable via `answers` injection."""

    def __init__(self, in_stream=None, out_stream=None, answers=None):
        self.in_stream = in_stream
        self.out_stream = out_stream
        self.answers = answers
        self._ai = 0

    @classmethod
    def default(cls) -> "_Prompt":
        import sys

        return cls(sys.stdin, sys.stdout)

    def _write(self, s: str) -> None:
        if self.out_stream is not None:
            print(s, file=self.out_stream, end="", flush=True)

    def isatty(self) -> bool:
        if self.answers is not None:
            return False  # injected answers => deterministic, never block
        return bool(getattr(self.in_stream, "isatty", lambda: False)())

    def ask(self, question: str, *, countdown=None, default_yes=False) -> bool:
        default = "Y/n" if default_yes else "y/N"
        if countdown:
            suffix = f" [{default}, {countdown}s default {'Y' if default_yes else 'N'}]"
        else:
            suffix = f" [{default}]"
        self._write(question + suffix + ": ")
        if self.answers is not None:
            ans = (
                self.answers[self._ai]
                if self._ai < len(self.answers)
                else ("y" if default_yes else "n")
            )
            self._ai += 1
            return str(ans).strip().lower() in ("y", "yes")
        if not self.isatty():
            return default_yes
        try:
            if countdown:
                import select

                rlist, _, _ = select.select([self.in_stream], [], [], countdown)
                if not rlist:
                    self._write(("Y" if default_yes else "N") + "\n")
                    return default_yes
                ans = self.in_stream.readline().strip().lower()
            else:
                ans = self.in_stream.readline().strip().lower()
        except (EOFError, OSError):
            return default_yes
        return ans in ("y", "yes")


def _write_closure_note(workspace: Path, milestone_id: str) -> Path:
    """Emit the context-compression closure checklist for a sealed milestone.

    k3dge seals the mechanical part (archive + version + pointer); the real
    "收摊" is compressing context — documenting the unadopted/failed options,
    pruning unrelated context, updating design docs, then committing. k3dge
    cannot judge what is unrelated, so it lays down the checklist and stops.
    """
    today = datetime.date.today().isoformat()
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
            ]
        ),
        encoding="utf-8",
    )
    return p


_AUDIT_EXCLUDE_DOCS = ("docs/reviews/", "docs/tasks/", "docs/generated/")


def _changed_docs(workspace: Path) -> List[str]:
    """Managed docs in the current change set that warrant an authoring audit.

    Excludes process artifacts (reviews/tasks/generated) and archives.
    """
    import subprocess

    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"], cwd=workspace, capture_output=True, text=True
        )
        files = [ln[3:].strip() for ln in out.stdout.splitlines() if ln.strip()]
    except Exception:
        return []
    docs: List[str] = []
    for f in files:
        if not f.startswith("docs/"):
            continue
        parts = set(f.split("/"))
        if "archive" in parts or any(f.startswith(p) for p in _AUDIT_EXCLUDE_DOCS):
            continue
        docs.append(f)
    return docs


def _ensure_doc_audit_task(workspace: Path, milestone_id: str, docs: List[str], report: Optional[str] = None):
    """Idempotently open a milestone-scoped doc-audit task (the durability hook).

    Because the task carries `Milestone` (and a `report:` pointer, ADR-0022), the
    seal gate (all tasks done) forces it to be cleared in the milestone round even
    if nobody acts on it at commit time. Returns the new task path, or None if an
    open one already exists.
    """
    for t in scan_milestone_tasks(workspace, milestone_id):
        # create_task 把标题折成下划线文件名（doc_audit_*）——只匹配 "doc-audit" 会漏检，
        # 于是每次 doc-audit 都开重复 task（2026-09-03 实测 _4 存在仍建出 _39）。
        name = t.path.name.lower()
        if ("doc-audit" in name or "doc_audit" in name) and t.status != "done":
            return None
    scopes = sorted({d.split("/")[1] for d in docs if len(d.split("/")) > 1})
    hint = ", ".join(scopes[:3]) or "docs"
    title = f"doc-audit: 文档作者合规审计（{hint} 等 {len(docs)} 处）"
    ok, _msg, path = create_task(workspace, title, typ="audit", milestone=milestone_id, priority="P3", report=report)
    return path if ok else None



def _similar_task_hints(workspace: Path, title: str, exclude: Optional[Path] = None) -> List[Tuple[str, str]]:
    """k3che 相似/历史提示——service 语义：skip/失败/坏信封 ⇒ 无提示，**永不阻断创建**。

    语料含 tasks/archive（CacheIndex.rglob 覆盖归档子目录）——历史文件正是重复的
    本体。只提示，不判定：是不是真重复由看的人决定（规则 08：观测≠裁决）。
    """
    from k3dge.engine.pipeline_runner import run_action

    try:
        res = run_action(workspace, "cache.search", arguments={"query": title, "top_k": 6})
    except Exception:  # pragma: no cover - 观测件绝不误伤创建
        return []
    if not res.ok or res.provider != "mcp":
        return []
    try:
        env = json.loads(res.payload or "")
    except ValueError:
        return []
    if not isinstance(env, dict) or not env.get("ok"):
        return []
    excl = exclude.relative_to(workspace).as_posix() if exclude is not None else None
    out: List[Tuple[str, str]] = []
    for r in env.get("results") or []:
        p = str(r.get("path") or "")
        if not p or p == excl:
            continue
        out.append((p, str(r.get("title") or "")))
        if len(out) >= 3:
            break
    return out

# --- k3che 相关文档前路由（service 角色：只产提示，永不进判定链；peer contract §0） ---

_K3CHE_HINT_RE = re.compile(r"<!-- k3che-hints -->.*?<!-- /k3che-hints -->\n?", re.S)


def _related_doc_hints(workspace: Path, docs: List[str], io=None) -> List[Tuple[str, str]]:
    """Ask the cache role for docs related to the changed ones. Any failure ⇒ [] (silent-safe)."""
    from k3dge.engine.pipeline_runner import run_action

    names = [Path(d).name for d in docs[:6] if d]
    if not names:
        return []
    try:
        res = run_action(workspace, "cache.search", io=io, arguments={"query": " ".join(names), "top_k": 3})
    except Exception:  # pragma: no cover - service call must never break the flow
        return []
    if not res.ok or res.provider != "mcp":
        return []  # skip/降级 = 没有提示，仅此而已
    try:
        env = json.loads(res.payload or "")
    except ValueError:
        return []
    out: List[Tuple[str, str]] = []
    for r in env.get("results") or []:
        if isinstance(r, dict) and r.get("path"):
            out.append((str(r["path"]), str(r.get("title", ""))))
        if len(out) >= 3:
            break
    return out


def _attach_k3che_hints(workspace: Path, docs: List[str], io=None) -> int:
    """Write/refresh the hints block on the open doc-audit task. Returns #hints written."""
    hints = _related_doc_hints(workspace, docs, io=io)
    if not hints:
        return 0
    tasks_dir = workspace / "docs" / "tasks"
    if not tasks_dir.is_dir():
        return 0
    target = None
    for p in sorted(tasks_dir.glob("*.md")):
        # create_task 把标题里的非字母数字折成下划线：文件名是 doc_audit_*，标题是 doc-audit:
        if p.name.endswith(".done.md") or _is_doc_aux(p.name):
            continue
        if "doc-audit" not in p.name.lower() and "doc_audit" not in p.name.lower():
            continue
        target = p
        break
    if target is None:
        return 0
    block = (
        "<!-- k3che-hints -->\n"
        "## 相关文档提示（k3che · 服务性前路由，非判定；由审计席位取舍）\n\n"
        + "".join(f"- `{path}`" + (f" — {title}" if title else "") + "\n" for path, title in hints)
        + "<!-- /k3che-hints -->\n"
    )
    text = target.read_text(encoding="utf-8")
    text = _K3CHE_HINT_RE.sub("", text).rstrip() + "\n\n" + block
    target.write_text(text, encoding="utf-8")
    return len(hints)


def run_doc_audit(workspace: Path, *, io=None) -> Tuple[str, str]:
    """Non-blocking doc-audit, run AFTER the hard gate (never inside `check`).

    k3dge keeps `check` static (no MCP/LLM — T-01). This step: routes the doc lens
    to k3dit (authoring compliance; ADR conflict/coverage stays in the milestone
    audit), and guarantees a milestone-scoped task so the finding cannot slip.
    Always non-blocking (returns cleanly even if the peer is unavailable).
    status ∈ {reported, clean}.
    """
    import sys

    from k3dge.engine.pipeline_runner import run_action

    io = io or sys.stderr
    mid = get_current_milestone(workspace)
    docs = _changed_docs(workspace)
    if not docs:
        return "clean", "no managed docs changed; nothing to doc-audit."

    try:
        # docs/ targets must route to the Doc Audit lens, not the code passes
        run_action(
            workspace,
            "k3dit.actions.audit",
            io=io,
            arguments={"target_scope": "docs", "milestone_id": mid or ""},
        )  # peer/manual authors the report
    except Exception:
        pass
    # Bind the task to the report it audits (1 report = 1 task, ADR-0022) if present.
    found = _find_report(workspace, mid, "audit")
    report_rel = found[0].relative_to(workspace).as_posix() if found else None
    task = _ensure_doc_audit_task(workspace, mid, docs, report=report_rel)
    _attach_k3che_hints(workspace, docs, io=io)  # 服务性提示；失败=无提示，绝不无审计
    if task is None:
        return "reported", (
            f"doc-audit: {len(docs)} 处文档改动；已有未关闭的 doc-audit task（不重复建）。"
        )
    return "reported", (
        f"doc-audit: 报告由 k3dit/人产出，已开里程碑 task `{task.name}`（非阻断；本轮不改，封板闸也会逼这轮闭环）。"
    )


def _audit_mode(workspace: Path, role: str = "audit") -> str:
    """审计腿形状：`[roles.audit] mode="ratchet"`＝工单模式（ADR-0026）；缺省 scaffold（旧形）。"""
    try:
        try:
            import tomllib
        except ModuleNotFoundError:  # pragma: no cover
            import tomli as tomllib  # type: ignore

        data = tomllib.loads((workspace / ".agent" / "pipeline.toml").read_text(encoding="utf-8"))
        return str((data.get("roles") or {}).get(role, {}).get("mode", "scaffold")).lower()
    except Exception:
        return "scaffold"


def _ratchet_audit_step(workspace: Path, milestone_id: str, io=None, role: str = "audit") -> Tuple[str, str]:
    """审计腿一步（ratchet）：建单→探单→collect→（merge 欠账幂等重试）。一步一返回，进程不等人。"""
    from k3dge.engine import audit_flow
    from k3dge.engine import worktree as _wt

    state = audit_flow._load_state(workspace)
    mine = [j for j in state.get("jobs", []) if j.get("milestone_id") == milestone_id
            and j.get("role", "audit") == role]
    pending_merge = [j for j in mine if j.get("state") == "collected" and not j.get("merge_ok", True)]
    if pending_merge:
        j = pending_merge[-1]
        # 编排自家产物（state/checklist/reviews/tasks）不是"人的未提交"；原则性白名单
        r = _wt.merge_back(workspace, j.get("milestone_id") or "adhoc",
                           accept_dirty=(audit_flow.STATE_REL, ".agent/audit_checklist.json",
                                         "docs/reviews/", "docs/tasks/"))
        if r.get("ok"):
            j["merge_ok"] = True
            audit_flow._save_state(workspace, state)
            return "closed", f"写回重试成功（{r.get('mode')}）。"
        return "stalled", f"写回仍未闭（{r.get('mode')}）：{r.get('message', '')[:90]}——人工 rebase 后再跑本命令幂等重试。"
    inflight = [j for j in mine if j.get("state") not in ("collected", "failed")]
    if not inflight:
        done = [j for j in mine if j.get("state") == "collected" and j.get("merge_ok", True) and j.get("report")]
        if done:  # 本里程碑已有签署报告且写回闭 ⇒ 审计腿即成（新鲜度与旧链同形：报告在场为凭）
            return "closed", f"本里程碑签署报告已闭环（{done[-1]['report']}；待修 {done[-1].get('counts', {}).get('待修', '?')}）。"
        r = audit_flow.submit_audit(workspace, milestone_id, io=io, role=role)
        if not r.get("ok"):
            return "stalled", f"建单失败：{str(r.get('detail') or r.get('state'))[:120]}"
        return "progress", f"棘轮工单已建：{r['job_id']}（{role} 腿判据在机构侧席位，k3dge 不代笔）。"
    j = inflight[-1]
    st = audit_flow.peer_status(workspace, j["job_id"], io=io)
    if not st.get("ok"):
        return "progress", f"工单 {j['job_id']} 对端不可探：{str(st.get('message', ''))[:80]}"
    if st.get("escalated"):
        return "stalled", f"工单 {j['job_id']} 有升级条目 {st['escalated']}：等人 k3dit adjudicate。"
    if st.get("state") == "done":
        c = audit_flow.collect_audit(workspace, milestone_id, j["job_id"], io=io)  # role 随工单记录走
        if c.get("ok"):
            if c.get("merge", {}).get("ok") is False:
                return "stalled", f"报告已落位但写回未闭：{c['merge'].get('message', '')[:90]}"
            return "closed", f"签署报告落位 {c.get('report')}；写回 {c.get('merge', {}).get('mode', 'n/a')}；待修 {c.get('pending')}。"
        return "progress", f"collect 未通过：{str(c.get('message') or c.get('error') or c.get('state'))[:100]}"
    return "progress", f"工单 {j['job_id']} 对端态 {st.get('state')}，open={st.get('open', [])}。"


def run_audit_flow(
    workspace: Path,
    milestone_id: str,
    *,
    prompter: Optional[_Prompt] = None,
    max_verify_attempts: int = 3,
) -> Tuple[str, str]:
    """Independent audit entry: BOTH k3dit.audit and k3lity.quality produce 12-col
    reports, each must reach 待修==0 to count as "audited once". Verify is
    per-report (audit→audit report, quality→quality report). Returns
    (status, message); status ∈ {audited, rejected, escalated}. Seal unlocks only
    after this closes (`run_seal_flow`).
    """
    from k3dge.engine import audit_checklist as ac, nextstep
    from k3dge.engine.pipeline_runner import run_action

    prompt = prompter or _Prompt.default()
    # Initiating an audit resets the condition checklist (fresh verify budget +
    # started_at stamp), whether triggered manually (`milestone audit`) or via a hook.
    ac.reset_for_audit(workspace, milestone_id)

    ratchet = _audit_mode(workspace) == "ratchet"
    if ratchet:
        # 审计腿＝工单步进（ADR-0026）：一次调用推一步，绝不在闸里等席；步没 closed 就交回 [NEXT]。
        step_status, step_msg = _ratchet_audit_step(workspace, milestone_id, io=prompt.out_stream)
        if step_status != "closed":
            if step_status == "progress":
                return "ratchet_open", step_msg + "\n" + nextstep.NextStep.from_state(
                    "ratchet_open", milestone_id, reasons=[step_msg[:120]]).render_cli()
            return "escalated", step_msg + "\n" + nextstep.NextStep.from_state(
                "escalated", milestone_id).render_cli()

    # kind -> (produce action, verify action)；ratchet 模式下审计腿已经工单闭环，只剩 quality
    streams = {
        "audit": ("k3dit.actions.audit", "k3dit.actions.verify"),
        "quality": ("k3lity.actions.quality", "k3lity.actions.verify"),
    }
    if ratchet:
        streams.pop("audit")
    # quality 腿同形换源（09-04）：roles.quality.mode="ratchet" ⇒ 与审计腿同一工单步进
    if _audit_mode(workspace, "quality") == "ratchet":
        q_status, q_msg = _ratchet_audit_step(workspace, milestone_id, io=prompt.out_stream, role="quality")
        if q_status != "closed":
            if q_status == "progress":
                return "ratchet_open", q_msg + "\n" + nextstep.NextStep.from_state(
                    "ratchet_open", milestone_id, reasons=["quality 腿: " + q_msg[:100]]).render_cli()
            return "escalated", q_msg + "\n" + nextstep.NextStep.from_state(
                "escalated", milestone_id).render_cli()
        streams.pop("quality", None)

    # mandatory audit + fix loop, capped at `max_verify_attempts` verifies.
    while True:
        attempts = ac.get_verify_attempts(workspace)
        if attempts >= max_verify_attempts:
            msg = f"verify 已超过 {max_verify_attempts} 次仍未闭环，停止自动 loop，转人工干预。"
            return "escalated", msg + "\n" + nextstep.NextStep.from_state("escalated", milestone_id).render_cli()
        ac.bump_verify_attempt(workspace)

        # produce phase: run every stream, then collect its report.
        pending_total = 0
        for kind, (produce_action, _verify_action) in streams.items():
            # Action-level arguments only — no pass numbers (ADR-0006 §2.3.8). The lens
            # entry decides internally how many passes that takes.
            produced = run_action(
                workspace,
                produce_action,
                io=prompt.out_stream,
                arguments={"target_scope": f"milestone {milestone_id}", "milestone_id": milestone_id},
            )
            found = _find_report(workspace, milestone_id, kind)
            if found is None:
                hint = ""
                try:
                    import json as _json

                    _body = _json.loads(produced.payload) if produced.payload else {}
                    if _body.get("report_path"):
                        hint = (
                            f" {produced.provider} 已给出落点建议 `{_body['report_path']}`"
                            f"（lens_count={_body.get('lens_count')}）；k3dge 不代笔正文。"
                        )
                except (ValueError, AttributeError):
                    pass
                msg = (
                    f"Audit is mandatory: no 12-col {kind} report found under docs/reviews/. "
                    f"Persist one (`k3dge milestone audit-submit {milestone_id} ... --scope ...` "
                    f"or run the peer per docs/protocols/) and re-run audit.{hint}"
                    + ("" if not produced.downgrades else
                       f" [本轮降级：{'; '.join(produced.downgrades)}]")
                )
                return "rejected", msg + "\n" + nextstep.next_for_rejection(milestone_id, msg).render_cli()
            report_path, report_text = found
            stats = _parse_audit_stats(report_text)
            _ensure_leftovers(workspace, report_text, report_path)
            pending_total += stats["待修"]

        if pending_total == 0:
            break
        # 待修 > 0 across reports -> surface the next-step hint, then ask agent to fix.
        prompt._write(
            nextstep.NextStep.from_state("audit_open", milestone_id, pending=pending_total).render_cli() + "\n"
        )
        if not prompt.ask(
            f"审计/质量共发现 {pending_total} 项待修。是否由 agent 修复？（超时默认修复）",
            countdown=60,
            default_yes=True,
        ):
            msg = f"Audit open: {pending_total} 项待修未修复且 agent 拒绝修复。"
            return "rejected", msg + "\n" + nextstep.NextStep(
                state="rejected", milestone=milestone_id, note="stop / 转人工干预（待修未修复且 agent 拒绝修复）"
            ).render_cli()
        # agent fixes externally -> loop re-runs audit AND quality, each verifying its own report
        continue

    # verify phase: per-report secondary cross-check (audit→audit, quality→quality).
    for _kind, (_produce_action, verify_action) in streams.items():
        # Verify is per-report and needs to be told *which* report (the check tools take a
        # path); without this the mcp transport can never succeed and falls to manual.
        found = _find_report(workspace, milestone_id, _kind)
        verify_args = {"milestone_id": milestone_id}
        if found:
            verify_args["path"] = str(found[0].relative_to(workspace).as_posix())
        try:
            run_action(workspace, verify_action, io=prompt.out_stream, arguments=verify_args)
        except Exception:
            pass
    ac.reset_verify_attempts(workspace)
    msg = f"Milestone {milestone_id}: 审计闭环（audit + quality 报告 待修=0），可以谈封板。"
    return "audited", msg + "\n" + nextstep.NextStep.from_state("seal_ready", milestone_id).render_cli()


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

    if not audit_closed(workspace, milestone_id):
        msg = f"Milestone {milestone_id}: 未审计（待修未归零或无 12 列报告），不可封板。"
        return "audit_needed", msg + "\n" + nextstep.NextStep.from_state("audit_needed", milestone_id).render_cli()

    # enter-seal prompt — NO countdown; N = keep milestone open. Skipped with --yes.
    if not skip_enter_prompt and not prompt.ask(
        f"里程碑 {milestone_id} 审计已闭环，封板？", default_yes=False
    ):
        msg = f"Milestone {milestone_id}: seal deferred — 不封，里程碑继续挂着。"
        return "deferred", msg + "\n" + nextstep.NextStep.from_state("deferred", milestone_id).render_cli()

    # align (Full Matrix) if not yet run this cycle, then archive.
    ok, amsg, _ = run_milestone_alignment(workspace, milestone_id)
    if not ok:
        return "rejected", amsg + "\n" + nextstep.next_for_rejection(milestone_id, amsg).render_cli()
    _strip_align_stub(workspace, milestone_id)

    ok, msg = seal_milestone(workspace, milestone_id)
    if not ok:
        return "rejected", msg + "\n" + nextstep.next_for_rejection(milestone_id, msg).render_cli()
    closure = _write_closure_note(workspace, milestone_id)
    msg += f"\n  收摊清单: {closure.relative_to(workspace)}"
    try:  # ⑤ end-flow 清理钩子：派生件（worktree/bundle）收口即焚，store 与合并后的分支史保留
        from k3dge.engine.audit_flow import prune_finished

        pr = prune_finished(workspace)
        if pr.get("pruned"):
            msg += f"\n  审计派生件清理: {pr['pruned']} 组"
    except Exception:
        pass
    return "sealed", msg + "\n" + nextstep.NextStep.from_state("sealed", milestone_id).render_cli()
