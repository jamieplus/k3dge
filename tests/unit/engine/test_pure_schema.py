"""pure_schema: stdlib-only enforcement + behavioral parity with the engine."""
import ast
import sys
import tempfile
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
                    if node.module.startswith(allowed_prefixes):
                        pass  # from k3dge.engine.pure_x import y
                    elif node.module in ("k3dge", "k3dge.engine"):
                        # ocr2-775：`from k3dge.engine import pure_refs`
                        # （doc_catalog.py:403 用的形状）与
                        # `import k3dge.engine.pure_refs` 同义（t-243 放行后者）——
                        # 只看 module 会误杀。看 names 是否全落进 pure_ 边界。
                        for a in node.names:
                            full = f"{node.module}.{a.name}"
                            if a.name == "*" or not full.startswith(allowed_prefixes):
                                _fail(f"{mod_path.name} imports non-pure k3dge module {full}")
                    else:
                        _fail(f"{mod_path.name} imports non-pure k3dge module {node.module}")
                elif top not in stdlib:
                    _fail(f"{mod_path.name} imports non-stdlib {node.module}")

    # 运行期动态导入不产生 ast.Import（t-244）：`importlib.import_module("numpy")`、
    # `__import__("yaml")` 能整体绕过静态扫描，把"零依赖层"变成"只在 CI 里零依赖"。
    # ocr2-516：必须解析绑定，不能只比三个字面点号名——`from importlib import import_module`
    # 后裸调 `import_module("yaml")`、别名、`builtins`/`__import__` 重绑，以及
    # exec/eval/compile 都曾从指缝溜走。
    dyn_names: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in ("importlib", "builtins"):
            for a in node.names:
                if a.name in ("import_module", "__import__"):
                    dyn_names.add(a.asname or a.name)
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] in ("importlib", "builtins"):
                    dyn_names.add(a.asname or a.name.split(".")[0])

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        is_dyn = False
        if isinstance(f, ast.Name):
            if f.id in ("exec", "eval", "compile"):
                _fail(f"{mod_path.name} 运行期代码执行 {f.id}() 绕过静态纯度检查")
            if f.id in dyn_names or f.id in ("__import__", "import_module"):
                is_dyn = True
        elif isinstance(f, ast.Attribute):
            if f.attr in ("import_module", "__import__"):
                is_dyn = True
        if not is_dyn:
            continue
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

    def test_from_import_of_pure_module_is_allowed(self):
        """ocr2-775：`from k3dge.engine import pure_refs` 不得误杀（与
        `import k3dge.engine.pure_refs` 同义，t-243）；而非纯成员仍要拦。"""
        with tempfile.TemporaryDirectory() as td:
            ok_mod = Path(td) / "ok_from.py"
            ok_mod.write_text("from k3dge.engine import pure_refs\n", encoding="utf-8")
            _stdlib_only(ok_mod)  # 不得抛
            bad_mod = Path(td) / "bad_from.py"
            bad_mod.write_text("from k3dge.engine import doc_catalog\n", encoding="utf-8")
            with self.assertRaises(AssertionError):
                _stdlib_only(bad_mod)

    def test_all_pure_modules_are_checked(self):
        """ocr2-776：纯度门按目录驱动——新增 `pure_*.py` 自动纳入零依赖门，
        不再靠手写枚举（旧形状只点名两文件，新文件 `import yaml` 也全绿）。"""
        mods = sorted(SRC.glob("pure_*.py"))
        names = [p.name for p in mods]
        self.assertIn("pure_schema.py", names, names)
        self.assertIn("pure_refs.py", names, names)
        for p in mods:
            with self.subTest(mod=p.name):
                _stdlib_only(p)

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

    def _pure_results(self, typ, path, schema, text):
        from k3dge.engine.doc_catalog import _schema_rel
        rel = str(path.relative_to(REPO)).replace("\\", "/")
        schema_rel = _schema_rel(typ)
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
                # ocr2-777：已读的 text 直接喂 pure 侧（之前 pure 侧又读一遍，
                # 每件受管文档每轮被解码三次）；engine 侧走自己的读路径（委托被测）。
                eng = self._engine_results(typ, path, schema)
                pure, ok = self._pure_results(typ, path, schema, text)
                rel = str(path.relative_to(REPO)).replace("\\", "/")
                # **双向**对账（t-245）：单向 `pure ⊆ engine` 按构造恒真——
                # `_validate_file` 的文件局域检查就是**委托这几个 pure 函数**的，
                # 任何未来分叉（engine 侧悄悄少调一项、或包装时丢码）都测不出。
                # 方向①pure→engine；方向②engine 的文件局域输出（file_path 属本件/
                # schema 件）必须原样来自 pure——引擎独有的跨文件项（索引、ident 台账）
                # 不在比对集。
                pure_set = set(pure)
                eng_set = set(eng)
                # ocr2-517：比**完整三元组**（码 + 消息 + file_path）。旧形状只比 (码,消息)，
                # `_validate_file` 的 `schema_rel if scope=="schema" else rel` 映射被整个跳过，
                # 映射反转/scope 翻面都照样绿。
                for c, m, f in pure_set:
                    self.assertIn((c, m, f), eng_set,
                                  f"{path}: pure violation missing in engine: {(c, m, f)}")
                schema_rel = doc_catalog._schema_rel(typ)
                for c, m, f in eng:
                    if f in (rel, schema_rel):     # 归属本件/schema 件的 engine 违例
                        self.assertIn((c, m, f), pure_set,
                                      f"{path}: engine 独有文件局域违例（pure 侧没走）: {(c, m, f)}")
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


