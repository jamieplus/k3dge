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
    # 归档目录不在顶层扫描视野内：只传顶层列表测不出账本豁免（ocr2-124）。把归档票也传进去，
    # 断言它被豁免（不在 pending），活票仍在。
    from k3dge.engine.task_index import archived_milestone_tasks

    _all = scan_milestone_tasks(ws, "M9") + archived_milestone_tasks(ws, "M9")
    assert any(t.path == in_ledger for t in _all), "归档票须在输入里，否则豁免测不到"
    pending = work_pending(_all, ws)
    assert [t.path for t in pending] == [live], "同名不同路径的活票被账本指针误免"


def test_unreadable_ticket_is_skipped_loudly() -> None:
    """读不出要**跨平台必然**读不出（t-286）。

    旧夹具 `chmod(0o000)` 在 root（Docker/CI 常态）与 Windows 上根本不挡读——
    前提静默消失，断言随环境红/绿。换成同名的**目录**占住 `*.md` 路径：
    `read_text` 必抛 OSError，也省掉还原 chmod 的 finally。
    """
    ws = _ws()
    good = _ticket(ws / "docs" / "tasks", "2026-09-01-M9-feat-a.md")
    bad = ws / "docs" / "tasks" / "2026-09-01-M9-feat-b.md"
    bad.mkdir()
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        rows = list_tasks(ws)
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
