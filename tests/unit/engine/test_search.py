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
