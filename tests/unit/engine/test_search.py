import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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


class TestIndexUnavailableAndFallback(unittest.TestCase):
    """坏索引 ≠ 查无此符号；兜底路径的语义/预算/坐标（ocr-317..321）。"""

    def _ws(self, root: Path) -> None:
        pkg = root / "src" / "demo"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "m.py").write_text("def alpha():\n    return 1\n", encoding="utf-8")

    def test_corrupt_index_raises_instead_of_no_symbol(self) -> None:
        from k3dge.engine.search import (
            IndexUnavailable, _is_stale_cheaply, index_meta_path, index_path,
            write_symbol_index,
        )

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._ws(root)
            idx = write_symbol_index(root)
            self.assertFalse(_is_stale_cheaply(root, idx))
            self.assertTrue(index_meta_path(root).is_file())
            idx.write_text("{ not json", encoding="utf-8")     # 签名仍与树一致 ⇒ 不触发重建
            with self.assertRaises(IndexUnavailable):
                where(root, "alpha")

    def test_fallback_does_not_follow_symlinks(self) -> None:
        import os

        from k3dge.engine.search import _python_search

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            outside = Path(d).parent / "secret_outside.txt"
            outside.write_text("TOPSECRET needle\n", encoding="utf-8")
            os.symlink(str(outside), str(root / "link.txt"))
            self.assertEqual(_python_search(root, "needle"), [])
            outside.unlink()

    def test_ripgrep_invocation_skips_git(self) -> None:
        from k3dge.engine import search as search_mod

        seen = {}

        class R:
            returncode, stdout = 0, ""

        def fake(cmd, **kw):
            seen["cmd"] = cmd
            return R()

        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(search_mod.subprocess, "run", fake):
                search_mod._run_ripgrep(Path(d), "needle")
        self.assertIn("!.git/**", seen["cmd"], "rg 带 --hidden 会命中 .git，与兜底口径不一致")

    def test_fallback_respects_scan_budget(self) -> None:
        import contextlib

        from k3dge.engine import search as search_mod

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for i in range(50):
                (root / f"f{i}.py").write_text("needle\n", encoding="utf-8")
            err = io.StringIO()
            with mock.patch.object(search_mod, "_FALLBACK_BUDGET_SEC", -5.0), \
                    contextlib.redirect_stderr(err):
                got = search_mod._python_search(root, "needle")
            self.assertEqual(got, [])
            self.assertIn("不完整", err.getvalue())

    def test_colon_in_filename_keeps_full_path_and_line(self) -> None:
        from k3dge.engine.search import _split_hit_line

        self.assertEqual(_split_hit_line("a:b/c.py:12:code"), ("a:b/c.py", 12))
        self.assertEqual(_split_hit_line("plain.py:3:"), ("plain.py", 3))
        self.assertEqual(_split_hit_line("no hit line")[1], None)


if __name__ == "__main__":
    unittest.main()
