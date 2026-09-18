"""pure_refs: B1 dangling refs, B2 name/content, B3 markdown, B4 orphans."""
import tempfile
import unittest
from pathlib import Path

from k3dge.engine import pure_refs

REPO = Path(__file__).resolve().parents[3]


def _ws(d, adrs=(), tasks=(), specs=(), tests=()):
    ws = Path(d)
    (ws / "docs" / "adr").mkdir(parents=True, exist_ok=True)
    for name, body in adrs:
        p = ws / "docs" / "adr" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    (ws / "docs" / "adr" / "README.md").write_text(
        "# ADRs\n\n## Topics\n\n- **Gate**: 0001\n", encoding="utf-8")
    for name, body in tasks:
        p = ws / "docs" / "tasks" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    for name, body in specs:
        p = ws / "docs" / "specs" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    for name, body in tests:
        p = ws / "tests" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    return ws


class TestDanglingAdr(unittest.TestCase):
    def test_missing_number_flags(self):
        with tempfile.TemporaryDirectory() as d:
            ws = _ws(d, adrs=[("0001-a.md", "# ADR-0001\n")])
            out = pure_refs.check_dangling_adr(ws, "docs/x.md", "see ADR-0001 and ADR-0099")
            self.assertEqual(len(out), 1)
            self.assertIn("ADR-0099", out[0][1])

    def test_obsolete_counts_as_resolved(self):
        with tempfile.TemporaryDirectory() as d:
            ws = _ws(d)
            obs = ws / "docs" / "adr" / "obsolete"
            obs.mkdir(parents=True)
            (obs / "0002-old.md").write_text("# ADR-0002\n", encoding="utf-8")
            out = pure_refs.check_dangling_adr(ws, "docs/x.md", "see ADR-0002")
            self.assertEqual(out, [])

    def test_fenced_refs_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            ws = _ws(d)
            out = pure_refs.check_dangling_adr(ws, "docs/x.md", "```\nADR-0099 example\n```\n")
            self.assertEqual(out, [])


class TestFootnotes(unittest.TestCase):
    def test_missing_definition(self):
        out = pure_refs.check_footnotes("f.md", "see [^A1] here\n\n[^A2]: defined\n")
        self.assertEqual(len(out), 1)
        self.assertIn("A1", out[0][1])

    def test_paired_ok(self):
        out = pure_refs.check_footnotes("f.md", "see [^A1]\n\n[^A1]: detail\n")
        self.assertEqual(out, [])

    def test_literal_in_code_span_is_not_a_reference(self):
        """文档描述该模式（表格里的 `[^X]`）不是活引用——否则闸自己造假红。"""
        out = pure_refs.check_footnotes(
            "f.md", "| footnote `[^X]` 有引用必须有定义 | `re` 配对 |\n")
        self.assertEqual(out, [])

    def test_adr_ref_in_code_span_still_checked(self):
        """反向守卫：ADR 指针常写在反引号里，不得因 code-span 处理而漏检。"""
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            (ws / "docs" / "adr").mkdir(parents=True)
            out = pure_refs.check_dangling_adr(ws, "docs/x.md", "见 `ADR-0099` 与 `docs/adr/0099-y.md`\n")
            self.assertEqual([c for c, _ in out], ["DANGLING_ADR_REF"])

    def test_real_adr_footnotes_pair(self):
        text = (REPO / "docs" / "adr" / "0006-mcp-foreign-harness-injection.md").read_text(encoding="utf-8")
        out = pure_refs.check_footnotes("docs/adr/0006-mcp-foreign-harness-injection.md", text)
        self.assertEqual(out, [])


class TestTaskConsistency(unittest.TestCase):
    def test_done_without_suffix(self):
        out = pure_refs.check_task_consistency(
            "docs/tasks/2026-09-16-fix-x.md", "---\nstatus: done\n---\n# t\n")
        self.assertEqual(len(out), 1)
        self.assertIn(".done.md", out[0][1])

    def test_suffix_without_done(self):
        out = pure_refs.check_task_consistency(
            "docs/tasks/2026-09-16-fix-x.done.md", "---\nstatus: idea\n---\n# t\n")
        self.assertEqual(len(out), 1)

    def test_consistent_ok(self):
        out = pure_refs.check_task_consistency(
            "docs/tasks/2026-09-16-fix-x.done.md", "---\nstatus: done\n---\n# t\n")
        self.assertEqual(out, [])

    def test_milestone_mismatch(self):
        out = pure_refs.check_task_consistency(
            "docs/tasks/2026-09-16-fix-x.done.md",
            "---\nstatus: done\nmilestone: M11\n---\n# t\n")
        codes = [c for c, _ in out]
        self.assertIn("TASK_MILESTONE_MISMATCH", codes)

    def test_non_task_skipped(self):
        self.assertEqual(pure_refs.check_task_consistency("docs/guides/x.md", "---\nstatus: done\n---\n"), [])


