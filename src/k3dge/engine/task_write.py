"""Task 写入核心：创建 / 关闭（含报告闸、回填、CHANGELOG）。

Extracted from `engine/milestone.py` (A-1 第九块). All deps come from leaf modules
(task_index / audit_report / changelog / milestone_pointer / milestone_files) — no cycle.
"""
from __future__ import annotations

import datetime
import re
from pathlib import Path
import json
from typing import List, Optional, Tuple

from k3dge.engine import report_table
from k3dge.engine.audit_report import _parse_audit_stats
from k3dge.engine.changelog import _append_to_unreleased
from k3dge.engine.milestone_files import _has_milestone_token, _is_doc_aux, _is_review_aux
from k3dge.engine.milestone_pointer import _validate_milestone_id, get_current_milestone
from k3dge.engine.task_index import MILESTONE_RE, TITLE_RE, parse_frontmatter

_TASK_TYPES = frozenset({"audit", "feat", "fix", "docs", "chore", "refactor"})


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
            header, rows = report_table.parse_rows(
                text, required=("ID", "问题描述", "状态", "处置"))
            if header is None:
                continue
            lines = text.splitlines()
            new_lines = lines[:]
            changed = False
            fid = ""   # 表无匹配行时的绑定兜底
            for i, row in rows:
                if row.get("状态") != "待修":
                    continue
                desc = row.get("问题描述", "")
                fid = row.get("ID", "")
                hit = (
                    (title_token and title_token[:15] and title_token[:15] in desc)
                    or (fid and fid in stem_token)
                    or (desc and desc[:15] in title_token)
                )
                if not hit:
                    continue
                row["状态"] = "已修"
                disp = row.get("处置", "")
                if "已修" not in disp:
                    row["处置"] = (f"已修 → {task_path.name}（{disp[:40]}）" if disp
                                   else f"已修 → {task_path.name}")
                new_lines[i] = "| " + " | ".join(row[h] for h in header) + " |"
                changed = True
            if not changed:
                continue
            # Append/ensure ## 回填 section (quoted to avoid k3dit second-table check)
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


