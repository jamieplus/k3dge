"""任务 DAG 透镜：blocking 环 + CPM 关键路径。"""

import argparse
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from k3dge.engine import task_dag


def _task(ws: Path, stem: str, blocking: str = "") -> None:
    d = ws / "docs" / "tasks"
    d.mkdir(parents=True, exist_ok=True)
    body = f"---\nstatus: idea\nmilestone: M9\nblocking: {blocking}\n---\n\n# {stem}\n"
    (d / f"{stem}.md").write_text(body, encoding="utf-8")


def test_critical_path_follows_blocking_chain(tmp_path: Path) -> None:
    _task(tmp_path, "a", "b")
    _task(tmp_path, "b", "c")
    _task(tmp_path, "c")
    assert task_dag.blocking_cycles(tmp_path)["cyclic"] is False
    cp = task_dag.critical_path(tmp_path)
    assert cp["path"] == ["a", "b", "c"] and cp["length"] == 3


def test_blocking_cycle_detected(tmp_path: Path) -> None:
    _task(tmp_path, "a", "b")
    _task(tmp_path, "b", "a")
    assert task_dag.blocking_cycles(tmp_path)["cyclic"] is True
    assert task_dag.critical_path(tmp_path)["path"] == []


def test_unknown_blocking_ignored(tmp_path: Path) -> None:
    _task(tmp_path, "a", "does-not-exist")
    assert task_dag.blocking_graph(tmp_path)["a"] == []


def test_summary_scans_graph_once() -> None:
    """summary 从**同一份图**派生环与关键路径（ocr2-320）：只读一次盘。"""
    g = {"a": ["b"], "b": []}
    calls = []

    def _fake(_ws):
        calls.append(1)
        return g

    with mock.patch.object(task_dag, "blocking_graph", _fake):
        s = task_dag.summary(Path("/nonexistent"))
    assert len(calls) == 1, calls
    assert s["critical_path"] == ["a", "b"]
    assert s["blocking_cycles"] == {"cyclic": False}


class TestBlockingDangling(unittest.TestCase):
    """`blocking:` 指向已关/不存在的票 ⇒ **报事实**（票一关，边被静默丢弃）。

    实测来源：三张票的 blocking 漂了（两张指向已关票、一处写成 `-`），全靠人工扫才发现；
    而 task_dag 的观测当时**没进人类可读输出**（只在 JSON 里）⇒ 无人看见。
    """

    def _ws(self, d):
        p = Path(d) / "docs" / "tasks"
        p.mkdir(parents=True)
        return p

    def test_dangling_classified(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._ws(d)
            (p / "2026-09-01-a.md").write_text(
                "---\nstatus: idea\nblocking: 2026-09-01-b 2026-09-01-c 2026-09-01-d\n---\n# a\n",
                encoding="utf-8")
            (p / "2026-09-01-b.md").write_text("---\nstatus: idea\n---\n# b\n", encoding="utf-8")
            (p / "2026-09-01-c.done.md").write_text("---\nstatus: done\n---\n# c\n", encoding="utf-8")
            out = task_dag.blocking_dangling(Path(d))
            self.assertEqual(out["closed"], ["2026-09-01-a → 2026-09-01-c"])   # 已关票
            self.assertEqual(out["unknown"], ["2026-09-01-a → 2026-09-01-d"])  # 不存在
            # 指向**开票**的不报（正常依赖）
            self.assertNotIn("2026-09-01-b", " ".join(out["closed"] + out["unknown"]))

    def test_clean_repo_has_no_dangling(self):
        """全仓扫描的先提条件**显式断**（t-279）：`parents[3]` 一漂移或装的包没带 docs/ 时，
        `blocking_dangling` 在 `not d.is_dir()` 上回空 dict——"零悬空"绿得什么都没查。
        另：这条测把单测绑到票**内容**上（任一真票漂了 blocking 就红）——它是有意的
        仓库卫生对账，红时先 `k3dge status` 看是哪张票，别改本测。"""
        repo = Path(__file__).resolve().parents[3]
        tasks = repo / "docs" / "tasks"
        self.assertTrue(tasks.is_dir(), f"根不指本仓（parents[3] 漂了？）：{repo}")
        n = len([p for p in tasks.glob("**/*.md")
                 if p.name not in ("README.md", "AUTHORING.md", ".schema.json")])
        self.assertGreater(n, 10, f"docs/tasks 只有 {n} 份可查——本测在空转")
        out = task_dag.blocking_dangling(repo)
        self.assertEqual(out, {"closed": [], "unknown": []})

    def test_archived_closed_ticket_lands_in_closed(self) -> None:
        """bug 465 的形状（t-280）：已关票的常态位置是 `archive/M*/X.done.md`，不是顶层。
        摘掉归档 glob ⇒ 引用被报成"不存在的票"而非"已关票"——旧测全用顶层件，从没防它。"""
        with tempfile.TemporaryDirectory() as d:
            p = self._ws(d)
            arch = p / "archive" / "M8"
            arch.mkdir(parents=True)
            (arch / "2026-09-01-c.done.md").write_text("---\nstatus: done\n---\n# c\n",
                                                       encoding="utf-8")
            (p / "2026-09-01-a.md").write_text("---\nstatus: idea\nblocking: 2026-09-01-c\n---\n# a\n",
                                               encoding="utf-8")
            out = task_dag.blocking_dangling(Path(d))
            self.assertEqual(out["closed"], ["2026-09-01-a → 2026-09-01-c"], out)
            self.assertEqual(out["unknown"], [], out)

    def test_summary_carries_the_observation(self):
        """类 docstring 的回归点是"观测进了**人类可读**输出"（只在 JSON 里＝没人看见）。

        `summary()` 本身就是那块 JSON ⇒ `assertIn(key)` 在修复前后同真，什么都没钉。
        这里分两层：①payload 与输入**相等**（键存在＋值对得上）；②真跑 `cmd_status`
        抓 stdout——把 `main.py:1134-1145` 的 print 块删掉，本测必须红（t-278）。
        """
        with tempfile.TemporaryDirectory() as d:
            p = self._ws(d)
            (p / "2026-09-01-a.md").write_text("---\nstatus: idea\nblocking: ghost\n---\n# a\n",
                                              encoding="utf-8")
            s = task_dag.summary(Path(d))
            self.assertEqual(s.get("blocking_dangling"),
                             {"closed": [], "unknown": ["2026-09-01-a → ghost"]}, s)

            ws = Path(d)
            (ws / ".agent").mkdir(exist_ok=True)
            (ws / ".agent" / "manifest.json").write_text('{"package_root":"src","domains":{}}',
                                                         encoding="utf-8")
            from k3dge.cli import main as cli_main

            buf = io.StringIO()
            with mock.patch.object(cli_main, "_find_workspace", lambda *a, **k: ws), \
                    contextlib.redirect_stdout(buf):
                rc = cli_main.cmd_status(argparse.Namespace(json=False, deep=False))
            out_txt = buf.getvalue()
            self.assertEqual(rc, 0, out_txt)
            self.assertIn("指向不存在的票", out_txt)
            self.assertIn("2026-09-01-a → ghost", out_txt)
