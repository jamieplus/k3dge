"""pure_schema: stdlib-only enforcement + behavioral parity with the engine."""
import ast
import sys
import unittest
from pathlib import Path

from k3dge.engine import pure_schema

SRC = Path(__file__).resolve().parents[3] / "src" / "k3dge" / "engine"
REPO = Path(__file__).resolve().parents[3]


def _stdlib_only(mod_path: Path) -> None:
    tree = ast.parse(mod_path.read_text(encoding="utf-8"))
    allowed_prefixes = ("k3dge.engine.pure_",)
    stdlib = set(sys.stdlib_module_names)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                top = a.name.split(".")[0]
                assert top in stdlib, f"{mod_path.name} imports non-stdlib {a.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                raise AssertionError(f"{mod_path.name} uses relative import")
            if node.module:
                top = node.module.split(".")[0]
                if top == "k3dge":
                    assert node.module.startswith(allowed_prefixes), (
                        f"{mod_path.name} imports non-pure k3dge module {node.module}"
                    )
                else:
                    assert top in stdlib, f"{mod_path.name} imports non-stdlib {node.module}"


class TestPurity(unittest.TestCase):
    def test_pure_schema_stdlib_only(self):
        _stdlib_only(SRC / "pure_schema.py")

    def test_pure_refs_stdlib_only(self):
        _stdlib_only(SRC / "pure_refs.py")

    def test_aux_names_in_sync(self):
        from k3dge.engine.doc_catalog import AUX_NAMES
        self.assertEqual(pure_schema.AUX_NAMES, AUX_NAMES)

    def test_frontmatter_pairs_match_task_index(self):
        from k3dge.engine.task_index import _frontmatter_pairs as engine_pairs
        cases = [
            "",
            "no frontmatter\nkey: value\n",
            "---\nstatus: idea\npriority: P2\n---\n# Title\n",
            "---\nunclosed: block\n# Title\n",
            "---\nStatus: Done\nDate: 2026-09-16\n---\n",
            "---\nkey: a: b\nempty:\n---\n",
        ]
        for c in cases:
            self.assertEqual(pure_schema.parse_frontmatter_pairs(c), engine_pairs(c), f"input: {c!r}")


class TestCheckFileParity(unittest.TestCase):
    """pure.check_file == engine._validate_file on real repo files (minus Violation wrap)."""

    def _engine_results(self, typ, path, schema):
        from k3dge.engine import doc_catalog
        seen: dict = {}
        out = doc_catalog._validate_file(REPO, typ, path, schema, seen)
        return sorted((v.rule_id, v.message, v.file_path) for v in out)

    def _pure_results(self, typ, path, schema):
        from k3dge.engine.doc_catalog import _schema_rel
        rel = str(path.relative_to(REPO)).replace("\\", "/")
        schema_rel = _schema_rel(typ)
        text = path.read_text(encoding="utf-8")
        violations, _ident, ok = pure_schema.check_file(schema, path.name, text, schema_rel=schema_rel)
        out = sorted((c, m, schema_rel if s == "schema" else rel) for c, m, s in violations)
        return out, ok

    def test_parity_across_managed_docs(self):
        import json
        from k3dge.engine import doc_catalog
        checked = 0
        for typ in doc_catalog.iter_doc_types(REPO):
            schema_path = REPO / "docs" / typ / ".schema.json"
            if not schema_path.is_file():
                continue
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            for path in doc_catalog.iter_managed_files(REPO, typ):
                try:
                    text = path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                eng = self._engine_results(typ, path, schema)
                pure, _ok = self._pure_results(typ, path, schema)
                # engine index check appends extra violations; compare the file-local subset
                pure_set = set(pure)
                eng_codes = {(c, m) for c, m, _f in eng}
                for c, m, _f in pure:
                    self.assertIn((c, m), eng_codes, f"{path}: pure violation missing in engine: {(c, m)}")
                checked += 1
        self.assertGreater(checked, 20, "parity oracle must cover real files")


class TestUnits(unittest.TestCase):
    def test_filename_invalid_regex(self):
        out, _ident, ok = pure_schema.check_filename("[invalid", {}, "docs/x/.schema.json", "a.md")
        self.assertFalse(ok)
        self.assertEqual(out[0][2], "schema")

    def test_filename_mismatch(self):
        out, _ident, ok = pure_schema.check_filename(r"^(\d{4})-", {}, "s", "nodate.md")
        self.assertFalse(ok)
        self.assertEqual(out[0][2], "file")

    def test_section_order(self):
        self.assertIsNone(pure_schema.check_section_order("## 1\n### 1.1\n## 2\n"))
        self.assertEqual(pure_schema.check_section_order("## 2\n## 1\n"), ("2", "1"))

    def test_frontmatter_date(self):
        out = pure_schema.check_frontmatter({"date": "date"}, {}, "f.md", "---\ndate: 2026-13-45\n---\n")
        # regex only checks shape YYYY-MM-DD, not calendar validity
        self.assertEqual(out, [])
        out = pure_schema.check_frontmatter({"date": "date"}, {}, "f.md", "---\ndate: yesterday\n---\n")
        self.assertEqual(len(out), 1)


if __name__ == "__main__":
    unittest.main()