def create_task(
    workspace: Path,
    title: str,
    *,
    typ: str = "fix",
    slug: Optional[str] = None,
    milestone: Optional[str] = None,
    priority: str = "P2",
    report: Optional[str] = None,
    context: Optional[str] = None,
) -> Tuple[bool, str, Optional[Path]]:
    """Write a living task file. Returns (ok, message, path).

    `report` (ADR-0022): a `docs/reviews/<file>.md` pointer binding this task to an
    audit report — 1 report = 1 task. When set, `mark_task_done` requires the report
    to reach 待修==0 before the task can close.

    `context`: body for `## 上下文/切入点`. Callers that already know the concrete
    scope (e.g. the files a scan reported) must pass it — omitting it makes
    all three body sections repeat the title, producing a ticket nobody can execute.
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
    # Frontmatter 是任务元数据的**唯一源**（docs/tasks/AUTHORING.md）：正文不复写
    # status/milestone/priority/date/report——第二源只能漂移（机检码 TASK_BODY_META_REDUNDANT）。
    fm_lines = ["---", f"status: idea"]
    if milestone:
        fm_lines.append(f"milestone: {milestone}")
    fm_lines.append(f"priority: {priority}")
    fm_lines.append(f"date: {date}")
    if report:
        fm_lines.append(f"report: {report}")
    fm_lines.append("---")
    fm_block = "\n".join(fm_lines)
    content = (
        f"{fm_block}\n\n"
        f"# {title}\n\n"
        f"\n"
        f"## 已确认意图\n{title}\n\n"
        f"## 可检索摘要\n{title}\n\n"
        f"## 上下文/切入点\n{context or title}\n"
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


def _resolve_task_target(workspace: Path, ident: str, tasks_dir: Path, archive_dir: Path) -> Tuple[Optional[Path], Optional[str]]:
    """Resolve a done target from an exact path or unique filename substring; (path, error)."""
    raw = Path(ident)
    cand = raw if raw.is_absolute() else (workspace / ident)
    try:
        resolved = cand.resolve()
        resolved.relative_to(tasks_dir.resolve())
        # 阻断对 archive/ 目录内任务的修改（不可变性）
        if archive_dir.exists():
            try:
                resolved.relative_to(archive_dir.resolve())
                return None, f"cannot modify archived task: {ident}"
            except ValueError:
                pass
        if resolved.is_file() and not _is_doc_aux(resolved.name):
            return resolved, None
    except (ValueError, OSError):
        pass
    name_only = Path(ident).name
    matches = [
        p
        for p in sorted(tasks_dir.glob("*.md"))
        if not _is_doc_aux(p.name) and (ident in p.name or ident in p.stem or name_only == p.name)
    ]
    if not matches:
        return None, f"no task matching '{ident}'"
    if len(matches) > 1:
        names = ", ".join(p.name for p in matches)
        return None, f"multiple matches for '{ident}': {names}"
    return matches[0], None


def _rename_task_done(target: Path) -> Path:
    """Rename to `.done.md` unless already done or the target name is taken."""
    if target.name.endswith(".done.md"):
        return target
    new_path = target.parent / (target.name[:-3] + ".done.md")
    if new_path.exists():
        return target
    target.rename(new_path)
    return new_path


def _append_task_changelog(workspace: Path, target: Path) -> None:
    """Append the task title to CHANGELOG Unreleased; warn (non-blocking) on failure."""
    if not _append_to_unreleased(workspace, target):
        import sys

        print(f"[WARN] mark_task_done: CHANGELOG update failed for {target.name}", file=sys.stderr)


def _backfill_task_reviews(workspace: Path, target: Path) -> None:
    """Best-effort audit-review backfill when a task closes (never raises)."""
    import sys

    try:
        t_content = target.read_text(encoding="utf-8")
        t_m = TITLE_RE.search(t_content)
        t_title = t_m.group(1).strip() if t_m else target.stem
        fm2 = parse_frontmatter(t_content)
        t_ms = fm2.get("milestone", "").strip() if fm2 else ""
        if not t_ms:
            mm = MILESTONE_RE.search(t_content)
            t_ms = mm.group(1).strip() if mm else ""
        _auto_backfill_reviews(workspace, target, t_title, t_ms)
    except Exception as exc:
        print(f"[WARN] task done: 报告自动回填跳过（{target.name}: {exc}）；报告仍未回填，封板闸会兜底", file=sys.stderr)


def _finalize_task_done(workspace: Path, target: Path, content: str, fm: dict) -> Tuple[bool, str, Optional[Path]]:
    """Report gate -> flip status -> rename -> changelog -> review backfill."""
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
        # Strict frontmatter path（唯一源；正文不再有 Status 副本可同步）
        if fm.get("status", "").lower() == "done":
            return True, f"already done: {target.name}", target
        new_content = re.sub(r"(?m)^status:\s*.*$", "status: done", content, count=1)
        if new_content == content:
            return False, f"no Status field in {target.name}", target
        target.write_text(new_content, encoding="utf-8")
    else:
        # 遗留票（无 frontmatter）：body 即唯一源，仍按旧路改正文
        if re.search(r"-\s+\*\*Status\*\*:\s*done\b", content, re.IGNORECASE):
            return True, f"already done: {target.name}", target
        new_content = re.sub(r"-\s+\*\*Status\*\*:\s*[\w-]+", "- **Status**: done", content, count=1)
        if new_content == content:
            return False, f"no Status field in {target.name}", target
        target.write_text(new_content, encoding="utf-8")
    target = _rename_task_done(target)
    _append_task_changelog(workspace, target)
    _backfill_task_reviews(workspace, target)
    from k3dge.engine import events
    events.emit(workspace, "task_done", task=target.name)
    return True, f"marked done: {target.name}", target


def mark_task_done(workspace: Path, ident: str) -> Tuple[bool, str, Optional[Path]]:
    """Mark one living task done. Prefer exact path from list_tasks; else unique filename substring."""
    ident = ident.strip().replace("\\", "/")
    if not ident:
        return False, "done requires a path or unique filename substring", None
    tasks_dir = workspace / "docs" / "tasks"
    archive_dir = tasks_dir / "archive"
    if not tasks_dir.is_dir():
        return False, "docs/tasks/ missing", None
    target, err = _resolve_task_target(workspace, ident, tasks_dir, archive_dir)
    if target is None:
        return False, err or f"no task matching '{ident}'", None
    try:
        content = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return False, str(exc), target
    return _finalize_task_done(workspace, target, content, parse_frontmatter(content))


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
