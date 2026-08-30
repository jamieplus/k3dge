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
