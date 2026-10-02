import tempfile
import unittest
from pathlib import Path

from k3dge.engine import contract

SRC = '''"""Module docstring."""
from __future__ import annotations

def foo(x: int, y: str = "a") -> bool:
    return True

async def bar() -> None:
    pass

class Widget:
    def run(self, n: int) -> int:
        return n

    def _helper(self) -> None:
        pass
'''


class TestContract(unittest.TestCase):
    def test_extract_interface(self):
        iface = contract.extract_python_interface(SRC)
        self.assertIn("foo(x: int, y: str='a') -> bool", iface)
        # ocr2-448：`"bar() -> None"` 是 `"async bar() -> None"` 的子串——若 `async` 前缀被丢，
        # 旧断言照绿（ocr-059 的回归恰好就此隐形）。钉整行。
        self.assertIn("async bar() -> None", iface)
        self.assertIn("class Widget", iface)
        self.assertIn("    run(self, n: int) -> int", iface)
        self.assertNotIn("_helper", iface)

    def test_compute_hash_deterministic(self):
        self.assertEqual(contract.compute_hash(SRC), contract.compute_hash(SRC))
        self.assertNotEqual(
            contract.compute_hash(SRC), contract.compute_hash("def other() -> None: pass")
        )

    def test_normalize_collapses_whitespace(self):
        self.assertEqual(
            contract.normalize("  def foo(x: int)  "),
            contract.normalize("def foo(x: int)"),
        )

    def test_verify_contract_matches(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d)
            (src / "mod.py").write_text("def foo(x: int) -> str:\n    return ''\n", encoding="utf-8")
            iface = contract.collect_domain_interface(src)
            h = contract.compute_hash(iface)
            spec = f"**Contract Hash**: `sha256:{h}`"
            ok, expected, actual = contract.verify_contract(src, spec)
            self.assertTrue(ok)
            self.assertEqual(expected, h)
            self.assertEqual(actual, h)

    def test_verify_contract_drift(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d)
            (src / "mod.py").write_text("def foo(x: int) -> str:\n    return ''\n", encoding="utf-8")
            spec = "**Contract Hash**: `sha256:" + "0" * 64 + "`"
            ok, expected, actual = contract.verify_contract(src, spec)
            self.assertFalse(ok)
            self.assertNotEqual(expected, actual)

    def test_symbol_diff_reports_changed_symbols(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src"
            src.mkdir()
            mod = src / "mod.py"
            mod.write_text("def foo(x: int) -> str:\n    return ''\n\ndef bar() -> None:\n    return None\n", encoding="utf-8")
            iface = contract.collect_domain_interface(src)
            h = contract.compute_hash(iface)
            spec = (
                "**Contract Hash**: `sha256:" + h + "`\n"
                + contract.INTERFACE_START + "\n" + iface + "\n" + contract.INTERFACE_END + "\n"
            )
            self.assertEqual(
                contract.symbol_diff(spec, src),
                {"added": [], "removed": [], "changed": []},
            )
            mod.write_text(
                "def foo(x: int, y: int) -> str:\n    return ''\n\n"
                "def baz() -> int:\n    return 1\n"
            , encoding="utf-8")
            diff = contract.symbol_diff(spec, src)
            self.assertIn("foo", diff["changed"])
            self.assertIn("bar", diff["removed"])
            self.assertIn("baz", diff["added"])

    def test_cached_property_changes_hash(self):
        prop = "class W:\n    @property\n    def x(self) -> int:\n        return 1\n"
        cached = (
            "from functools import cached_property\n"
            "class W:\n    @cached_property\n    def x(self) -> int:\n        return 1\n"
        )
        # ocr2-449：`cached` 比 `prop` 多一行 `from functools import cached_property`，
        # 所以即便两个装饰器都从 `_SIGNIFICANT_DECORATORS` 删掉，接口仍不同 ⇒ 旧 `assertNotEqual`
        # 恒绿。先直接断言装饰器真的进了接口，再比哈希。
        prop_iface = contract.extract_python_interface(prop)
        cached_iface = contract.extract_python_interface(cached)
        self.assertIn("@property", prop_iface)
        self.assertIn("@cached_property", cached_iface)
        self.assertNotEqual(
            contract.compute_hash(prop_iface),
            contract.compute_hash(cached_iface),
        )

    def test_syntax_error_is_visible(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d)
            (src / "ok.py").write_text("def foo() -> int:\n    return 1\n", encoding="utf-8")
            h1 = contract.compute_hash(contract.collect_domain_interface(src))
            (src / "broken.py").write_text("def bar( ->\n", encoding="utf-8")
            from k3dge.engine.contract import _ExtractError

            with self.assertRaises(_ExtractError) as cm:
                contract.collect_domain_interface(src)
            # 断**消息点名坏文件**（t-098）：`assertTrue(h1)` 恒真（compute_hash 永远回
            # 64-hex），对"语法错可见"这条要求零覆盖——真判据是错误里要说得出是谁坏了。
            self.assertIn("broken.py", str(cm.exception), str(cm.exception))
            # 坏文件出现前的成功提取 h1 必须是合法 64-hex（"非空"太弱）
            self.assertRegex(h1, r"^[0-9a-f]{64}$")

    def test_ts_function_body_not_in_signature(self):
        import importlib.util
        import sys
        try:
            import tree_sitter  # noqa: F401
            import tree_sitter_typescript  # noqa: F401
        except ImportError:
            self.skipTest("tree-sitter-typescript not installed")
        from k3dge.engine.contract import _EXTRACTORS
        from k3dge.engine import extractor_gen
        before = list(_EXTRACTORS)
        # 曾经这里去读一个**不存在的**资产 `templates/assets/extractors/ts.py`（TS 插件现在由
        # `extractor_gen` 生成，资产树里没有该文件）⇒ 断言必红或在 `python -O` 下换成另一种崩，
        # 且入口名 `extract_ts_interface` 也是旧的（真名 `extract_typescript_interface`，t-095）。
        # 现在**当场生成插件**再加载：确定、不依赖资产，也不靠 `parents[3]` 猜仓根。
        mod_name = "k3dge_plugin_ts_generated_test"
        with tempfile.TemporaryDirectory() as d:
            asset = Path(d) / "typescript.py"
            asset.write_text(extractor_gen.render_plugin(
                "typescript", extractor_gen.DEFAULT_LANGS["typescript"]), encoding="utf-8")
            spec_obj = importlib.util.spec_from_file_location(mod_name, asset)
            assert spec_obj is not None and spec_obj.loader is not None
            mod = importlib.util.module_from_spec(spec_obj)
            sys.modules[mod_name] = mod
            try:
                spec_obj.loader.exec_module(mod)
                path = Path(d) / "mod.ts"
                path.write_text("export function foo(x: number): number {\n  return x + 1;\n}\nconst skipped = 1;\n", encoding="utf-8")
                iface = mod.extract_typescript_interface(path) or ""
                self.assertIn("foo", iface)
                self.assertNotIn("return x", iface)
                self.assertNotIn("skipped", iface)
            finally:
                _EXTRACTORS[:] = before
                sys.modules.pop(mod_name, None)

    def test_rename_preserves_hash(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d)
            (src / "foo.py").write_text("def foo() -> None:\n    pass\n", encoding="utf-8")
            h1 = contract.compute_hash(contract.collect_domain_interface(src))
            (src / "foo.py").rename(src / "bar.py")
            h2 = contract.compute_hash(contract.collect_domain_interface(src))
            self.assertEqual(h1, h2)

    def test_symlink_outside_domain_not_hashed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / "src"
            src.mkdir()
            (src / "ok.py").write_text("def foo() -> int:\n    return 1\n", encoding="utf-8")
            outside = root / "outside.py"
            outside.write_text("def leaked() -> int:\n    return 1\n", encoding="utf-8")
            try:
                (src / "evil.py").symlink_to(outside)
            except OSError:
                self.skipTest("symlinks not supported")
            ext = root / "ext"
            ext.mkdir()
            (ext / "leaked2.py").write_text("def leaked2() -> None:\n    pass\n", encoding="utf-8")
            try:
                (src / "subdir").symlink_to(ext)
            except OSError:
                self.skipTest("symlinks not supported")
            iface = contract.collect_domain_interface(src)
            self.assertIn("foo", iface)
            self.assertNotIn("leaked", iface)
            self.assertNotIn("leaked2", iface)

    def test_verify_contract_missing_hash(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d)
            (src / "mod.py").write_text("def foo(x: int) -> str:\n    return ''\n", encoding="utf-8")
            ok, expected, actual = contract.verify_contract(src, "no hash here")
            self.assertFalse(ok)
            self.assertIsNone(expected)

    def test_register_extractor(self):
        from k3dge.engine.contract import ContractExtractor, _EXTRACTORS
        before = list(_EXTRACTORS)
        try:
            class DummyExtractor(ContractExtractor):
                def can_handle(self, path):
                    return path.suffix == ".dummy_test"
                def extract(self, path, include_doc=False):
                    return "dummy iface"
            dummy = DummyExtractor()
            contract.register_extractor(dummy)
            self.assertIn(dummy, _EXTRACTORS)
        finally:
            _EXTRACTORS[:] = before

    def test_register_extractor_rejects_non_extractor(self):
        with self.assertRaises(TypeError):
            contract.register_extractor(object())

    def test_register_extractor_override_front(self):
        from k3dge.engine.contract import ContractExtractor, _EXTRACTORS
        before = list(_EXTRACTORS)
        try:
            class FrontExtractor(ContractExtractor):
                def can_handle(self, path):
                    return path.suffix == ".front_test"
                def extract(self, path, include_doc=False):
                    return "front"
            front = FrontExtractor()
            contract.register_extractor(front, override=True)
            self.assertIs(_EXTRACTORS[0], front)
        finally:
            _EXTRACTORS[:] = before

    def test_plugin_extractor_via_manifest(self):
        import sys
        from k3dge.engine.contract import ContractExtractor, _EXTRACTORS
        before = list(_EXTRACTORS)
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "plug_test_mod.py").write_text(
                "from pathlib import Path\n"
                "from k3dge.engine.contract import ContractExtractor, register_extractor\n"
                "class PlugTestExtractor(ContractExtractor):\n"
                "    def can_handle(self, path: Path) -> bool:\n"
                "        return path.suffix == '.plugtest'\n"
                "    def extract(self, path: Path, include_doc: bool = False) -> str:\n"
                "        return 'plugtest iface'\n"
                "register_extractor(PlugTestExtractor())\n",
                encoding="utf-8",
            )
            sys.path.insert(0, d)
            try:
                class FakeManifest:
                    data = {"extractors": ["plug_test_mod"]}
                    def is_ignored(self, rel):
                        return False
                src = Path(d) / "srcx"
                src.mkdir()
                (src / "a.plugtest").write_text("x", encoding="utf-8")
                out = contract.collect_domain_interface(src, manifest=FakeManifest(), workspace_root=Path(d))
                self.assertIn("plugtest iface", out)
            finally:
                sys.path.remove(d)
                sys.modules.pop("plug_test_mod", None)
                _EXTRACTORS[:] = before

    def test_plugin_broken_module_warns_not_crash(self):
        import contextlib
        import io

        from k3dge.engine.contract import _EXTRACTORS
        before = list(_EXTRACTORS)
        try:
            class BadManifest:
                data = {"extractors": ["nonexistent_mod_xyz_abc"]}
                def is_ignored(self, rel):
                    return False
            with tempfile.TemporaryDirectory() as d:
                src = Path(d)
                (src / "a.py").write_text("def foo() -> int:\n    return 1\n", encoding="utf-8")
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    out = contract.collect_domain_interface(src, manifest=BadManifest(), workspace_root=Path(d))
                self.assertIn("foo", out)
                # ocr2-450：名字承诺"坏插件可见"——只断"不崩"的话，整条 manifest-extractor
                # 分支被删/警告被删也照样绿。断言坏 spec 名真的被报到 stderr。
                self.assertIn("nonexistent_mod_xyz_abc", err.getvalue(), err.getvalue())
        finally:
            _EXTRACTORS[:] = before

    def _dropin_sandbox(self):
        """插件面的**真**隔离（t-096/097）。

        旧代码 poke `contract._load_plugin_extractors._attempted`——那函数属性**不存在**
        （缓存早搬到模块级 `_PLUGIN_ATTEMPTED`）⇒ `attempted` 恒 None、clear/restore
        全是死分支；测能过纯靠"每轮 tempdir 路径是新的"，进程级缓存则背着陈旧
        路径无限涨。teardown 也不得按 `k3dge_plugin_` 前缀**全拆**——那会连别处
        （TS 资产测/本仓 `.agent/extractors`）加载的插件一起卸载＝隐式跨测干扰、
        顺序相关。这里只还原"本测新增"的模块与缓存项。返回 (restorer,)。
        """
        import sys
        from k3dge.engine.contract import _EXTRACTORS, _PLUGIN_ATTEMPTED
        before_ext = list(_EXTRACTORS)
        saved_attempted = set(_PLUGIN_ATTEMPTED)
        saved_modules = set(sys.modules)

        def restore() -> None:
            _EXTRACTORS[:] = before_ext
            for mod in set(sys.modules) - saved_modules:
                if mod.startswith("k3dge_plugin_"):
                    sys.modules.pop(mod, None)
            _PLUGIN_ATTEMPTED.difference_update(_PLUGIN_ATTEMPTED - saved_attempted)
        return restore

    def test_convention_dir_dropin_plugin(self):
        import sys
        restore = self._dropin_sandbox()
        try:
            with tempfile.TemporaryDirectory() as d:
                ws = Path(d)
                plugdir = ws / ".agent" / "extractors"
                plugdir.mkdir(parents=True)
                (plugdir / "zz_dropin_test.py").write_text(
                    "from pathlib import Path\n"
                    "from k3dge.engine.contract import ContractExtractor, register_extractor\n"
                    "class DropinExtractor(ContractExtractor):\n"
                    "    def can_handle(self, path: Path) -> bool:\n"
                    "        return path.suffix == '.dropin'\n"
                    "    def extract(self, path: Path, include_doc: bool = False) -> str:\n"
                    "        return 'dropin iface'\n"
                    "register_extractor(DropinExtractor())\n",
                    encoding="utf-8",
                )
                src = ws / "srcx"
                src.mkdir()
                (src / "a.dropin").write_text("x", encoding="utf-8")
                out = contract.collect_domain_interface(src, manifest=None, workspace_root=ws)
                self.assertIn("dropin iface", out)
                self.assertIn("k3dge_plugin_zz_dropin_test", sys.modules)   # 真的加载过
        finally:
            restore()

    def test_convention_dir_broken_file_does_not_block(self):
        import sys
        restore = self._dropin_sandbox()
        try:
            with tempfile.TemporaryDirectory() as d:
                ws = Path(d)
                plugdir = ws / ".agent" / "extractors"
                plugdir.mkdir(parents=True)
                (plugdir / "zz_broken_test.py").write_text("raise RuntimeError('boom')\n", encoding="utf-8")
                (plugdir / "zz_good_test.py").write_text(
                    "from pathlib import Path\n"
                    "from k3dge.engine.contract import ContractExtractor, register_extractor\n"
                    "class GoodExtractor(ContractExtractor):\n"
                    "    def can_handle(self, path: Path) -> bool:\n"
                    "        return path.suffix == '.goodtest'\n"
                    "    def extract(self, path: Path, include_doc: bool = False) -> str:\n"
                    "        return 'good iface'\n"
                    "register_extractor(GoodExtractor())\n",
                    encoding="utf-8",
                )
                (plugdir / "_helper_test.py").write_text("X = 1\n", encoding="utf-8")
                src = ws / "srcx"
                src.mkdir()
                (src / "a.goodtest").write_text("x", encoding="utf-8")
                out = contract.collect_domain_interface(src, manifest=None, workspace_root=ws)
                self.assertIn("good iface", out)
                # ocr2-451：`_helper_test.py` 此前是死布置——删掉 `startswith("_")` 跳过规则
                # 也测不出。直接钉"下划线文件没被加载进 sys.modules"（与正对照对称）。
                self.assertNotIn("k3dge_plugin__helper_test", sys.modules)
        finally:
            restore()

if __name__ == "__main__":
    unittest.main()
