"""文档规约化的确定性修复（闭集、幂等、可预演）。

范围守 ADR-0022 §2.2 🅰1.3：只做**无歧义**的文件级改写；散文、编码猜测不在内。
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from k3dge.engine import doc_fix, gate_facts


def _ws(d: Path) -> Path:
    (d / "docs" / "memo").mkdir(parents=True, exist_ok=True)
    (d / "docs" / "tasks").mkdir(parents=True, exist_ok=True)
    return d


class TestRuleSetConsistency(unittest.TestCase):
    def test_fixable_rules_are_declared_deterministic(self):
        """守卫：本模块能修的规则，必须都在 `gate_facts` 里声明为 deterministic。

        两处状态机（声明表 / 修复器）不得分叉——声明说"进程能修"而修复器不认（或反之）
        都会让 `docs_normalized` 闸与 `k3dge doc fix` 的说法不一致。
        """
        for rule in doc_fix.FIXABLE_RULES:
            self.assertTrue(gate_facts.is_declared(rule), rule)
            self.assertEqual(gate_facts.fix_kind(rule), "deterministic", rule)

    def test_encoding_is_not_in_scope(self):
        """`MD_ENCODING` 属判断类（源编码猜错会损坏文件）⇒ 不得进修复器。"""
        self.assertNotIn("MD_ENCODING", doc_fix.FIXABLE_RULES)
        self.assertEqual(gate_facts.fix_kind("MD_ENCODING"), "judgment")


class TestApplyRules(unittest.TestCase):
    def _scan_and_fix(self, rel: str, body: str, **kw) -> tuple:
        d = Path(tempfile.mkdtemp())
        _ws(d)
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body.encode("utf-8"))
        before = doc_fix.scan(d)
        report = doc_fix.apply(d, **kw)
        return d, p, before, report

    def test_trailing_ws(self):
        _d, p, before, rep = self._scan_and_fix("docs/memo/a.md", "# t\n\n行尾有空白   \n")
        self.assertIn("MD_TRAILING_WS", [b["rule"] for b in before])
        self.assertEqual(p.read_text(encoding="utf-8"), "# t\n\n行尾有空白\n")
        self.assertEqual([f["rule"] for f in rep["fixed"]], ["MD_TRAILING_WS"])

    def test_crlf(self):
        _d, p, _b, _r = self._scan_and_fix("docs/memo/a.md", "# t\r\n\r\n正文\r\n")
        self.assertNotIn("\r", p.read_text(encoding="utf-8"))

    def test_final_newline(self):
        _d, p, _b, _r = self._scan_and_fix("docs/memo/a.md", "# t\n\n正文")
        self.assertTrue(p.read_text(encoding="utf-8").endswith("正文\n"))

    def test_task_body_meta_redundant(self):
        body = ("---\nstatus: idea\npriority: P2\ndate: 2026-09-19\n---\n\n# t\n\n"
                "- **Status**: idea\n- **Priority**: P2\n- **可检索摘要**: 一句话\n")
        _d, p, before, rep = self._scan_and_fix("docs/tasks/2026-09-19-M10-x-y.md", body)
        self.assertIn("TASK_BODY_META_REDUNDANT", [b["rule"] for b in before])
        text = p.read_text(encoding="utf-8")
        self.assertNotIn("- **Status**:", text)
        self.assertNotIn("- **Priority**:", text)
        self.assertIn("- **可检索摘要**:", text)      # 没有 frontmatter 对应字段的正文行不动

    def test_idempotent(self):
        """幂等：再跑一次应为零改动（闸 `docs_normalized` 的零偏差判据依赖它）。"""
        d, _p, _b, first = self._scan_and_fix("docs/memo/a.md", "# t\n\n正文   ")
        self.assertTrue(first["fixed"])
        second = doc_fix.apply(d)
        self.assertEqual(second["fixed"], [])
        self.assertEqual(doc_fix.scan(d), [])

    def test_dry_run_writes_nothing(self):
        d = Path(tempfile.mkdtemp())
        _ws(d)
        p = d / "docs" / "memo" / "a.md"
        p.write_text("# t\n\n正文   \n", encoding="utf-8")
        rep = doc_fix.apply(d, dry_run=True)
        self.assertTrue(rep["fixed"])
        self.assertIn("   \n", p.read_text(encoding="utf-8"))   # 原样
        self.assertTrue(doc_fix.scan(d))                        # 仍可检出

    def test_clean_repo_is_noop(self):
        repo = Path(__file__).resolve().parents[3]
        self.assertEqual(doc_fix.scan(repo), [])
        self.assertEqual(doc_fix.apply(repo, dry_run=True)["fixed"], [])


class TestScope(unittest.TestCase):
    def test_skips_aux_archive_generated_obsolete(self):
        d = Path(tempfile.mkdtemp())
        _ws(d)
        for rel in ("docs/memo/README.md", "docs/memo/archive/old.md",
                    "docs/generated/api.md", "docs/adr/obsolete/0001-x.md"):
            p = d / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("# t\n\n正文   \n", encoding="utf-8")
        self.assertEqual(doc_fix.scan(d), [])      # 都不在扫描面里


class TestNextHint(unittest.TestCase):
    """`[NEXT] doc_fix`：主动动作提示（priority 2——不修就封不了板）。"""

    def _ws_with_deviation(self) -> Path:
        d = Path(tempfile.mkdtemp())
        (d / ".agent").mkdir(parents=True)
        (d / ".agent" / "manifest.json").write_text('{"package_root":"src","domains":{}}', encoding="utf-8")
        (d / ".agent" / "milestone").write_text("M10\n", encoding="utf-8")
        (d / "docs" / "memo").mkdir(parents=True)
        (d / "docs" / "memo" / "a.md").write_text("# t\n\n正文   \n", encoding="utf-8")
        return d

    def test_hint_emitted_with_counts(self):
        from k3dge.cli.main import _collect_hints

        steps = _collect_hints(self._ws_with_deviation())
        hits = [s for s in steps if s.state == "doc_fix"]
        self.assertEqual(len(hits), 1)
        ns = hits[0]
        self.assertEqual(ns.priority, 2)
        self.assertIn("1 处", ns.fact)                 # 计数已填（模板里的 <n>）
        self.assertIn("MD_TRAILING_WS", ns.fact)
        self.assertNotIn("<n>", ns.fact)
        self.assertGreaterEqual(len(ns.options or []), 2)   # 成对选项（ADR-0026 §2.2）

    def test_no_hint_when_clean(self):
        from k3dge.cli.main import _collect_hints

        d = self._ws_with_deviation()
        doc_fix.apply(d)
        self.assertEqual([s for s in _collect_hints(d) if s.state == "doc_fix"], [])
