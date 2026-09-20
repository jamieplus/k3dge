"""gate_facts：闸红文案/档位/可修性的单一声明面（B 线：自动 → 自主）。

守的是内容/流程解耦的**内容侧形态**：档位闭集、block 必给成对选项、不出疑问句、
占位符可安全填、可修性显式分类、检查器真给出声明要的事实。
与 `test_nextstep.TestProjectionInvariants` 同口径——两个投影面（[NEXT] 与闸红）
必须同形，否则判断主体会收到两种形状。
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


class TestFixClassification(unittest.TestCase):
    """「进程能不能修」是本表的主要产出之一 ⇒ 分类必须显式，不得靠默认值。"""

    def test_every_declared_code_classifies_fix_explicitly(self):
        missing = [c for c, d in gate_facts.GATE_FACTS.items() if d.get("fix") not in gate_facts.FIX_KINDS]
        self.assertEqual(missing, [])

    def test_deterministic_codes_carry_a_hint(self):
        bad = [c for c, d in gate_facts.GATE_FACTS.items()
               if d.get("fix") == "deterministic" and not d.get("fix_hint")]
        self.assertEqual(bad, [])

    def test_deterministic_render_shows_fix_line(self):
        self.assertIn("fix: 确定性可修——k3dge sync",
                      gate_facts.render("DOC_INDEX_STALE", {"reason": "stale"}))
        # 需判断的 code 不得冒充可自动修
        self.assertNotIn("fix:", gate_facts.render("ADR_NUMBER_MISMATCH", {"path": "docs/adr/0001-x.md"}))

    def test_inventory_matches_rulings(self):
        """清单对齐用户裁定（2026-09-19）：已有命令即修法 ⇒ 确定性可修；
        方向不明 / 要读懂语义 / 会改史 ⇒ 需判断（ADR_NUMBER_MISMATCH、TEMPLATE_DRIFT 明写不自动修）。"""
        det = {c for c in gate_facts.GATE_FACTS if gate_facts.fix_kind(c) == "deterministic"}
        for code in ("TASK_BODY_META_REDUNDANT", "ADR_SUPERSEDE_UNRECONCILED", "DOC_INDEX_STALE",
                     "CONTRACT_DRIFT", "CONTRACT_HASH_MISSING", "VERSION_MISMATCH",
                     "MD_TRAILING_WS", "MD_CRLF", "MD_NO_FINAL_NEWLINE"):
            self.assertIn(code, det, code)
        for code in ("ADR_NUMBER_MISMATCH", "TEMPLATE_DRIFT", "MD_CONFLICT_MARKER", "MD_ENCODING",
                     "MD_FENCE_UNCLOSED", "DOC_SECTION_ORDER", "DOC_NEW_UNSCREENED",
                     "DOC_SCHEMA_INVALID", "DANGLING_ADR_REF", "TASK_STATUS_MISMATCH"):
            self.assertEqual(gate_facts.fix_kind(code), "judgment", code)
        # 未声明的 code 保守按 judgment（不假装能自动修）
        self.assertEqual(gate_facts.fix_kind("SOMETHING_NEW"), "judgment")


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

    def test_render_carries_detail_and_where(self):
        text = gate_facts.render("CONTRACT_DRIFT",
                                 {"expected_hash": "abc", "actual_hash": "def"},
                                 where="<engine> [docs/specs/engine/spec.md]",
                                 detail="symbol diff: +foo -bar")
        self.assertIn("<engine>", text)
        self.assertIn("spec=abc", text)
        self.assertIn("detail: symbol diff: +foo -bar", text)

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

    def test_no_unfilled_placeholder_for_any_code(self):
        """全表自动覆盖：喂代表性事实后不得残留 `{key}`。"""
        for code in gate_facts.GATE_FACTS:
            facts = {k: f"<{k}>" for k in gate_facts.facts_of(code)}
            out = gate_facts.render(code, facts)
            self.assertNotIn("{", out, f"{code}: {out}")
            self.assertIn("fact:", out, code)


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
        """增量迁移：未进表的 code 仍走旧形状（message 自带），不得变空。

        用一个刻意不存在的 code——迁移完成后本测试仍须成立（表的兜底路径不能被删）。
        """
        code = "ZZZ_NOT_DECLARED_YET"
        self.assertFalse(gate_facts.is_declared(code))
        v = Violation(code, "raw message", domain="engine", file_path="x.md")
        self.assertEqual(v.format(), f"[GATE ERROR] {code} <engine>: raw message [x.md]")

    def test_severity_tag_follows_declaration(self):
        self.assertTrue(Violation("ORPHAN_TEST", "t", file_path="tests/x.py").format()
                        .startswith("[GATE WARN]"))
        self.assertTrue(Violation("DUP_CHECK", "t").format().startswith("[GATE NOTE]"))

    def test_json_carries_severity(self):
        from k3dge.cli.main import _to_json
        from k3dge.engine.models import GateReport

        rep = GateReport(passed=False, violations=(Violation("ORPHAN_ADR", "a"),))
        self.assertEqual(_to_json(rep)["violations"][0]["severity"], "warn")


class TestProducersFeedDeclaredFacts(unittest.TestCase):
    """结构守卫：声明了占位符的 code，其 `Violation(...)` 构造点必须给 `detail=`。

    这是"内容/流程解耦"的接缝检查——表里写了 `{path}`，检查器就必须真给 `path`；
    否则文案永远缺字段，而这种漂移以前无人发现。静态扫 AST，不靠人记。
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
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    yield py.relative_to(root), node, first.value

    def test_declared_codes_with_placeholders_pass_detail(self):
        missing = []
        for rel, node, code in self._violation_calls():
            keys = set(gate_facts.facts_of(code))
            if not keys:
                continue
            if "detail" not in {k.arg for k in node.keywords}:
                missing.append(f"{rel}:{node.lineno} {code} 缺 detail=（声明用了 {sorted(keys)}）")
        self.assertEqual(missing, [])