class TestTaskMetaAgreement(unittest.TestCase):
    """双源对照：frontmatter ↔ body（权威源 vs 人类可读副本）。"""

    REL = "docs/tasks/2026-09-16-M10-fix-x.done.md"

    def _task(self, fm_lines, body_lines):
        fm = "---\n" + "\n".join(fm_lines) + "\n---\n"
        body = "\n".join(f"- **{k}**: {v}" for k, v in body_lines)
        return f"{fm}\n# 标题\n\n{body}\n"

    def test_agreed_passes(self):
        text = self._task(
            ["status: done", "milestone: M10", "priority: P2", "date: 2026-09-16"],
            [("Status", "done"), ("Milestone", "M10"), ("Priority", "P2"), ("Date", "2026-09-16")],
        )
        self.assertEqual(pure_refs.check_task_meta_agreement(self.REL, text), [])

    def test_status_divergence_detected(self):
        text = self._task(["status: done"], [("Status", "idea")])
        out = pure_refs.check_task_meta_agreement(self.REL, text)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0][0], "TASK_META_DIVERGENCE")
        self.assertIn("Status", out[0][1])

    def test_milestone_divergence_detected(self):
        text = self._task(["milestone: M10"], [("Milestone", "M99")])
        self.assertTrue(any("Milestone" in m for _c, m in pure_refs.check_task_meta_agreement(self.REL, text)))

    def test_report_backtick_normalized(self):
        """body 的 Report 带反引号，对照前须归一，否则恒报假阳。"""
        text = self._task(["report: docs/reviews/x.md"], [("Report", "`docs/reviews/x.md`")])
        self.assertEqual(pure_refs.check_task_meta_agreement(self.REL, text), [])

    def test_single_side_missing_not_reported(self):
        """写入端不保证全字段（milestone/report 可缺）⇒ 单侧缺失不得报。"""
        text = self._task(
            ["status: idea", "priority: P2", "date: 2026-09-16"],
            [("Status", "idea"), ("Priority", "P2"), ("Date", "2026-09-16")],
        )
        self.assertEqual(pure_refs.check_task_meta_agreement(self.REL, text), [])

    def test_legacy_without_frontmatter_skipped(self):
        """无 frontmatter 的遗留任务：body 即唯一源，无从对照，不得误伤。"""
        text = "# 遗留\n\n- **Status**: idea\n- **Milestone**: M10\n"
        self.assertEqual(pure_refs.check_task_meta_agreement(self.REL, text), [])

    def test_non_task_skipped(self):
        self.assertEqual(
            pure_refs.check_task_meta_agreement("docs/guides/x.md", "---\nstatus: done\n---\n"), [])

    def test_wired_into_check_task_consistency(self):
        """接线：check_task_consistency 必须包含双源对照（否则 pre-commit 不会跑）。"""
        text = self._task(["status: done"], [("Status", "idea")])
        codes = [c for c, _ in pure_refs.check_task_consistency(self.REL, text)]
        self.assertIn("TASK_META_DIVERGENCE", codes)


class TestAdrConsistency(unittest.TestCase):
    def test_mismatch(self):
        out = pure_refs.check_adr_consistency("docs/adr/0006-x.md", "# ADR-0007: y\n")
        self.assertEqual(len(out), 1)

    def test_match_ok(self):
        out = pure_refs.check_adr_consistency("docs/adr/0006-x.md", "# ADR-0006: y\n")
        self.assertEqual(out, [])


class TestSupersedeUnreconciled(unittest.TestCase):
    """声明 Supersedes ⇒ 目标必须已归档。红时给出修复路径（k3dge sync）。"""

    REL = "docs/adr/0002-new.md"
    DECL = "---\nStatus: Accepted\nSupersedes: ADR-0001\n---\n# ADR-0002: new\n"

    def _ws(self, d):
        ws = Path(d)
        adr = ws / "docs" / "adr"
        adr.mkdir(parents=True)
        return ws, adr

    def test_declared_but_still_in_place_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            ws, adr = self._ws(d)
            (adr / "0001-old.md").write_text("---\nStatus: Accepted\n---\n# ADR-0001\n", encoding="utf-8")
            out = pure_refs.check_supersede_unreconciled(ws, self.REL, self.DECL)
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0][0], "ADR_SUPERSEDE_UNRECONCILED")
            self.assertIn("k3dge sync", out[0][1])

    def test_missing_from_obsolete_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            ws, adr = self._ws(d)   # 本地与 obsolete/ 都没有 0001
            self.assertEqual(len(pure_refs.check_supersede_unreconciled(ws, self.REL, self.DECL)), 1)

    def test_archived_but_not_marked_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            ws, adr = self._ws(d)
            obs = adr / "obsolete"; obs.mkdir()
            (obs / "0001-old.md").write_text("---\nStatus: Accepted\n---\n# ADR-0001\n", encoding="utf-8")
            out = pure_refs.check_supersede_unreconciled(ws, self.REL, self.DECL)
            self.assertEqual(len(out), 1)
            self.assertIn("未标 Status: Superseded", out[0][1])

    def test_archived_and_marked_passes(self):
        with tempfile.TemporaryDirectory() as d:
            ws, adr = self._ws(d)
            obs = adr / "obsolete"; obs.mkdir()
            (obs / "0001-old.md").write_text(
                "---\nStatus: Superseded\nsuperseded_by: ADR-0002\n---\n# ADR-0001\n", encoding="utf-8")
            self.assertEqual(pure_refs.check_supersede_unreconciled(ws, self.REL, self.DECL), [])

    def test_no_declaration_passes(self):
        with tempfile.TemporaryDirectory() as d:
            ws, _adr = self._ws(d)
            self.assertEqual(
                pure_refs.check_supersede_unreconciled(ws, "docs/adr/0002-x.md", "# ADR-0002\n"), [])

    def test_non_adr_and_obsolete_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            ws, _adr = self._ws(d)
            self.assertEqual(pure_refs.check_supersede_unreconciled(ws, "docs/guides/x.md", self.DECL), [])
            self.assertEqual(
                pure_refs.check_supersede_unreconciled(ws, "docs/adr/obsolete/0009-z.md", self.DECL), [])


