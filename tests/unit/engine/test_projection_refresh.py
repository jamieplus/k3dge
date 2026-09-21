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
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = _make_repo(Path(self._tmp.name))

    def tearDown(self) -> None:
        self._tmp.cleanup()

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
        _refresh_projections(self.repo)
        self.assertEqual(_refresh_projections(self.repo), [])

    def test_readme_layout_block_is_refreshed(self) -> None:
        self.assertIn("README.md", " ".join(_refresh_projections(self.repo)))
        self.assertIn("| core |", (self.repo / "README.md").read_text(encoding="utf-8"))

    def test_symbol_index_is_written(self) -> None:
        _refresh_projections(self.repo)
        self.assertTrue(search.index_path(self.repo).is_file())


class TestWhereSelfHeals(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = _make_repo(Path(self._tmp.name))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_stale_index_is_rebuilt_on_where(self) -> None:
        search.write_symbol_index(self.repo)
        idx = search.index_path(self.repo)
        data = json.loads(idx.read_text(encoding="utf-8"))
        data.pop("foo", None)
        idx.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (self.repo / "src" / "core" / "mod.py").write_text(
            "def foo() -> int:\n    return 2\n", encoding="utf-8"
        )
        # 显式把索引 mtime 拨到过去：不依赖文件系统的秒级粒度（CI 上防 flake）
        os.utime(idx, (time.time() - 60, time.time() - 60))
        self.assertTrue(search.where(self.repo, "foo"))

    def test_missing_index_is_built(self) -> None:
        self.assertTrue(search.where(self.repo, "foo"))


if __name__ == "__main__":
    unittest.main()
