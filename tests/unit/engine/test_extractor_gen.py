"""extractor_gen: render determinism, sync idempotency, prune safety, config errors."""
import tempfile
import unittest
from pathlib import Path

from k3dge.engine import extractor_gen as g


def _ws(d, toml=None):
    ws = Path(d)
    (ws / ".agent").mkdir(parents=True, exist_ok=True)
    if toml is not None:
        (ws / ".agent" / "extractors.toml").write_text(toml, encoding="utf-8")
    return ws


class TestRender(unittest.TestCase):
    def test_deterministic(self):
        for name in g.DEFAULT_LANGS:
            a = g.render_plugin(name, g.DEFAULT_LANGS[name])
            b = g.render_plugin(name, g.DEFAULT_LANGS[name])
            self.assertEqual(a, b)

    def test_marker_header(self):
        text = g.render_plugin("go", g.DEFAULT_LANGS["go"])
        self.assertTrue(text.startswith(g.MARKER))

    def test_typescript_branches(self):
        """Generated TS keeps the legacy branch structure (export/class/lexical)."""
        src = g.render_plugin("typescript", g.DEFAULT_LANGS["typescript"])
        for needle in ("export_statement", "class_body", "lexical_declaration",
                       "public_field_definition", "language_typescript()"):
            self.assertIn(needle, src)

    def test_no_container_means_no_walker(self):
        src = g.render_plugin("go", g.DEFAULT_LANGS["go"])
        self.assertNotIn("_container_signature", src)
        src_ts = g.render_plugin("typescript", g.DEFAULT_LANGS["typescript"])
        self.assertIn("_container_signature", src_ts)

    def test_language_arity_fallback_narrows_except(self):
        """code-4: `Language(ptr)` vs `Language(ptr, name)` 的差异只该被 `TypeError` 兜住，
        真实故障（ABI/import 错）不得被吞成降级分支（fail-closed 而非 fail-silent）。"""
        src = g.render_plugin("typescript", g.DEFAULT_LANGS["typescript"])
        self.assertIn("except TypeError:", src)
        self.assertNotIn("except Exception:", src)

    def test_skip_is_documented_as_gate_caught(self):
        """code-1/code-11: 缺 grammar 时 `raise ImportError` 是**被门禁吞的 skip 信号**，
        docstring 必须写明调用方 `except ImportError`（消「会红」与「never fatal」的表观矛盾）。"""
        src = g.render_plugin("typescript", g.DEFAULT_LANGS["typescript"])
        self.assertIn("except ImportError", src)
        self.assertIn("never fatal", src)


class TestGeneratedFiltering(unittest.TestCase):
    """code-6/code-9: 生成的插件在**没有 grammar 时也能测**的路径逻辑——加载模块、直接调
    `can_handle` / `_slice`（两者都不触发 tree_sitter import）。"""

    def _load(self):
        import importlib.util
        import sys
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "gen_ts.py"
            p.write_text(g.render_plugin("typescript", g.DEFAULT_LANGS["typescript"]), encoding="utf-8")
            spec = importlib.util.spec_from_file_location("gen_ts_filter_probe", p)
            assert spec is not None and spec.loader is not None
            mod = importlib.util.module_from_spec(spec)
            sys.modules["gen_ts_filter_probe"] = mod
            spec.loader.exec_module(mod)
            return mod

    def tearDown(self):
        import sys
        sys.modules.pop("gen_ts_filter_probe", None)
        from k3dge.engine import contract as c
        c._EXTRACTORS[:] = [e for e in c._EXTRACTORS if type(e).__module__ != "gen_ts_filter_probe"]

    def test_can_handle_skips_deps_and_generated(self):
        mod = self._load()
        ext = mod.TypescriptExtractor()
        self.assertTrue(ext.can_handle(Path("src/app.ts")))
        self.assertFalse(ext.can_handle(Path("node_modules/x/index.ts")), "third-party dep")
        self.assertFalse(ext.can_handle(Path("dist/bundle.js")), "ignored dir")
        self.assertFalse(ext.can_handle(Path("src/types/api.d.ts")), "type-only declaration file")
        self.assertFalse(ext.can_handle(Path("src/gen.proto.generated.ts")), "generated marker")
        self.assertFalse(ext.can_handle(Path("src/vendor/app.min.js")), "minified bundle")

    def test_slice_strips_control_and_cr(self):
        """code-9: 不可信字节/换行控制符不得原样进契约文本（U+FFFD/`\r` 造成 hash 漂移）。"""
        mod = self._load()

        class Node:
            start_byte, end_byte = 0, 0

        raw = b"line1\r\nline2\x00\x07 end"
        n = Node()
        n.start_byte, n.end_byte = 0, len(raw)
        out = mod._slice(raw, n)
        self.assertNotIn("\r", out)
        self.assertNotIn("\x00", out)
        self.assertNotIn("\x07", out)
        self.assertIn("line1", out)
        self.assertIn("line2", out)