class TestNoProseBackflow(unittest.TestCase):
    """棘轮：已声明的 code，其构造点不得再拼散文（措辞只能来自表）。

    实测基线 2026-09-19：35 处 Violation 构造点、静态 message 最长 25 字符（全是事实摘要）。
    阈值放到 100 是给事实字段留余量，不是给散文留口子。
    """

    MAX_MESSAGE = 100

    def test_declared_code_messages_stay_factual(self):
        import ast

        root = Path(__file__).resolve().parents[3] / "src" / "k3dge"
        offenders = []
        for py in sorted(root.rglob("*.py")):
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                if name != "Violation" or len(node.args) < 2:
                    continue
                code = node.args[0].value if isinstance(node.args[0], ast.Constant) else None
                msg = node.args[1]
                if not (isinstance(code, str) and gate_facts.is_declared(code)):
                    continue
                if isinstance(msg, ast.Constant) and isinstance(msg.value, str):
                    if len(msg.value) > self.MAX_MESSAGE:
                        offenders.append(f"{py.relative_to(root)}:{node.lineno} {code} "
                                         f"message {len(msg.value)} 字符（措辞应归表）")
                    for word in ("run 'k3dge", "run `k3dge", "；先 ", "please "):
                        if word in msg.value:
                            offenders.append(f"{py.relative_to(root)}:{node.lineno} {code} "
                                             f"message 里出现补救散文 {word!r}（应归 options）")
        self.assertEqual(offenders, [])


class TestMessageDoesNotRestateFact(unittest.TestCase):
    """棘轮：已声明 code 的构造点 `message` 不得**复述声明 fact 的散文片段**。

    detail（检查器原文）与 fact（声明文案）是两层；message 只该是"事实摘要"，
    复述 fact 的措辞会立刻产生第二个文案源（改一处忘一处）。
    字段名/标识符的重叠不算（那本身就是事实），故只查**含中文的散文片段**。
    """

    MIN_SEG = 10

    def _segments(self, text: str):
        import re

        t = re.sub(r"\{[^}]*\}", "", text or "")
        parts = re.split(r"[，。；、（）()\[\]`：:…——\s]+", t)
        return [s.strip() for s in parts
                if len(s.strip()) >= self.MIN_SEG and re.search(r"[\u4e00-\u9fff]", s)]

    def test_static_messages_do_not_restate_facts(self):
        import ast

        root = Path(__file__).resolve().parents[3] / "src" / "k3dge"
        offenders = []
        for py in sorted(root.rglob("*.py")):
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                if name != "Violation" or len(node.args) < 2:
                    continue
                code = node.args[0].value if isinstance(node.args[0], ast.Constant) else None
                msg = node.args[1]
                if not (isinstance(code, str) and gate_facts.is_declared(code)):
                    continue
                if not (isinstance(msg, ast.Constant) and isinstance(msg.value, str)):
                    continue
                fact = (gate_facts.GATE_FACTS.get(code) or {}).get("fact", "")
                for seg in self._segments(fact):
                    if seg in msg.value:
                        offenders.append(f"{py.relative_to(root)}:{node.lineno} {code}: "
                                         f"message 复述 fact 片段 {seg!r}")
        self.assertEqual(offenders, [])


class TestFactsAreProducedNotParsed(unittest.TestCase):
    """棘轮：已声明 code 的事实字段，其消费者**不得**从 message 里切（散文解析）。

    实测前科：pre-commit 用 `msg.split(": ")[-1]` / `msg.split(":")[0]` 从检查器的
    message 里取 path——检查器一改措辞就静默取错。现在检查器只产 (code, 事实)，
    path 由调用方显式给（`where=`）。
    """

    def test_hook_does_not_split_messages(self):
        hook = (Path(__file__).resolve().parents[3] / "scripts" / "pre-commit").read_text(encoding="utf-8")
        code_lines = [ln for ln in hook.splitlines()
                      if "msg.split" in ln and not ln.strip().startswith("#")]
        self.assertEqual(code_lines, [], f"hook 仍在从 message 里切字段：{code_lines}")

    def test_pure_checks_return_facts_for_declared_codes(self):
        """抽样：`ORPHAN_*` / `MD_CRLF` / `ARCHIVE_NO_DEST` 返回的第二项就是**事实**（路径）。"""
        import tempfile

        from k3dge.engine import pure_refs

        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            p = ws / "docs" / "memo" / "a.md"
            p.parent.mkdir(parents=True)
            p.write_text("# t\r\n", encoding="utf-8")
            self.assertEqual(pure_refs.check_markdown_bytes(p.read_bytes(), "docs/memo/a.md"),
                             [("MD_CRLF", "docs/memo/a.md")])
            arch = ws / "docs" / "memo" / "archive"
            arch.mkdir(parents=True)
            (arch / "x.md").write_text("# 归档但没写去向标记\n", encoding="utf-8")
            self.assertEqual(pure_refs.find_unguarded_archives(ws, ["docs/memo/archive/x.md"]),
                             [("ARCHIVE_NO_DEST", "docs/memo/archive/x.md")])