class TestMarkdown(unittest.TestCase):
    def test_unclosed_fence(self):
        out = pure_refs.check_markdown_text("```python\ncode\n", "f.md")
        self.assertTrue(any(c == "MD_FENCE_UNCLOSED" for c, _ in out))

    def test_conflict_markers(self):
        out = pure_refs.check_markdown_text("a\n<<<<<<< HEAD\nb\n=======\nc\n>>>>>>> x\n", "f.md")
        self.assertEqual(sum(1 for c, _ in out if c == "MD_CONFLICT_MARKER"), 3)

    def test_setext_not_conflict(self):
        out = pure_refs.check_markdown_text("Title\n=======\n\nbody\n", "f.md")
        self.assertFalse(any(c == "MD_CONFLICT_MARKER" for c, _ in out))

    def test_trailing_ws_and_newline(self):
        out = pure_refs.check_markdown_text("line   \nno-newline", "f.md")
        codes = [c for c, _ in out]
        self.assertIn("MD_TRAILING_WS", codes)
        self.assertIn("MD_NO_FINAL_NEWLINE", codes)

    def test_bytes_encoding(self):
        out = pure_refs.check_markdown_bytes("ok\n".encode(), "f.md")
        self.assertEqual(out, [])
        out = pure_refs.check_markdown_bytes(b"\xff\xfe bad", "f.md")
        self.assertTrue(any(c == "MD_ENCODING" for c, _ in out))
        out = pure_refs.check_markdown_bytes(b"a\r\nb\r\n", "f.md")
        self.assertTrue(any(c == "MD_CRLF" for c, _ in out))


class TestOrphans(unittest.TestCase):
    def test_orphan_spec(self):
        with tempfile.TemporaryDirectory() as d:
            ws = _ws(d, specs=[("eng/spec.md", "# spec\n")])
            out = pure_refs.find_orphan_specs(ws, ["docs/specs/other/spec.md"])
            self.assertEqual(len(out), 1)
            out = pure_refs.find_orphan_specs(ws, ["docs/specs/eng/spec.md"])
            self.assertEqual(out, [])

    def test_orphan_test(self):
        with tempfile.TemporaryDirectory() as d:
            ws = _ws(d,
                     specs=[("eng/spec.md", "run `tests/unit/test_a.py`\n")],
                     tests=[("unit/test_a.py", "def test_a(): pass\n"),
                            ("unit/test_lonely.py", "def test_x(): pass\n")])
            out = pure_refs.find_orphan_tests(ws)
            self.assertEqual([m for _c, m in out], ["tests/unit/test_lonely.py: no Verification Matrix references this test file"])

    def test_orphan_adr(self):
        with tempfile.TemporaryDirectory() as d:
            ws = _ws(d, adrs=[("0001-a.md", "# ADR-0001\n"), ("0099-z.md", "# ADR-0099\n")])
            out = pure_refs.find_orphan_adrs(ws)
            self.assertEqual(len(out), 1)
            self.assertIn("0099", out[0][1])


class TestReportPointer(unittest.TestCase):
    def test_missing_report(self):
        with tempfile.TemporaryDirectory() as d:
            ws = _ws(d, tasks=[("t.md", "---\nstatus: idea\nreport: docs/reviews/gone.md\n---\n# t\n")])
            out = pure_refs.check_report_pointer(ws, "docs/tasks/t.md",
                                                 (ws / "docs" / "tasks" / "t.md").read_text(encoding="utf-8"))
            self.assertEqual(len(out), 1)

    def test_existing_report_ok(self):
        with tempfile.TemporaryDirectory() as d:
            ws = _ws(d, tasks=[("t.md", "---\nstatus: idea\nreport: docs/reviews/r.md\n---\n# t\n")])
            (ws / "docs" / "reviews").mkdir(parents=True)
            (ws / "docs" / "reviews" / "r.md").write_text("# r\n", encoding="utf-8")
            out = pure_refs.check_report_pointer(ws, "docs/tasks/t.md",
                                                 (ws / "docs" / "tasks" / "t.md").read_text(encoding="utf-8"))
            self.assertEqual(out, [])


if __name__ == "__main__":
    unittest.main()
