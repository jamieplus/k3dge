import tempfile
import unittest
from pathlib import Path

from k3dge.engine.search import Location, build_symbol_index, search, where


class TestSearch(unittest.TestCase):
    def _ws(self, root: Path) -> None:
        pkg = root / "src" / "demo"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "module.py").write_text(
            "def top_level():\n    return 1\n\nclass Widget:\n    pass\n", encoding="utf-8"
        )

    def test_where_returns_file_line(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._ws(root)
            locs = where(root, "top_level")
            self.assertTrue(any(isinstance(l, Location) and l.line is not None for l in locs))
            self.assertTrue(all("module.py" in l.file for l in locs))

    def test_search_returns_snippet(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._ws(root)
            locs = search(root, "def top_level")
            self.assertTrue(locs)
            self.assertTrue(any(l.snippet for l in locs))

    def test_search_no_snippet_coords_only(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._ws(root)
            locs = search(root, "def top_level", snippet=False)
            self.assertTrue(all(l.snippet is None for l in locs))

    def test_build_index_shape(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._ws(root)
            idx = build_symbol_index(root)
            self.assertIn("top_level", idx)
            self.assertEqual(idx["top_level"][0]["line"], 1)


if __name__ == "__main__":
    unittest.main()


def test_python_search_honors_gitignore():
    """code-7 残留：兜底对齐 rg——跳过 .gitignore 命中项。"""
    import subprocess

    from k3dge.engine.search import _python_search

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        subprocess.run(["git", "init", "-qb", "main", str(root)], check=True, capture_output=True)
        (root / ".gitignore").write_text("ignored/\n", encoding="utf-8")
        (root / "ignored").mkdir()
        (root / "ignored" / "a.py").write_text("SECRET_TOKEN = 1\n", encoding="utf-8")
        (root / "keep.py").write_text("SECRET_TOKEN = 2\n", encoding="utf-8")
        hits = _python_search(root, "SECRET_TOKEN")
        files = {h.split(":", 1)[0] for h in hits}
        assert "keep.py" in files
        assert not any(f.startswith("ignored/") for f in files)


class TestStalenessSignature(unittest.TestCase):
    """删除/重命名必须让 `where` 重建；一次进程只扫一遍树（ocr-315/316）。"""

    def _ws(self, root: Path) -> None:
        pkg = root / "src" / "demo"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "gone.py").write_text("def ghost():\n    return 1\n", encoding="utf-8")

    def test_deleted_source_is_not_stale_cheaply_invisible(self) -> None:
        from k3dge.engine.search import _is_stale_cheaply, index_path, write_symbol_index

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._ws(root)
            idx = write_symbol_index(root)
            self.assertIn("ghost", build_symbol_index(root))
            self.assertFalse(_is_stale_cheaply(root, idx))
            (root / "src" / "demo" / "gone.py").unlink()
            self.assertTrue(_is_stale_cheaply(root, idx), "删掉源文件后仍判'不陈旧'⇒ where 给幽灵坐标")
            self.assertNotIn("ghost", build_symbol_index(root))
            self.assertIn(str(index_path(root)), str(idx))

    def test_editing_source_still_detected(self) -> None:
        from k3dge.engine.search import _is_stale_cheaply, write_symbol_index
        import time

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._ws(root)
            idx = write_symbol_index(root)
            self.assertFalse(_is_stale_cheaply(root, idx))
            time.sleep(0.02)
            (root / "src" / "demo" / "gone.py").write_text(
                "def ghost():\n    return 2\n", encoding="utf-8")
            self.assertTrue(_is_stale_cheaply(root, idx))

    def test_missing_meta_sidecar_forces_one_rebuild(self) -> None:
        from k3dge.engine.search import (
            _is_stale_cheaply, index_meta_path, write_symbol_index,
        )

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._ws(root)
            idx = write_symbol_index(root)
            self.assertTrue(index_meta_path(root).is_file())
            index_meta_path(root).unlink()
            self.assertTrue(_is_stale_cheaply(root, idx), "无签名 ⇒ 不猜'应该不陈旧'")
