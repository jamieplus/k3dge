"""Task 索引/读取（frontmatter 解析 + `docs/tasks/*.md` 扫描），extracted from `engine/milestone.py`
(A-1 第七块). `milestone` re-exports these names for back-compat.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from k3dge.engine.milestone_files import _is_doc_aux

STATUS_RE = re.compile(r"-\s+\*\*Status\*\*:\s*([\w-]+)", re.IGNORECASE)
MILESTONE_RE = re.compile(r"-\s+\*\*Milestone\*\*:\s*([^\n\r]+)", re.IGNORECASE)
PRIORITY_RE = re.compile(r"-\s+\*\*Priority\*\*:\s*(\S+)", re.IGNORECASE)
TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


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
