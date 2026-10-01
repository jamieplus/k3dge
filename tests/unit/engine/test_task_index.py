"""票索引的两条边界：账本豁免认**指针路径**（非 basename），读不出的票**出声跳过**（ocr-329/330）。"""

import contextlib
import io
import json
import tempfile
from pathlib import Path

from k3dge.engine.task_index import list_tasks, scan_milestone_tasks, work_pending
import shutil
import atexit


def _ws() -> Path:
    root = Path(tempfile.mkdtemp())
    atexit.register(shutil.rmtree, root, True)
    (root / "docs" / "tasks").mkdir(parents=True)
    return root


def _ticket(folder: Path, name: str, status: str = "idea") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    f = folder / name
    f.write_text(f"---\nstatus: {status}\nmilestone: M9\ndate: 2026-09-01\n---\n\n# x\n",
                 encoding="utf-8")
    return f


def test_pointer_matches_path_not_basename() -> None:
    ws = _ws()
    led = ws / "docs" / "tasks" / "archive" / "M9"
    in_ledger = _ticket(led, "same-name.md", status="done")
    live = _ticket(ws / "docs" / "tasks", "same-name.md")
    (ws / ".agent").mkdir(parents=True, exist_ok=True)
    (ws / ".agent" / "audit_jobs.json").write_text(json.dumps({"jobs": [
        {"job_id": "j", "milestone_id": "M9",
         "ticket_task": f"docs/tasks/archive/M9/{in_ledger.name}"}]}), encoding="utf-8")
    pending = work_pending(scan_milestone_tasks(ws, "M9"), ws)
    assert [t.path for t in pending] == [live], "同名不同路径的活票被账本指针误免"


def test_unreadable_ticket_is_skipped_loudly() -> None:
    ws = _ws()
    good = _ticket(ws / "docs" / "tasks", "2026-09-01-M9-feat-a.md")
    bad = _ticket(ws / "docs" / "tasks", "2026-09-01-M9-feat-b.md")
    bad.chmod(0o000)
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err):
            rows = list_tasks(ws)
    finally:
        bad.chmod(0o644)
    assert [r.path.name for r in rows] == [good.name]
    assert "WARN" in err.getvalue()


def test_empty_frontmatter_block_does_not_fall_back_to_body() -> None:
    """`---` 空块 ≠ 没有块：正文一行 `- **Status**: done` 不得冒充元数据（ocr-331）。"""

    ws = Path(tempfile.mkdtemp())
    atexit.register(shutil.rmtree, ws, True)
    d = ws / "docs" / "tasks"
    d.mkdir(parents=True)
    (d / "2026-09-01-M9-feat-a.md").write_text("---\n---\n\n# A\n\n- **Status**: done\n",
                                               encoding="utf-8")
    rows = list_tasks(ws)
    assert [r.status for r in rows] == ["unknown"], rows
