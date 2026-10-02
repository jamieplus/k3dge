"""封版相位 3 的纯投影刷新 + `k3dge where` 的索引自愈（2026-09-21）。"""
import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from k3dge.engine import search
from k3dge.engine.generated_docs import render_manual_docs_content
from k3dge.engine.manifest import Manifest
from k3dge.engine.seal_flow import _refresh_projections


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _make_repo(tmp: Path) -> Path:
    repo = tmp / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "tester")
    (repo / ".agent").mkdir()
    (repo / ".agent" / "manifest.json").write_text(
        json.dumps({"package_root": "src",
                    "domains": {"core": {"src": "src/core", "spec": "docs/specs/core/spec.md"}},
                    "ignore": []}),
        encoding="utf-8",
    )
    (repo / "src" / "core").mkdir(parents=True)
    (repo / "src" / "core" / "mod.py").write_text("def foo() -> int:\n    return 1\n", encoding="utf-8")
    (repo / "README.md").write_text(
        "# R\n\n<!-- k3dge:layout-start -->\n<!-- k3dge:layout-end -->\n", encoding="utf-8"
    )
    return repo


class TestProjectionRefresh(unittest.TestCase):
    def setUp(self) -> None:
        # 清理**先登记再建仓**（t-235）：`setUp` 抛错时 unittest 不跑 tearDown，旧写法
        # 只剩解释器退出时的 finalizer 兜底；`self.repo` 也会悬空。
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = _make_repo(Path(self._tmp.name))

    def _fresh_contents(self) -> dict:
        return render_manual_docs_content(self.repo, Manifest.load(self.repo))

    def test_stale_generated_doc_is_refreshed_and_reported(self) -> None:
        gen = self.repo / "docs" / "generated"
        gen.mkdir(parents=True)
        (gen / "api.md").write_text("# API Reference\n\n陈旧\n", encoding="utf-8")
        changed = _refresh_projections(self.repo)
        self.assertIn("docs/generated/api.md", changed)
        expected = self._fresh_contents()[gen / "api.md"]
        self.assertEqual((gen / "api.md").read_text(encoding="utf-8"), expected)

    def test_refresh_is_idempotent(self) -> None:
        """第二次为空**只有第一次真写了**才有意义（t-233）。

        `_refresh_projections` 把每件失败都内部吞成"无变化"——两连空返回时旧测全绿，
        "幂等"与"全坏了"不可分辨。把 `failures` 传出来断言为空，并钉首轮确有产出。
        """
        f1: list = []
        first = _refresh_projections(self.repo, f1)
        self.assertEqual(f1, [], f"投影失败被吞：{f1}")
        self.assertTrue(first, "首轮什么都没刷新＝'已新鲜'的前提没建立，二轮的'空'是假绿")
        f2: list = []
        second = _refresh_projections(self.repo, f2)
        self.assertEqual(second, [], f2)
        self.assertEqual(f2, [], "第二轮把失败吞进了返回值之外")

    def test_readme_layout_block_is_refreshed(self) -> None:
        # **列表成员**精确断（t-234）：`" ".join` 后子串匹配会被任何含 README.md 的路径
        # （docs/generated/README.md…）满足——根 README 没刷也绿。
        self.assertIn("README.md", _refresh_projections(self.repo))
        self.assertIn("| core |", (self.repo / "README.md").read_text(encoding="utf-8"))

    def test_symbol_index_is_written(self) -> None:
        """ocr2-508：不只"文件在"——把**载荷**钉住。`write_symbol_index` 在 `_make_repo`
        没找到任何源时会愉快地持久化空 `{}`，仅断 is_file() 恰好在投影空转时绿。"""
        _refresh_projections(self.repo)
        idx = search.index_path(self.repo)
        self.assertTrue(idx.is_file())
        data = json.loads(idx.read_text(encoding="utf-8"))
        self.assertIn("foo", data, f"索引存在但没编入 src/core/mod.py 的 foo：{sorted(data)[:8]}")

    def test_one_unreadable_projection_does_not_abort_the_rest(self) -> None:
        """某件读前失败只跳过它，其余投影照刷（ocr2-312）。"""
        from unittest import mock

        gen = self.repo / "docs" / "generated"
        gen.mkdir(parents=True)
        target = gen / "api.md"
        target.write_text("old\n", encoding="utf-8")
        real_read_bytes = Path.read_bytes

        def _fake_read_bytes(self):
            if self == target:
                raise OSError("EIO")
            return real_read_bytes(self)

        f: list = []
        with mock.patch.object(Path, "read_bytes", _fake_read_bytes):
            _refresh_projections(self.repo, f)      # 不抛
        self.assertTrue(any("api.md" in x for x in f), f)
        self.assertTrue(search.index_path(self.repo).is_file())   # 其余件仍完成


class TestWhereSelfHeals(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)          # 同 t-235：setUp 抛错也回收
        self.repo = _make_repo(Path(self._tmp.name))

    def test_stale_index_is_rebuilt_on_where(self) -> None:
        search.write_symbol_index(self.repo)
        idx = search.index_path(self.repo)
        data = json.loads(idx.read_text(encoding="utf-8"))
        # 先证"foo 键本来在"（t-236）：顶层键约定若变，pop 带 default 会静默 no-op——
        # "被破坏的索引"其实没被破坏，本测就白跑。
        self.assertIn("foo", data, f"索引顶层形状变了？keys={sorted(data)[:8]}")
        data.pop("foo")
        idx.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (self.repo / "src" / "core" / "mod.py").write_text(
            "def foo() -> int:\n    return 2\n", encoding="utf-8"
        )
        # 显式把索引 mtime 拨到过去：不依赖文件系统的秒级粒度（CI 上防 flake）
        os.utime(idx, (time.time() - 60, time.time() - 60))
        locs = search.where(self.repo, "foo")
        # "非空"太宽（t-236）：钉**重建后坐标对**——文件与行号来自现树，不是残留载荷。
        self.assertTrue(locs, "自愈没把删掉的 `foo` 建回来")
        self.assertEqual({l.file for l in locs}, {"src/core/mod.py"}, locs)
        self.assertEqual([l.line for l in locs], [1], locs)

    def test_missing_index_is_built(self) -> None:
        """ocr2-509：钉**持久化产物**与前置（缺失），而不是 `where()` 的非空返回。
        内存扫/兜底路径也能让 `where()` 返回坐标，而索引文件根本没建。"""
        idx = search.index_path(self.repo)
        self.assertFalse(idx.exists(), "前置：索引本不存在，否则测不到'建'")
        locs = search.where(self.repo, "foo")
        self.assertTrue(locs)
        self.assertTrue(idx.is_file(), "where() 解析了符号却没把索引落盘")
        data = json.loads(idx.read_text(encoding="utf-8"))
        self.assertIn("foo", data, f"落盘的索引是空的/缺 foo：{sorted(data)[:8]}")


if __name__ == "__main__":
    unittest.main()
