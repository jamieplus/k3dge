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
        changelog.write_text(new_text, encoding="utf-8")
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
            backfill_marker = f"> | {fid if 'fid' in locals() and fid else 'ID'} |"
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


_REVIEW_AUX = frozenset({"README.md", "AUTHORING.md", "_template.md"})
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


def _rewrite_review_readme_links(workspace: Path, filename: str, new_href: str) -> None:
    readme = workspace / "docs" / "reviews" / "README.md"
    if not readme.is_file():
        return
    try:
        text = readme.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return
    updated = text.replace(f"]({filename})", f"]({new_href})")
    updated = updated.replace(f"](./{filename})", f"]({new_href})")
    if updated != text:
        readme.write_text(updated, encoding="utf-8")


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
        if p.name in ("README.md", "_template.md"):
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
) -> Tuple[bool, str, Optional[Path]]:
    """Write a living task file. Returns (ok, message, path)."""
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
    fm_lines.append("---")
    fm_block = "\n".join(fm_lines)
    milestone_line = f"- **Milestone**: {milestone}\n" if milestone else ""
    content = (
        f"{fm_block}\n\n"
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
    fm = parse_frontmatter(content)
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

    readme_path = reviews_dir / "README.md"
    readme_orig: str | None = None
    if readme_path.is_file():
        try:
            readme_orig = readme_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            readme_orig = None

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
            _rewrite_review_readme_links(workspace, rev.name, f"archive/{milestone_id}/{rev.name}")
    except Exception as exc:
        if readme_orig is not None:
            try:
                readme_path.write_text(readme_orig, encoding="utf-8")
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
