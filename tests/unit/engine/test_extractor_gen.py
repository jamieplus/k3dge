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
        真实故障（ABI/import 错）不得被吞成降级分支（fail-silent→fail-closed）。

        断言走 **AST**（t-141）：字符串 grep 会把注释/docstring 里的字样算数，
        `except Exception` 换个拼法（`except Exception as e:`）也能骗过子串比对。
        """
        import ast
        tree = ast.parse(g.render_plugin("typescript", g.DEFAULT_LANGS["typescript"]))
        handlers = [h for h in ast.walk(tree) if isinstance(h, ast.ExceptHandler) and h.type]

        def _types(h):
            tt = h.type.elts if isinstance(h.type, ast.Tuple) else [h.type]
            return {t.id for t in tt if isinstance(t, ast.Name)}

        types_at = [_types(h) for h in handlers]
        self.assertIn({"TypeError"}, types_at, types_at)          # 真有且**只**兜 TypeError 的处理器
        self.assertFalse([t for t in types_at if "Exception" in t],
                         f"出现吞万能 Exception 的降级分支：{types_at}")

    def test_skip_is_documented_as_gate_caught(self):
        """code-1/code-11: 缺 grammar 时 `raise ImportError` 是**被门禁吞的 skip 信号**，
        docstring 必须写明调用方 `except ImportError`（消「会红」与「never fatal」的表观矛盾）。"""
        src = g.render_plugin("typescript", g.DEFAULT_LANGS["typescript"])
        self.assertIn("except ImportError", src)
        self.assertIn("never fatal", src)

    def test_thread_safe_language_and_include_doc(self):
        """code-1/2/6：缓存不可变 Language（带锁）、Parser 每次新建；include_doc 透传。

        判据全部走 AST（t-141）：旧 grep 形状 ①`assertNotIn("_PARSER", src)` 改名
        `_SHARED_P` 即绕过，②"有锁声明"不等于"缓存路径上取了锁"，③注释里出现同样
        字串照样绿。现在：锁**以 with 语境包住**缓存读写才算线程安全。
        """
        import ast
        src = g.render_plugin("typescript", g.DEFAULT_LANGS["typescript"])
        tree = ast.parse(src)
        assigned: dict = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.targets[0], ast.Name):
                assigned.setdefault(node.targets[0].id, node.value)
        self.assertIn("_LANGUAGE", assigned)
        lock_init = assigned.get("_LANGUAGE_LOCK")
        self.assertIsNotNone(lock_init, "_LANGUAGE_LOCK 没在模块级初始化")
        self.assertIsInstance(lock_init, ast.Call)
        # ocr2-458：锁的判据必须落在**写**（ast.Store）上——旧写法收集子树里所有 Name
        # （含纯 load），于是"读在锁内、写挪到锁外"的双检锁破损照样绿。
        locked_stores = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.With):
                for item in node.items:
                    ctx = item.context_expr
                    if isinstance(ctx, ast.Name) and ctx.id == "_LANGUAGE_LOCK":
                        for sub in ast.walk(node):
                            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                                locked_stores.add(sub.id)
        self.assertIn("_LANGUAGE", locked_stores, "缓存**写**没在锁内（线程安全声明作废）")
        # ocr2-459：Parser 每次新建——不能只靠 `_PARSER` 名字黑名单（改名缓存即可绕过）。
        # 结构判据：①模块级不得有值为 `Parser(...)` 调用的赋值；②每个 `Parser(...)` 调用
        # 都必须在函数体内（否则就是被模块级缓存的形态）。
        pcalls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                  and isinstance(n.func, ast.Name) and n.func.id == "Parser"]
        self.assertTrue(pcalls, "Parser 不再每次新建？")
        module_level_cached = []
        for stmt in tree.body:
            if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call) \
                    and isinstance(stmt.value.func, ast.Name) and stmt.value.func.id == "Parser":
                module_level_cached += [t.id for t in stmt.targets if isinstance(t, ast.Name)]
        self.assertEqual(module_level_cached, [],
                         f"Parser 实例被缓存在模块级：{module_level_cached}")
        func_spans = [(n.lineno, getattr(n, "end_lineno", n.lineno))
                      for n in ast.walk(tree)
                      if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        outside = [c.lineno for c in pcalls
                   if not any(lo <= c.lineno <= hi for lo, hi in func_spans)]
        self.assertEqual(outside, [], f"Parser(...) 出现在函数体外（会被缓存）：{outside}")
        # include_doc 透传：extract 入口真以关键字传下去（调用面，不是字串）
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name)
                 and n.func.id == "extract_typescript_interface"]
        self.assertTrue(any(any(k.arg == "include_doc" and isinstance(k.value, ast.Name)
                                and k.value.id == "include_doc" for k in c.keywords)
                            for c in calls), src)


class TestGeneratedFiltering(unittest.TestCase):
    """code-6/code-9: 生成的插件在**没有 grammar 时也能测**的路径逻辑——加载模块、直接调
    `can_handle` / `_slice`（两者都不触发 tree_sitter import）。"""

    def _load(self):
        import importlib.util
        import sys
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "gen_ts.py"
            p.write_text(g.render_plugin("typescript", g.DEFAULT_LANGS["typescript"]), encoding="utf-8")
            # 构建产物在 tests/ 之外（`.agent/extractors/…`）：稀疏检出/未 sync 时 p 可以不存在，
            # `spec` 会是 None、`spec.loader` 可缺——直接抛 AttributeError 读不出"缺工件"这个因（t-142）
            # ocr2-735：旧 `assert p.is_file()` 是同函数两行上刚 write 出来的——永真，且裸 assert
            # 在 `python -O` 下整句剥掉（坏了就变 AttributeError）。用 unittest 断言（永不优化掉）。
            self.assertTrue(p.is_file(), f"构建工件不在：{p}（先跑 k3dge extractor sync）")
            spec = importlib.util.spec_from_file_location("gen_ts_filter_probe", p)
            self.assertIsNotNone(spec, f"spec_from_file_location 对 {p} 回 None")
            self.assertIsNotNone(spec.loader, f"{p} 没有可用 loader")
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
            p.write_text(g.render_plugin("typescript", g.DEFAULT_LANGS["typescript"]),
                       encoding="utf-8")     # 生成头含非 ASCII（"— do not edit"）⇒ 缺 encoding 随 locale 崩
            spec = importlib.util.spec_from_file_location("gen_ts_fidelity", p)
            # ocr2-736：同病——裸 assert 在 `python -O` 下剥掉，spec 为 None 就变
            # `AttributeError: 'NoneType'...loader`。分两句 unittest 断言（永不优化掉）。
            self.assertIsNotNone(spec, f"spec_from_file_location 对 {p} 回 None")
            self.assertIsNotNone(spec.loader, f"{p} 没有可用 loader")
            mod = importlib.util.module_from_spec(spec)
            from k3dge.engine import contract as _contract
            snapshot = list(_contract._EXTRACTORS)
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
                encoding="utf-8")
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
                # 渲染出的模块体在 import 时就 `register_extractor(...)`，只 pop sys.modules
                # 会把一个后端文件已删的提取器留在进程注册表里；`collect_domain_interface`
                # 取首个匹配 ⇒ 其它测试变成顺序相关（t-140）
                from k3dge.engine import contract as _c
                _c._EXTRACTORS[:] = snapshot


class TestGeneratedPluginSurfaceGuards(unittest.TestCase):
    """生成件里**不需要 grammar** 的两条判据：`can_handle` 的路径面与 `_slice` 的解码形状。

    code-7（09-29）：`can_handle` 旧版只比 `path.parts`，`..`／绝对路径／经 symlink 的
    忽略目录都能绕过黑名单；code-9（09-28）：`decode(errors="replace")` 把不同非法字节
    塌成同一个 U+FFFD ⇒ 两份不同文件可产出同一接口文本（哈希碰撞面）。
    """

    PLUGIN = Path(__file__).resolve().parents[3] / ".agent" / "extractors" / "typescript.py"

    def _load(self):
        """ocr2-460：测**被测代码**（`g.render_plugin`）而不是仓内构建产物——产物回归
        要等下一次 `extractor sync` 才会现形，且稀疏检出上可能根本不存在。渲染进临时目录加载。"""
        import importlib.util
        import sys

        from k3dge.engine import contract

        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "gen_ts_guards.py"
            p.write_text(g.render_plugin("typescript", g.DEFAULT_LANGS["typescript"]),
                         encoding="utf-8")
            spec = importlib.util.spec_from_file_location("gen_ts_guards", p)
            self.assertIsNotNone(spec)
            mod = importlib.util.module_from_spec(spec)
            snapshot = list(contract._EXTRACTORS)
            sys.modules["gen_ts_guards"] = mod
            try:
                spec.loader.exec_module(mod)  # 模块体只 import contract；tree-sitter 在函数内才要
            finally:
                contract._EXTRACTORS[:] = snapshot
                sys.modules.pop("gen_ts_guards", None)
        return mod

    def test_can_handle_rejects_unnormalized_and_escaping_paths(self) -> None:
        mod = self._load()
        ext = mod.TypescriptExtractor()
        self.assertTrue(ext.can_handle(Path("src/a.ts")))
        self.assertFalse(ext.can_handle(Path("/abs/a.ts")), "绝对路径不得被认领")
        self.assertFalse(ext.can_handle(Path("src/../node_modules/a.ts")), "`..` 归一后必须撞黑名单")
        self.assertFalse(ext.can_handle(Path("src/node_modules/a.ts")))
        self.assertFalse(ext.can_handle(Path("src/a.d.ts")), "声明文件按生成件处理，不抽接口")
        self.assertFalse(ext.can_handle(Path("src/app.min.js")))

    def test_can_handle_follows_dir_symlink_into_ignored(self) -> None:
        import os

        mod = self._load()
        ext = mod.TypescriptExtractor()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "node_modules").mkdir()
            f = root / "node_modules" / "a.ts"
            f.write_text("export const x = 1\n", encoding="utf-8")
            link = root / "link"
            try:
                os.symlink(str(root / "node_modules"), str(link))
            except (OSError, NotImplementedError):  # pragma: no cover - 平台不支持软链
                self.skipTest("symlink unsupported")
            # 绝对路径在首卫即拒，测不到 symlink 解析（ocr2-118）。切进目录用相对路径，
            # 让 `link/a.ts` 走完归一化+忽略目录判定。
            _cwd = os.getcwd()
            os.chdir(root)
            try:
                self.assertFalse(ext.can_handle(Path("link/a.ts")),
                                 "目录 symlink 指向忽略目录 ⇒ 归一后仍须拒")
            finally:
                os.chdir(_cwd)

    def test_slice_is_injective_on_invalid_bytes(self) -> None:
        class Node:
            start_byte, end_byte = 0, 2

        mod = self._load()
        a = mod._slice(b"\x80\x81", Node())
        b = mod._slice(b"\x81\x80", Node())
        c = mod._slice(b"\x80\x80", Node())
        self.assertNotEqual(a, b, "非法字节塌成同一 U+FFFD ⇒ 不同文件同一段接口文本")
        self.assertNotEqual(a, c)

    def test_generated_header_no_longer_tells_readers_to_edit_it(self) -> None:
        # ocr2-460：判据来自模板渲染（被测代码）；仓内产物若在，另加一条漂移对照。
        text = g.render_plugin("typescript", g.DEFAULT_LANGS["typescript"])
        first = text.splitlines()[0]
        self.assertIn("do not edit", first)
        self.assertNotIn("edit freely", text, "同一段头既禁改又教改 ⇒ 分叉指引归 README 单源")
        self.assertIn("Hand-written", text, "指向 README 的可解析去处")
        if self.PLUGIN.is_file():
            self.assertEqual(self.PLUGIN.read_text(encoding="utf-8"), text,
                             "仓内构建件与模板渲染漂移（跑 k3dge extractor sync）")


if __name__ == "__main__":
    unittest.main()
