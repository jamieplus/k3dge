"""gate_facts：闸红文案/档位的单一声明面（B 线：自动 → 自主）。

守的是内容/流程解耦的**内容侧形态**：档位闭集、block 必给成对选项、不出疑问句、
占位符可安全填、未声明 code 有兜底。与 `test_nextstep.TestProjectionInvariants` 同口径
——两个投影面（[NEXT] 与闸红）形态必须一致，否则判断主体会收到两种形状。
"""
from __future__ import annotations

import unittest
from pathlib import Path

from k3dge.engine import gate_facts
from k3dge.engine.models import Violation


class TestDeclarationShape(unittest.TestCase):
    def test_severity_is_closed_set(self):
        for code, decl in gate_facts.GATE_FACTS.items():
            self.assertIn(decl.get("severity"), gate_facts.SEVERITIES, code)

    def test_blocking_codes_come_in_pairs(self):
        """block ⇒ ≥2 个 options（只给一条路＝下令，不是给判断主体）。"""
        bad = [c for c, d in gate_facts.GATE_FACTS.items()
               if d.get("severity") == "block" and len(d.get("options") or []) < 2]
        self.assertEqual(bad, [])

    def test_no_interrogative_in_declared_text(self):
        """疑问句会把预设嵌进句式 ⇒ 纯打印面一律陈述式（ADR-0026 §2.2 语法维）。"""
        for code, decl in gate_facts.GATE_FACTS.items():
            for text in [decl.get("fact", "")] + list(decl.get("options") or []):
                self.assertNotIn("？", text, code)
                self.assertNotIn("y/N", text, code)
                self.assertNotIn("倒计时", text, code)

    def test_every_declared_code_has_fact_and_pointers(self):
        for code, decl in gate_facts.GATE_FACTS.items():
            self.assertTrue(decl.get("fact"), code)
            self.assertTrue(decl.get("pointers"), code)

    def test_placeholders_are_covered_by_producers(self):
        """声明里用的占位键，必须由产出该 code 的检查器真给出来（否则文案永远缺字段）。"""
        self.assertEqual(set(gate_facts.facts_of("CONTRACT_DRIFT")),
                         {"expected_hash", "actual_hash"})
        self.assertEqual(set(gate_facts.facts_of("DOC_NEW_UNSCREENED")), {"path"})
        # evaluator 的 detail 确实带这两个键（回归：改字段名会同时红两处）
        self.assertEqual(set(gate_facts.facts_of("ORPHAN_TEST")), {"path"})


class TestRendering(unittest.TestCase):
    def test_fill_leaves_missing_keys_intact(self):
        self.assertEqual(gate_facts.fill("a={x} b={y}", {"x": 1}), "a=1 b={y}")
        self.assertEqual(gate_facts.fill("no facts", None), "no facts")

    def test_fill_survives_literal_braces(self):
        """模板里有非占位花括号不得抛（工具坏不得阻断提交）。"""
        self.assertIn("{", gate_facts.fill("code={a} set={}", {"a": 1}))

    def test_render_shape(self):
        text = gate_facts.render("DOC_NEW_UNSCREENED", {"path": "docs/memo/x.md"})
        self.assertTrue(text.startswith("[DOC_NEW_UNSCREENED]"))
        self.assertIn("fact:", text)
        self.assertGreaterEqual(text.count("option:"), 2)
        self.assertIn("pointers:", text)
        self.assertIn("k3dge doc screen docs/memo/x.md", text)

    def test_render_with_where(self):
        text = gate_facts.render("CONTRACT_DRIFT",
                                 {"expected_hash": "abc", "actual_hash": "def"},
                                 where="<engine> [docs/specs/engine/spec.md]")
        self.assertIn("<engine>", text)
        self.assertIn("spec=abc", text)

    def test_undeclared_code_is_safe(self):
        self.assertEqual(gate_facts.render("SOMETHING_NEW"), "")
        self.assertEqual(gate_facts.severity("SOMETHING_NEW"), gate_facts.DEFAULT_SEVERITY)
        self.assertFalse(gate_facts.is_declared("SOMETHING_NEW"))

    def test_projection_is_closed_set(self):
        """给进程的投影：只有 code/severity/declared/facts，无文案、无分支余地。"""
        d = gate_facts.projection("ORPHAN_ADR", {"path": "docs/adr/0099-x.md"})
        self.assertEqual(set(d), {"code", "severity", "declared", "facts"})
        self.assertEqual(d["severity"], "warn")
        self.assertTrue(d["declared"])


