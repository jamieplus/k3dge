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
    def _fail(msg: str) -> None:
        # 守卫**不能用 assert**：`python -O` 下 assert 被整条剥掉，纯度检查静默失效（t-242）
        raise AssertionError(msg)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                top = a.name.split(".")[0]
                if top not in stdlib and not a.name.startswith(allowed_prefixes):
                    # `import k3dge.engine.pure_refs` 这种写法以前一律判违规（t-243）
                    _fail(f"{mod_path.name} imports non-stdlib {a.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                _fail(f"{mod_path.name} uses relative import")
            if node.module:
                top = node.module.split(".")[0]
                if top == "k3dge":
                    if not node.module.startswith(allowed_prefixes):
                        _fail(f"{mod_path.name} imports non-pure k3dge module {node.module}")
                elif top not in stdlib:
                    _fail(f"{mod_path.name} imports non-stdlib {node.module}")

    # 运行期动态导入不产生 ast.Import（t-244）：`importlib.import_module("numpy")`、
    # `__import__("yaml")` 能整体绕过静态扫描，把"零依赖层"变成"只在 CI 里零依赖"。
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        fname = f.id if isinstance(f, ast.Name) else (
            f"{f.value.id}.{f.attr}" if isinstance(f, ast.Attribute)
            and isinstance(f.value, ast.Name) else "")
        if fname in ("__import__", "importlib.import_module", "builtins.__import__"):
            if not node.args:
                _fail(f"{mod_path.name} 动态导入无可解析目标，纯度不可证")
            arg0 = node.args[0]
            if not isinstance(arg0, ast.Constant) or not isinstance(arg0.value, str):
                _fail(f"{mod_path.name} 的动态导入目标是运行期值，零依赖层不接受")
            top = arg0.value.split(".")[0]
            if top not in stdlib and not arg0.value.startswith(allowed_prefixes):
                _fail(f"{mod_path.name} 运行期导入非 stdlib：{arg0.value!r}")


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
                pure, ok = self._pure_results(typ, path, schema)
                rel = str(path.relative_to(REPO)).replace("\\", "/")
                # **双向**对账（t-245）：单向 `pure ⊆ engine` 按构造恒真——
                # `_validate_file` 的文件局域检查就是**委托这几个 pure 函数**的，
                # 任何未来分叉（engine 侧悄悄少调一项、或包装时丢码）都测不出。
                # 方向①pure→engine；方向②engine 的文件局域输出（file_path 属本件/
                # schema 件）必须原样来自 pure——引擎独有的跨文件项（索引、ident 台账）
                # 不在比对集。
                pure_set = set((c, m) for c, m, _f in pure)
                eng_set = set((c, m) for c, m, _f in eng)
                for c, m in pure_set:
                    self.assertIn((c, m), eng_set,
                                  f"{path}: pure violation missing in engine: {(c, m)}")
                for c, m, f in eng:
                    if f in (rel,):        # 归属本文件的 engine 违例
                        self.assertIn((c, m), pure_set,
                                      f"{path}: engine 独有文件局域违例（pure 侧没走）: {(c, m)}")
                self.assertTrue(ok, f"{path}: 被检文件文件名形状已不合法，本对账失去前提")
                checked += 1
        self.assertGreater(checked, 20, "parity oracle must cover real files")


class TestUnits(unittest.TestCase):
    def test_filename_invalid_regex(self):
        out, _ident, ok = pure_schema.check_filename("[invalid", {}, "docs/x/.schema.json", "a.md")
        self.assertFalse(ok)
        # 空表先红在形状上（t-246）：契约变了（不再出违例）时 `out[0]` 的 IndexError
        # 会伪装成测试崩溃，把真正的信号丢光
        self.assertTrue(out, "ok=False 却零违例：致命信号丢了")
        # 钉**码**不只钉 scope（t-246）：两违例同码异 scope，码漂成 FILENAME_* 也要看见
        self.assertEqual(out[0][0], "DOC_SCHEMA_INVALID")
        self.assertEqual(out[0][2], "schema")

    def test_filename_mismatch(self):
        out, _ident, ok = pure_schema.check_filename(r"^(\d{4})-", {}, "s", "nodate.md")
        self.assertFalse(ok)
        self.assertTrue(out, "ok=False 却零违例")          # 同 t-246：先断非空再索引
        self.assertEqual(out[0][0], "DOC_SCHEMA_INVALID")   # 码同、scope 才是分流点
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


class TestLiteralVsRegex(unittest.TestCase):
    """字面量清单不再被当正则猜；正则要显式 `re:` 前缀（ocr-300/301/302）。"""

    def test_status_literal_metachars_are_not_relaxed(self) -> None:
        self.assertFalse(pure_schema._status_ok("2x0", ["2.0"]))
        self.assertTrue(pure_schema._status_ok("2.0", ["2.0"]))
        self.assertFalse(pure_schema._status_ok("SuX", ["Su(ed)"]))

    def test_status_re_prefix_is_explicit_regex(self) -> None:
        self.assertTrue(pure_schema._status_ok("v2", ["re:^v\\d$"]))

    def test_sections_literal_parentheses_are_required(self) -> None:
        secs = ["## 1. 上下文 (Context)"]
        out = pure_schema.check_sections(secs, {}, "x.md", "# T\n\n## 1. 上下文 Context\n")
        self.assertEqual([c for c, _, _ in out], ["DOC_SCHEMA_INVALID"])
        ok = pure_schema.check_sections(secs, {}, "x.md", "# T\n\n## 1. 上下文 (Context)\n")
        self.assertEqual(ok, [])

    def test_sections_re_prefix_channel(self) -> None:
        out = pure_schema.check_sections(["re:^##\\s+1\\."], {}, "x.md",
                                         "# T\n## 1. 现象\n")
        self.assertEqual(out, [])

    def test_amend_block_at_eof_without_trailing_newline(self) -> None:
        text = ("# A\n\n## 2. 决策\n\n§2.1 说过\n\nAmended-by:\n"
                "  - 🅰1 | k3dit | 2026-09-01 | §1.1 起\n"
                "  - 🅰2 | k3dit | 2026-09-02 | §2.1 改")     # 文件末尾无换行
        got = pure_schema._amend_sole_sections(text)
        self.assertIn("2.1", got, "末条无尾换行被整条丢弃 ⇒ 退役/拆分判据静默失效")




_CHILD_BAD = """
import importlib.util, sys
spec = importlib.util.spec_from_file_location("tps", MOD_PATH)
m = importlib.util.module_from_spec(spec)
sys.modules["tps"] = m
spec.loader.exec_module(m)
from pathlib import Path
try:
    m._stdlib_only(Path(BAD_PATH))
except AssertionError as exc:
    print("RAISED"); raise SystemExit(0)
print("SILENT"); raise SystemExit(1)
"""

_CHILD_GOOD = """
import importlib.util, sys
spec = importlib.util.spec_from_file_location("tps", MOD_PATH)
m = importlib.util.module_from_spec(spec)
sys.modules["tps"] = m
spec.loader.exec_module(m)
from pathlib import Path
m._stdlib_only(Path(GOOD_PATH))          # `import k3dge.engine.pure_*` 必须放行（t-243）
print("OK")
"""


def _run_optimized(tmp_path: Path, flags: list, body: str, bad: Path, good: Path) -> tuple:
    import subprocess

    script = (f"MOD_PATH = {str(Path(__file__))!r}\n"
              f"BAD_PATH = {str(bad)!r}\nGOOD_PATH = {str(good)!r}\n" + body)
    f = tmp_path / ("child" + "".join(flags).replace("-", "_") + ".py")
    f.write_text(script, encoding="utf-8")
    r = subprocess.run([sys.executable, *flags, str(f)], capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def test_purity_guard_raises_even_under_optimized_mode(tmp_path) -> None:
    """守卫不得用 `assert`：`python -O` 会把它整条剥掉 ⇒ 纯度检查静默失效（t-242）。"""
    bad = tmp_path / "bad_mod.py"
    bad.write_text("import sys\nimport requests\n", encoding="utf-8")
    good = tmp_path / "good_mod.py"
    good.write_text("import k3dge.engine.pure_refs\nimport sys\n", encoding="utf-8")
    for flags in ([], ["-O"], ["-OO"]):
        rc, out, err = _run_optimized(tmp_path, flags, _CHILD_BAD, bad, good)
        assert rc == 0 and "RAISED" in out, (flags, out, err[-300:])
        rc2, out2, err2 = _run_optimized(tmp_path, flags, _CHILD_GOOD, bad, good)
        assert rc2 == 0 and "OK" in out2, (flags, out2, err2[-300:])


if __name__ == "__main__":
    unittest.main()
