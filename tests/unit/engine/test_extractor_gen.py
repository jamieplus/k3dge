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