class TestResolve(unittest.TestCase):
    def test_no_toml_defaults_typescript(self):
        with tempfile.TemporaryDirectory() as d:
            resolved = g.resolve_languages(_ws(d))
            self.assertEqual(list(resolved), ["typescript"])

    def test_enable_builtin(self):
        with tempfile.TemporaryDirectory() as d:
            ws = _ws(d, 'enable = ["go", "rust"]\n')
            resolved = g.resolve_languages(ws)
            self.assertEqual(sorted(resolved), ["go", "rust"])

    def test_unknown_enable_errors(self):
        with tempfile.TemporaryDirectory() as d:
            ws = _ws(d, 'enable = ["klingon"]\n')
            with self.assertRaises(g.ExtractorConfigError) as ctx:
                g.resolve_languages(ws)
            self.assertIn("klingon", str(ctx.exception))

    def test_invalid_name_rejected(self):
        """语言名进 `plugdir / f"{name}.py"` 当文件名 ⇒ 路径分隔/`..` 必须拒（ocr-007）。"""
        row = ('grammar = "x"\npackage = "x"\nlang_func = "language"\nlang_name = "x"\n'
               'suffixes = [".x"]\nwrapper = []\nwrapper_kw = ""\nfn = []\ncontainer = []\n'
               'body = []\nmember = []\ntype = []\nlexical_nodes = []\n'
               'lexical_markers = []\nlexical = false\n')
        for bad in (f'[languages."../evil"]\n{row}', 'enable = ["a/b"]\n'):
            with tempfile.TemporaryDirectory() as d:
                ws = _ws(d, bad)
                with self.assertRaises(g.ExtractorConfigError):
                    g.resolve_languages(ws)

    def test_custom_row_replaces_builtin(self):
        with tempfile.TemporaryDirectory() as d:
            ws = _ws(d, 'enable = ["go"]\n[languages.go]\n'
                        'grammar = "x"\npackage = "x"\nlang_func = "language"\nlang_name = "go"\n'
                        'suffixes = [".g"]\nwrapper = []\nwrapper_kw = ""\nfn = []\ncontainer = []\n'
                        'body = []\nmember = []\ntype = []\nlexical_nodes = []\nlexical_markers = []\nlexical = false\n')
            resolved = g.resolve_languages(ws)
            self.assertEqual(resolved["go"]["suffixes"], [".g"])

    def test_custom_row_missing_key_errors(self):
        with tempfile.TemporaryDirectory() as d:
            ws = _ws(d, '[languages.mylang]\ngrammar = "x"\n')
            with self.assertRaises(g.ExtractorConfigError):
                g.resolve_languages(ws)