class TestViolationWiring(unittest.TestCase):
    def test_declared_code_renders_from_table(self):
        v = Violation("CONTRACT_DRIFT", "spec=abc code=def", domain="engine",
                      file_path="docs/specs/engine/spec.md",
                      detail={"expected_hash": "abc123", "actual_hash": "def456"})
        out = v.format()
        self.assertTrue(out.startswith("[GATE ERROR] [CONTRACT_DRIFT]"))
        self.assertIn("fact:", out)
        self.assertIn("option: k3dge sync", out)
        self.assertIn("abc123", out)

    def test_undeclared_code_keeps_legacy_shape(self):
        """增量迁移：未进表的 code 仍走旧形状（message 自带），不得变空。"""
        v = Violation("SPEC_NOT_FOUND", "spec missing", domain="engine", file_path="x.md")
        self.assertEqual(v.format(), "[GATE ERROR] SPEC_NOT_FOUND <engine>: spec missing [x.md]")

    def test_severity_tag_follows_declaration(self):
        warn = Violation("ORPHAN_TEST", "t", file_path="tests/x.py").format()
        self.assertTrue(warn.startswith("[GATE WARN]"), warn)

    def test_json_carries_severity(self):
        from k3dge.cli.main import _to_json
        from k3dge.engine.models import GateReport

        rep = GateReport(passed=False, violations=(Violation("ORPHAN_ADR", "a"),))
        row = _to_json(rep)["violations"][0]
        self.assertEqual(row["severity"], "warn")


class TestProducersFeedDeclaredFacts(unittest.TestCase):
    """结构守卫：声明了占位符的 code，其构造点必须给 `detail=`（否则文案永远缺字段）。

    这是"内容/流程解耦"的接缝检查——表里写了 `{path}`，检查器就必须真给 `path`。
    静态扫 AST，不靠人记。
    """

    def _violation_calls(self):
        import ast

        root = Path(__file__).resolve().parents[3] / "src" / "k3dge"
        for py in sorted(root.rglob("*.py")):
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                if name != "Violation" or not node.args:
                    continue
                first = node.args[0]
                code = first.value if isinstance(first, ast.Constant) else None
                if isinstance(code, str):
                    yield py.relative_to(root), node, code

    def test_declared_codes_with_placeholders_pass_detail(self):
        missing = []
        for rel, node, code in self._violation_calls():
            keys = set(gate_facts.facts_of(code))
            if not keys:
                continue
            kw = {k.arg for k in node.keywords}
            if "detail" not in kw:
                missing.append(f"{rel}:{node.lineno} {code} 缺 detail=（声明用了 {sorted(keys)}）")
        self.assertEqual(missing, [])

    def test_no_unfilled_placeholder_in_rendered_output(self):
        """代表性事实喂进去后，渲染结果不得残留 `{key}`。"""
        samples = {
            "CONTRACT_DRIFT": {"expected_hash": "a", "actual_hash": "b"},
            "DOC_INDEX_STALE": {"reason": "stale"},
            "CONTRACT_HASH_MISSING": {"domain": "engine", "spec": "docs/specs/engine/spec.md"},
            "VERSION_MISMATCH": {"drift": "pyproject=1 ≠ manifest=2"},
            "TEMPLATE_DRIFT": {"asset": "assets/agents.md", "repo": "AGENTS.md"},
            "DOC_NEW_UNSCREENED": {"path": "docs/memo/x.md"},
            "ORPHAN_TEST": {"path": "tests/x.py"},
            "ORPHAN_SPEC": {"path": "docs/specs/x.md"},
            "ORPHAN_ADR": {"path": "docs/adr/0099-x.md"},
            "DUP_CHECK": {"count": 3},
        }
        self.assertEqual(set(samples), set(gate_facts.GATE_FACTS))  # 表增删必须同步本测试
        for code, facts in samples.items():
            self.assertNotIn("{", gate_facts.render(code, facts), code)
