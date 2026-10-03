"""票索引的两条边界：账本豁免认**指针路径**（非 basename），读不出的票**出声跳过**（ocr-329/330）。"""

import contextlib
import io
import json
from pathlib import Path

from k3dge.engine.task_index import list_tasks, scan_milestone_tasks, work_pending


# ocr2-794：旧 `_ws()` 手搓 mkdtemp + atexit（解释器退出才清；崩溃/xdist
# worker 挂时永久残留）。改吃调用方传进的 pytest `tmp_path`，按测回收。
def _ws(root: Path) -> Path:
    (root / "docs" / "tasks").mkdir(parents=True)
    return root


def _ticket(folder: Path, name: str, status: str = "idea") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    f = folder / name
    f.write_text(f"---\nstatus: {status}\nmilestone: M9\ndate: 2026-09-01\n---\n\n# x\n",
                 encoding="utf-8")
    return f


def test_pointer_matches_path_not_basename(tmp_path) -> None:
    ws = _ws(tmp_path)
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


def test_unreadable_ticket_is_skipped_loudly(tmp_path) -> None:
    """读不出要**跨平台必然**读不出（t-286）。

    旧夹具 `chmod(0o000)` 在 root（Docker/CI 常态）与 Windows 上根本不挡读——
    前提静默消失，断言随环境红/绿。换成同名的**目录**占住 `*.md` 路径：
    `read_text` 必抛 OSError，也省掉还原 chmod 的 finally。
    """
    ws = _ws(tmp_path)
    good = _ticket(ws / "docs" / "tasks", "2026-09-01-M9-feat-a.md")
    bad = ws / "docs" / "tasks" / "2026-09-01-M9-feat-b.md"
    bad.mkdir()
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        rows = list_tasks(ws)
    assert [r.path.name for r in rows] == [good.name]
    # ocr2-795：只断 "WARN" 时扫描中任何无关 stderr 噪声都满足——必须点名
    # 坏票路径，红时把捕获文本打出来才可诊。
    err_text = err.getvalue()
    assert "WARN" in err_text, err_text
    assert "feat-b" in err_text, err_text


def test_empty_frontmatter_block_does_not_fall_back_to_body(tmp_path) -> None:
    """`---` 空块 ≠ 没有块：正文一行 `- **Status**: done` 不得冒充元数据（ocr-331）。"""

    ws = _ws(tmp_path)
    d = ws / "docs" / "tasks"
    (d / "2026-09-01-M9-feat-a.md").write_text("---\n---\n\n# A\n\n- **Status**: done\n",
                                               encoding="utf-8")
    rows = list_tasks(ws)
    assert [r.status for r in rows] == ["unknown"], rows


def test_bom_prefixed_frontmatter_wins_over_body(tmp_path) -> None:
    """带 BOM 的票：frontmatter 仍须是唯一源（ocr2-321）。"""
    ws = _ws(tmp_path)
    p = ws / "docs" / "tasks" / "2026-09-01-M9-feat-a.md"
    p.write_bytes(b"\xef\xbb\xbf---\nstatus: idea\nmilestone: M9\n---\n\n# A\n- **Status**: done\n")
    rows = list_tasks(ws)
    assert [r.status for r in rows] == ["idea"], rows


def test_unclosed_frontmatter_does_not_fall_back_to_body(tmp_path) -> None:
    """首行 `---` 但块未闭合 ⇒ 元数据损坏，正文正则不得顶替（ocr2-321）。"""
    ws = _ws(tmp_path)
    p = ws / "docs" / "tasks" / "2026-09-01-M9-feat-b.md"
    p.write_text("---\nstatus: idea\n\n# B\n- **Status**: done\n", encoding="utf-8")
    rows = list_tasks(ws)
    assert [r.status for r in rows] == ["unknown"], rows