class TestPurityGuardUnderOptimized(unittest.TestCase):
    """ocr2-518：守卫不得用 `assert`，且必须能被 `unittest` 收集。

    旧形状是模块级 pytest 函数 + 裸 `assert`：`python -O` 下断言整条剥掉，
    直跑/`python -m unittest` 又不收集函数——t-242 的守卫在两种路径上都是空转。
    """

    def test_purity_guard_raises_even_under_optimized_mode(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            bad = tmp / "bad_mod.py"
            bad.write_text("import sys\nimport requests\n", encoding="utf-8")
            good = tmp / "good_mod.py"
            good.write_text("import k3dge.engine.pure_refs\nimport sys\n", encoding="utf-8")
            for flags in ([], ["-O"], ["-OO"]):
                rc, out, err = _run_optimized(tmp, flags, _CHILD_BAD, bad, good)
                self.assertTrue(rc == 0 and "RAISED" in out, (flags, out, err[-300:]))
                rc2, out2, err2 = _run_optimized(tmp, flags, _CHILD_GOOD, bad, good)
                self.assertTrue(rc2 == 0 and "OK" in out2, (flags, out2, err2[-300:]))

    def test_dynamic_import_aliases_are_not_a_bypass(self) -> None:
        """ocr2-516：绑定/别名/exec 三类绕过都要被守卫拦下。"""
        cases = {
            "from_import": "from importlib import import_module\nimport_module('requests')\n",
            "alias": "import importlib as im\nim.import_module('requests')\n",
            "builtins": "import builtins\nbuiltins.__import__('requests')\n",
            "exec": "exec('import requests')\n",
            "eval": "eval('__import__(\"requests\")')\n",
            "compile": "compile('import requests', '<s>', 'exec')\n",
        }
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            for name, src in cases.items():
                with self.subTest(case=name):
                    mod = tmp / f"{name}.py"
                    mod.write_text(src, encoding="utf-8")
                    with self.assertRaises(AssertionError, msg=name):
                        _stdlib_only(mod)
        # 正对照：合法的 `re.compile`（Attribute，非裸 compile）不得被误伤
        with tempfile.TemporaryDirectory() as td:
            mod = Path(td) / "ok.py"
            mod.write_text("import re\nRE = re.compile('x')\n", encoding="utf-8")
            _stdlib_only(mod)   # 不得抛



class TestFrontmatterSchemaRel(unittest.TestCase):
    def test_unsupported_rule_shape_reports_violation_not_nameerror(self) -> None:
        # 不支持的规则形状必须报 `DOC_SCHEMA_INVALID`，不能 `NameError: schema_rel`（ocr2-003）。
        out = pure_schema.check_frontmatter({"k": 123}, {}, "f.md", "---\nk: v\n---\n")
        self.assertTrue(out and out[0][0] == "DOC_SCHEMA_INVALID" and "不支持" in out[0][1])
        # 带显式 schema_rel 时用它
        out2 = pure_schema.check_frontmatter({"k": 123}, {}, "f.md", "---\nk: v\n---\n",
                                              schema_rel="docs/x/.schema.json")
        self.assertIn("docs/x/.schema.json", out2[0][1])


if __name__ == "__main__":
    unittest.main()
