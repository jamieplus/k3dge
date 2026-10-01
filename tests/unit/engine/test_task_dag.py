"""任务 DAG 透镜：blocking 环 + CPM 关键路径。"""

import tempfile
import unittest
from pathlib import Path

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
        repo = Path(__file__).resolve().parents[3]
        out = task_dag.blocking_dangling(repo)
        self.assertEqual(out, {"closed": [], "unknown": []})

    def test_summary_carries_the_observation(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._ws(d)
            (p / "2026-09-01-a.md").write_text("---\nstatus: idea\nblocking: ghost\n---\n# a\n",
                                              encoding="utf-8")
            self.assertIn("blocking_dangling", task_dag.summary(Path(d)))
