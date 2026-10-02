import io
import os
import shutil
import types
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
            # 空结果的 `all(...)` 恒真（t-266）：先证明"确实命中了带行号的坐标"，
            # 再断 snippet 被关——否则 rg 有无/命中集漂移这类全量丢单照样绿。
            self.assertTrue(locs, "零命中让 all() 变成 vacuous")
            self.assertTrue(all(l.snippet is None for l in locs))
            self.assertTrue(all(l.line is not None for l in locs), locs)
            self.assertTrue(any("module.py" in l.file for l in locs), locs)

    def test_build_index_shape(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._ws(root)
            idx = build_symbol_index(root)
            self.assertIn("top_level", idx)
            self.assertEqual(idx["top_level"][0]["line"], 1)




@unittest.skipUnless(shutil.which("git"), "gitignore 对齐判据需要 git（缺则跳过，非红）")
def test_python_search_honors_gitignore():
    """code-7 残留：兜底对齐 rg——跳过 .gitignore 命中项。

    `init -b main` 要求 git ≥2.28 且与 `_gitignored_prefixes` 无关（仓存在即可）⇒ 去掉（t-267）；
    缺 git 由装饰器**显式 skip**，不再让最小 CI 镜像报一面无产品回归的红。
    """
    import subprocess

    from k3dge.engine.search import _python_search

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        r = subprocess.run(["git", "init", "-q"], cwd=str(root), capture_output=True, text=True)
        assert r.returncode == 0, f"git init 失败：{r.stderr.strip()}"
        (root / ".gitignore").write_text("ignored/\n", encoding="utf-8")
        (root / "ignored").mkdir()
        (root / "ignored" / "a.py").write_text("SECRET_TOKEN = 1\n", encoding="utf-8")
        (root / "keep.py").write_text("SECRET_TOKEN = 2\n", encoding="utf-8")
        hits = _python_search(root, "SECRET_TOKEN")
        files = {h.split(":", 1)[0] for h in hits}
        assert "keep.py" in files               # 正对照：搜索真的产出了命中
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

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._ws(root)
            idx = write_symbol_index(root)
            self.assertFalse(_is_stale_cheaply(root, idx))
            target = root / "src" / "demo" / "gone.py"
            target.write_text("def ghost():\n    return 2\n", encoding="utf-8")
            # 判据是 `newest_mtime > 索引 mtime`，靠 sleep 顶不过文件系统 mtime 粒度
            # （FAT/exFAT 2s、部分 tmpfs/NFS 1s）⇒ 显式把 mtime 拨到未来，确定性化（t-268）
            future = idx.stat().st_mtime + 10.0
            os.utime(target, (future, future))
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
        """符号链接被忽略 + **正对照**（t-269）。

        旧形状三病：①`outside.unlink()` 只在绿时跑（红一次就在系统临时根留垃圾）；
        ②外置文件写到 `Path(d).parent`（受管临时区**之外**、固定名）——并行/复跑相撞；
        ③纯负断言：`_python_search` 对任何输入回 `[]`（早退守卫、过滤误伤）同样"通过"，
        分不清"链接被正确忽略"与"搜索根本没干活"。改：外部文件放进同一受管临时目录、
        正对照必须命中、Windows 无特权建链接时 skip 而不是 error。
        """
        if os.name == "nt":
            self.skipTest("Windows 建符号链接需要特权/开发者模式")
        from k3dge.engine.search import _python_search

        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            root = base / "ws"
            root.mkdir()
            outside = base / "secret_outside.txt"      # 受管内、workspace 外——红也不漏
            outside.write_text("TOPSECRET needle\n", encoding="utf-8")
            (root / "keep.py").write_text("needle here\n", encoding="utf-8")
            os.symlink(str(outside), str(root / "link.py"))
            hits = _python_search(root, "needle")
            files = [h.split(":", 1)[0] for h in hits]
            self.assertIn("keep.py", files, "正对照失手——搜索空转，'忽略链接'是 vacuous")
            self.assertNotIn("link.py", files)
            self.assertFalse(any("secret_outside" in h for h in hits), hits)

    def test_ripgrep_invocation_skips_git(self) -> None:
        """桩换在**模块局部引用**上（t-270）：`search_mod.subprocess` 就是全局 subprocess
        模块对象，patch 它的 `run`＝整进程替换——并行组件/线程撞上就吃到假 subprocess；
        而且哪天生产代码不再 `import subprocess` 而是 `from subprocess import run`，
        这个 patch 会静默 no-op（rg 真被跑起来都看不见）。换成往 search 命名空间里
        塞一个只含 `run` 的替身模块，作用域精确。"""
        from k3dge.engine import search as search_mod

        seen = {}

        class R:
            returncode, stdout = 0, ""

        def fake_run(cmd, **kw):
            seen["cmd"] = cmd
            return R()

        stub = types.SimpleNamespace(run=fake_run)
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(search_mod, "subprocess", stub, create=False):
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
