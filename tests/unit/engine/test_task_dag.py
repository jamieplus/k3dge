"""任务 DAG 透镜：blocking 环 + CPM 关键路径。"""

import argparse
import contextlib
import io
import shutil
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


class TestTaskDagCore(unittest.TestCase):
    """ocr2-531：原为模块级 pytest 函数 + 裸 `assert`——`unittest`/直跑不收集、`-O` 剥断言。
    折进 TestCase，用 tempfile 赋 `tmp_path` 的等价作用。"""

    def _ws(self) -> Path:
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        return d

    def test_critical_path_follows_blocking_chain(self) -> None:
        ws = self._ws()
        _task(ws, "a", "b")
        _task(ws, "b", "c")
        _task(ws, "c")
        self.assertIs(task_dag.blocking_cycles(ws)["cyclic"], False)
        cp = task_dag.critical_path(ws)
        self.assertEqual(cp["path"], ["a", "b", "c"])
        self.assertEqual(cp["length"], 3)
        self.assertIs(cp["cyclic"], False)

    def test_blocking_cycle_detected(self) -> None:
        ws = self._ws()
        _task(ws, "a", "b")
        _task(ws, "b", "a")
        cyc = task_dag.blocking_cycles(ws)
        self.assertIs(cyc["cyclic"], True)
        # ocr2-532：钉**环路径**本身（`_cycles_of` 读 `exc.args[-1]`；回退成 args[0]
        # 只重复固定标签、真环丢失），并钉退化 critical_path 的 cyclic 标记。
        self.assertIn("a", cyc.get("detail", ""), cyc)
        self.assertIn("b", cyc.get("detail", ""), cyc)
        self.assertNotIn("Cyclic dependencies exist", cyc.get("detail", ""), cyc)
        cp = task_dag.critical_path(ws)
        self.assertEqual(cp["path"], [])
        self.assertEqual(cp["length"], 0)
        self.assertIs(cp["cyclic"], True)

    def test_unknown_blocking_ignored(self) -> None:
        ws = self._ws()
        _task(ws, "a", "does-not-exist")
        self.assertEqual(task_dag.blocking_graph(ws)["a"], [])

    def test_summary_scans_graph_once(self) -> None:
        """summary 从**同一份图**派生环与关键路径（ocr2-320）：只读一次盘。"""
        g = {"a": ["b"], "b": []}
        calls = []

        def _fake(_ws):
            calls.append(1)
            return g

        with mock.patch.object(task_dag, "blocking_graph", _fake):
            s = task_dag.summary(Path("/nonexistent"))
        self.assertEqual(len(calls), 1, calls)
        self.assertEqual(s["critical_path"], ["a", "b"])
        self.assertEqual(s["blocking_cycles"], {"cyclic": False})


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

    def test_scanner_actually_emits_refs(self):
        """ocr2-533：正对照——证明 `blocking_dangling` 真的会产出引用事实。
        否则本仓"零悬空"可能只是"没有一票声明 blocking"。"""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "docs" / "tasks"
            p.mkdir(parents=True)
            (p / "a.md").write_text(
                "---\nstatus: idea\nblocking: ghost\n---\n# a\n", encoding="utf-8")
            self.assertEqual(task_dag.blocking_dangling(Path(d)),
                             {"closed": [], "unknown": ["a → ghost"]})

    def test_clean_repo_has_no_dangling(self):
        """全仓扫描的先提条件**显式断**（t-279 / ocr2-533）：计数必须与被测函数扫的是
        **同一集合**（顶层非 aux、非 done，走 impl 自己的 `_is_doc_aux` 谓词），
        并钉住能产出引用的机制（`test_scanner_actually_emits_refs`）。"""
        from k3dge.engine.milestone_files import _is_doc_aux

        repo = Path(__file__).resolve().parents[3]
        tasks = repo / "docs" / "tasks"
        self.assertTrue(tasks.is_dir(), f"根不指本仓（parents[3] 漂了？）：{repo}")
        scanned = [p for p in tasks.glob("*.md")
                   if not _is_doc_aux(p.name) and not p.name.endswith(".done.md")]
        n = len(scanned)
        self.assertGreater(n, 0, "docs/tasks 没有可查的开票——本测在空转")
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


if __name__ == "__main__":
    unittest.main()