class TestSync(unittest.TestCase):
    def test_sync_writes_and_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            ws = _ws(d, 'enable = ["go"]\n')
            r1 = g.sync_extractors(ws)
            self.assertEqual(r1["written"], ["go"])
            self.assertTrue((ws / ".agent" / "extractors" / "go.py").is_file())
            r2 = g.sync_extractors(ws)
            self.assertEqual(r2["written"], [])
            self.assertEqual(r2["pruned"], [])

    def test_sync_prunes_stale_generated_only(self):
        with tempfile.TemporaryDirectory() as d:
            ws = _ws(d, 'enable = ["go"]\n')
            g.sync_extractors(ws)
            plugdir = ws / ".agent" / "extractors"
            # stale generated file (marker, no longer enabled)
            (plugdir / "rust.py").write_text(g.MARKER + "\nold\n", encoding="utf-8")
            # hand-written file (no marker) must survive
            (plugdir / "hand.py").write_text("# no marker\nX = 1\n", encoding="utf-8")
            (plugdir / "_util.py").write_text("Y = 2\n", encoding="utf-8")
            r = g.sync_extractors(ws)
            self.assertEqual(r["pruned"], ["rust.py"])
            self.assertFalse((plugdir / "rust.py").exists())
            self.assertTrue((plugdir / "hand.py").is_file())
            self.assertTrue((plugdir / "_util.py").is_file())
            self.assertTrue((plugdir / "go.py").is_file())

    def test_missing_grammar_reported_not_fatal(self):
        with tempfile.TemporaryDirectory() as d:
            ws = _ws(d, 'enable = ["go"]\n'
                        '[languages.go]\n'
                        'grammar = "tree_sitter_nonexistent_xyz"\n'
                        'package = "tree-sitter-nonexistent-xyz"\n'
                        'lang_func = "language"\nlang_name = "go"\n'
                        'suffixes = [".go"]\nwrapper = []\nwrapper_kw = ""\nfn = []\ncontainer = []\n'
                        'body = []\nmember = []\ntype = []\nlexical_nodes = []\nlexical_markers = []\nlexical = false\n')
            r = g.sync_extractors(ws)
            self.assertEqual(len(r["missing"]), 1)
            name, pip_cmd = r["missing"][0]
            self.assertEqual(name, "go")
            self.assertIn("tree-sitter-nonexistent-xyz", pip_cmd)

    def test_generated_ts_output_fidelity(self):
        """Generated TS plugin must extract exactly like the legacy core version.

        Expected strings hand-computed from the legacy algorithm; runs only
        where tree-sitter-typescript is installed (else skipped like the old test).
        """
        import importlib.util
        import sys
        try:
            import tree_sitter  # noqa: F401
            import tree_sitter_typescript  # noqa: F401
        except ImportError:
            self.skipTest("tree-sitter-typescript not installed")
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "typescript.py"
            p.write_text(g.render_plugin("typescript", g.DEFAULT_LANGS["typescript"]))
            spec = importlib.util.spec_from_file_location("gen_ts_fidelity", p)
            assert spec is not None and spec.loader is not None
            mod = importlib.util.module_from_spec(spec)
            sys.modules["gen_ts_fidelity"] = mod
            try:
                spec.loader.exec_module(mod)
                f = Path(d) / "sample.ts"
                f.write_text(
                    'import { x } from "./y";\n'
                    "export function foo(x: number): number {\n  return x + 1;\n}\n"
                    "export class Bar {\n  name: string;\n  run(n: number): void {\n  }\n}\n"
                    "export interface Shape {\n  area(): number;\n}\n"
                    "export const g = (a: number): number => {\n  return a;\n};\n"
                    "export const V = 5;\n"
                    "const hidden = 1;\n",
                )
                self.assertEqual(
                    mod.extract_typescript_interface(f),
                    "export function foo(x: number): number\n"
                    "export class Bar\n"
                    "  name: string\n"
                    "  run(n: number): void\n"
                    "export interface Shape {\n"
                    "  area(): number;\n"
                    "}\n"
                    "export const g = (a: number): number =>\n"
                    "export const V = 5;",
                )
            finally:
                sys.modules.pop("gen_ts_fidelity", None)


if __name__ == "__main__":
    unittest.main()
