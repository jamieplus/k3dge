"""Task 索引/读取（frontmatter 解析 + `docs/tasks/*.md` 扫描），extracted from `engine/milestone.py`
(A-1 第七块).
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from k3dge.engine.milestone_files import _is_doc_aux
from k3dge.engine.state_machine import TaskState

#: 合法 task status（**派生**，不另写一份词表）：词表的拥有者是 `state_machine.TaskState`，
#: 这里是它的消费者视图（align/seal 的 `invalid_task_status` 判据也用它）。
_ALLOWED_STATUS = frozenset(s.value for s in TaskState)

def audit_job_ticket_paths(workspace: Path) -> set:
    """棘轮工单票＝本地账 `ticket_task` 记下的路径，不是文件名模式。

    文件名含 `-audit-audit_job_` 也能开给人干活；闸只认账本指针，避免改名绕过
    `tasks_all_done`。账缺失 ⇒ 空集（无人待办豁免）。
    """
    import json

    p = workspace / ".agent" / "audit_jobs.json"
    if not p.is_file():
        return set()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    if not isinstance(raw, dict):        # 顶层非对象（数组/字符串）⇒ 优雅退化空集，不崩（ocr-113）
        return set()
    names: set = set()
    for job in raw.get("jobs") or []:
        if not isinstance(job, dict):    # 元素非对象也跳过（ocr-113）
            continue
        rel = str(job.get("ticket_task") or "").replace("\\", "/").strip()
        if rel:
            # 指针**保持路径**：降成 basename ⇒ 任何目录下同名文件都被豁免出 `work_pending`
            # （账本指针在 `docs/tasks/archive/<M>/X.md`、别的目录躺一份 `X.md` 就被误免，329）
            names.add(rel.lstrip("./"))
    return names


def work_pending(tasks: List[MilestoneTask], workspace: Optional[Path] = None) -> List[MilestoneTask]:
    """人待办：未 done，且不是账本里的棘轮工单票（按**指针路径**比，不比文件名）。"""
    skip = audit_job_ticket_paths(workspace) if workspace is not None else set()
    root = Path(workspace).resolve() if workspace is not None else None
    out: List[MilestoneTask] = []
    for t in tasks:
        if t.status == "done":
            continue
        rel = ""
        if root is not None:
            try:
                rel = t.path.resolve().relative_to(root).as_posix()
            except (OSError, ValueError):
                rel = ""
        if rel and rel in skip:
            continue
        out.append(t)
    return out

STATUS_RE = re.compile(r"-\s+\*\*Status\*\*:\s*([\w-]+)", re.IGNORECASE)
MILESTONE_RE = re.compile(r"-\s+\*\*Milestone\*\*:\s*([^\n\r]+)", re.IGNORECASE)
PRIORITY_RE = re.compile(r"-\s+\*\*Priority\*\*:\s*(\S+)", re.IGNORECASE)
TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def _frontmatter_pairs(content: str) -> List[tuple]:
    """唯一的 `---` frontmatter 解析：必须首行开、行内闭合；返回 `(原键, 值)` 列表。

    value-11：`doc_catalog._frontmatter` 与 `parse_frontmatter` 共用本函数，只差键大小写。
    未闭合块一律不算 frontmatter（防正文 `key: value` 被误当元数据）。
    """
    lines = content.splitlines()
    if len(lines) < 2 or lines[0].strip() != "---":
        return []
    pairs: List[tuple] = []
    for line in lines[1:]:
        if line.strip() == "---":
            return pairs
        if ":" in line:
            k, v = line.split(":", 1)
            pairs.append((k.strip(), v.strip()))
    return []


def parse_frontmatter(content: str) -> dict[str, str]:
    """Strict frontmatter parser: only `---` block at start, YAML-like `key: value`.

    Avoids `Markdown as Database` anti-pattern where body text containing
    `- **Status**:` is mis-captured. Pure stdlib, no external dep.
    """
    return {k.lower(): v for k, v in _frontmatter_pairs(content)}


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
    return _scan_task_dir(workspace / "docs" / "tasks", milestone_id, status)


def archived_milestone_tasks(workspace: Path, milestone_id: str) -> List[TaskIndex]:
    """`docs/tasks/archive/<M>/` 里 frontmatter milestone==M 的任务（提前归档检测）。

    约定：里程碑任务留 `docs/tasks/` 顶层，由 `milestone seal` 封板时 batch archive；
    提前手工归档会让 top-level 扫描器看不到任务，align/seal 现场被拒（见 M9 实战）。
    """
    return _scan_task_dir(workspace / "docs" / "tasks" / "archive" / milestone_id,
                          milestone_id=milestone_id)


def premature_archive_hint(workspace: Path, milestone_id: str) -> Optional[str]:
    """当前里程碑任务被提前归档时给出可操作提示；否则 None（对齐/封板被拒时用）。"""
    from k3dge.engine.milestone_pointer import get_current_milestone

    if (get_current_milestone(workspace) or "").strip() != milestone_id:
        return None
    arch = archived_milestone_tasks(workspace, milestone_id)
    if not arch:
        return None
    return (
        f"里程碑 {milestone_id} 的任务已被提前归档到 docs/tasks/archive/{milestone_id}/（{len(arch)} 张）；"
        f"约定＝**封板时 batch archive**（`milestone seal` 自动做）。"
        f"请把它们的 .done.md 移回 docs/tasks/ 顶层后重试。"
    )


def _scan_task_dir(
    tasks_dir: Path,
    milestone_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[TaskIndex]:
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
        except (OSError, UnicodeDecodeError) as exc:
            # 权限拒绝/seal 正在批量 move 这些 .md/断链软链接/目录名以 .md 结尾 都会抛 OSError：
            # 旧只捕 UnicodeDecodeError ⇒ 整份扫描中断，align/seal 现场崩而不是跳过一票（330）
            print(f"[task_index] WARN: 跳过读不出的票 {p}（{type(exc).__name__}: {exc}）",
                  file=sys.stderr)
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
