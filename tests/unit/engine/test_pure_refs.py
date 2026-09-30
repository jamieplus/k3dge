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
            "docs/tasks/2026-09-16-fix-x.done.md",
            "---\nstatus: idea\n---\n# t\n\n## 结案\n- 落地于 abc\n")   # 隔离：只测状态↔文件名
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0][0], "TASK_STATUS_MISMATCH")

    def test_consistent_ok(self):
        out = pure_refs.check_task_consistency(
            "docs/tasks/2026-09-16-fix-x.done.md",
            "---\nstatus: done\n---\n# t\n\n## 结案\n- 落地于 abc\n")
        self.assertEqual(out, [])

    def test_milestone_mismatch(self):
        out = pure_refs.check_task_consistency(
            "docs/tasks/2026-09-16-fix-x.done.md",
            "---\nstatus: done\nmilestone: M11\n---\n# t\n")
        codes = [c for c, _ in out]
        self.assertIn("TASK_MILESTONE_MISMATCH", codes)

    def test_non_task_skipped(self):
        self.assertEqual(pure_refs.check_task_consistency("docs/guides/x.md", "---\nstatus: done\n---\n"), [])


class TestTaskBodyMetaRedundant(unittest.TestCase):
    """双源对照：frontmatter ↔ body（权威源 vs 人类可读副本）。"""

    REL = "docs/tasks/2026-09-16-M10-fix-x.done.md"

    def _task(self, fm_lines, body_lines):
        fm = "---\n" + "\n".join(fm_lines) + "\n---\n"
        body = "\n".join(f"- **{k}**: {v}" for k, v in body_lines)
        return f"{fm}\n# 标题\n\n{body}\n"

    def test_frontmatter_only_passes(self):
        """唯一源形状：只有 frontmatter，正文零复写 ⇒ 绿。"""
        text = self._task(
            ["status: done", "milestone: M10", "priority: P2", "date: 2026-09-16"], [])
        self.assertEqual(pure_refs.check_task_body_meta_redundant(self.REL, text), [])

    def test_body_copy_detected_even_when_agreed(self):
        """关键语义变化：**一致也报**——副本本身就是病（只能漂移），不是比对新旧值。"""
        text = self._task(
            ["status: done", "priority: P2", "date: 2026-09-16"],
            [("Status", "done"), ("Priority", "P2"), ("Date", "2026-09-16")],
        )
        out = pure_refs.check_task_body_meta_redundant(self.REL, text)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0][0], "TASK_BODY_META_REDUNDANT")
        for k in ("Status", "Priority", "Date"):
            self.assertIn(k, out[0][1])

    def test_divergent_copy_still_detected(self):
        text = self._task(["status: done"], [("Status", "idea")])
        out = pure_refs.check_task_body_meta_redundant(self.REL, text)
        self.assertEqual(out[0][0], "TASK_BODY_META_REDUNDANT")

    def test_summary_bullet_is_not_metadata(self):
        """`- **可检索摘要**:` 无 frontmatter 对应字段 ⇒ 不是复写，不得误伤。"""
        text = self._task(["status: idea"], [("可检索摘要", "一句话")])
        self.assertEqual(pure_refs.check_task_body_meta_redundant(self.REL, text), [])

    def test_legacy_without_frontmatter_skipped(self):
        """无 frontmatter 的遗留票：body 即唯一源，不得误伤。"""
        text = "# 遗留\n\n- **Status**: idea\n- **Milestone**: M10\n"
        self.assertEqual(pure_refs.check_task_body_meta_redundant(self.REL, text), [])

    def test_non_task_skipped(self):
        self.assertEqual(
            pure_refs.check_task_body_meta_redundant(
                "docs/guides/x.md", "---\nstatus: done\n---\n\n- **Status**: done\n"), [])

    def test_wired_into_check_task_consistency(self):
        """接线：check_task_consistency 必须含冗余检出（否则 pre-commit 不会跑）。"""
        text = self._task(["status: done"], [("Status", "idea")])
        codes = [c for c, _ in pure_refs.check_task_consistency(self.REL, text)]
        self.assertIn("TASK_BODY_META_REDUNDANT", codes)


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
            # 收成事实：第二项就是**路径**（文案归 gate_facts 声明表渲染，不再在检查器里拼）
            self.assertEqual(out, [("ORPHAN_TEST", "tests/unit/test_lonely.py")])

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


class TestMilestoneTokenCase(unittest.TestCase):
    def test_lowercase_filename_token_matches_uppercase_id(self) -> None:
        # `_filename_milestone` 带 IGNORECASE；这里严格比大小写会漏归档本里程碑报告（ocr-304）
        self.assertTrue(pure_refs.has_milestone_token("2026-09-16-m10-fix.md", "M10"))
        self.assertTrue(pure_refs.has_milestone_token("2026-09-16-M10-fix.md", "m10"))
        self.assertFalse(pure_refs.has_milestone_token("2026-08-23-M10-align.md", "M1"))


class TestPointerAndClosureShape(unittest.TestCase):
    """report 指针、排查去向、正文复写与结案段的边界（ocr-294..299）。"""

    REL = "docs/tasks/2026-09-16-M10-feat-x.md"

    def _ws_with_report(self, report: str) -> Path:
        import tempfile

        ws = Path(tempfile.mkdtemp())
        (ws / "docs" / "reviews").mkdir(parents=True)
        (ws / "docs" / "reviews" / "r.md").write_text("# r\n", encoding="utf-8")
        self._report = report
        return ws

    def test_capitalized_report_key_is_honored(self) -> None:
        ws = self._ws_with_report("docs/reviews/r.md")
        text = f"---\nReport: {self._report}\n---\n\n# X\n"
        self.assertEqual(pure_refs.check_report_pointer(ws, self.REL, text), [])

    def test_report_pointer_must_stay_in_workspace(self) -> None:
        ws = self._ws_with_report("/etc/hosts")
        text = f"---\nreport: {self._report}\n---\n\n# X\n"
        out = pure_refs.check_report_pointer(ws, self.REL, text)
        self.assertEqual([c for c, _ in out], ["DANGLING_REPORT_REF"])
        ws2 = self._ws_with_report("../elsewhere/x.md")
        self.assertTrue(pure_refs.check_report_pointer(
            ws2, self.REL, f"---\nreport: ../elsewhere/x.md\n---\n"))

    def test_body_meta_gate_ignores_fence_samples(self) -> None:
        text = "# X\n\n反例长这样：\n\n```md\n- **Status**: done\n```\n"
        self.assertEqual(pure_refs.check_task_body_meta_redundant(self.REL, text), [])

    def test_screen_ack_target_must_be_in_repo(self) -> None:
        import tempfile

        ws = Path(tempfile.mkdtemp())
        (ws / "docs").mkdir()
        (ws / "docs" / "a.md").write_text("x", encoding="utf-8")
        outside = Path(tempfile.mkdtemp()) / "elsewhere.md"
        outside.write_text("x", encoding="utf-8")
        self.assertTrue(pure_refs.screen_target_exists(ws, "docs/a.md"))
        self.assertFalse(pure_refs.screen_target_exists(ws, str(outside)))
        self.assertFalse(pure_refs.screen_target_exists(ws, "../%s" % outside.name))

    def test_retired_ledger_warns_when_marker_drifted(self) -> None:
        import contextlib
        import io
        import tempfile

        ws = Path(tempfile.mkdtemp())
        led = ws / "docs" / "adr" / "obsolete"
        led.mkdir(parents=True)
        (led / "README.md").write_text(
            "# 退役\n\n| 0007 | was | merged | dest |\n\n", encoding="utf-8")   # 标题漂了
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(pure_refs.retired_adr_numbers(ws), {})
        self.assertIn("WARN", err.getvalue())

    def test_closure_section_scoped_to_its_own_block(self) -> None:
        rel = "docs/tasks/2026-09-16-x.done.md"
        # 模板留白的空 `## 进度` + 真写内容的 `## 结案` ⇒ 必须过（旧实现在第一个命中就返回）
        good = "# X\n\n## 进度\n\n## 结案\n\n- 落地了\n\n## 其它\n\n内容\n"
        self.assertEqual(pure_refs.check_task_closure_record(rel, good), [])
        # 结案段空、后面还有别的段 ⇒ 必须红（旧实现取"全文剩余"判成有内容）
        bad = "# X\n\n## 结案\n\n## 其它\n\n内容\n"
        out = pure_refs.check_task_closure_record(rel, bad)
        self.assertEqual([c for c, _ in out], ["TASK_CLOSURE_MISSING"])
        self.assertIn("空的", out[0][1])




class TestRepoTaskSingleSource(unittest.TestCase):
    """自举：本仓顶层票一律不得复写 frontmatter 元数据（存量已迁移，防回潮）。

    schema gate 只看 staged 文件，存量漂移它看不见 ⇒ 用自举测试兜住全仓。
    """

    def test_no_body_meta_in_repo_tasks(self):
        root = REPO / "docs" / "tasks"
        if not root.is_dir():
            self.skipTest("no tasks dir")
        offenders = []
        for p in sorted(root.glob("*.md")):
            if p.name in ("README.md", "AUTHORING.md", "_template.md"):
                continue
            rel = f"docs/tasks/{p.name}"
            for code, msg in pure_refs.check_task_body_meta_redundant(
                    rel, p.read_text(encoding="utf-8")):
                if code == "TASK_BODY_META_REDUNDANT":
                    offenders.append(msg)
        self.assertEqual(offenders, [])


class TestNewDocScreening(unittest.TestCase):
    """新建受管文档的首次排查闸（阻断一次；回执后放行）。

    判定权在 agent（进程判不了语义覆盖）；闸只负责把排查送到动手那一刻。
    """

    def test_subjective_new_doc_is_screenable(self):
        for rel in ("docs/adr/0027-x.md", "docs/memo/2026-09-19-y.md",
                    "docs/guides/g.md", "docs/architecture/a.md",
                    "docs/protocols/p.md", "docs/incidents/INC-20260919-x.md"):
            self.assertTrue(pure_refs.is_screenable_new_doc(rel), rel)

    def test_deterministic_and_aux_are_not(self):
        """确定性流程生成的文档有权威生成源，不存在"值不值得建"⇒ 不排查。"""
        for rel in ("docs/generated/api.md", "docs/specs/engine/spec.md",
                    "docs/tasks/2026-09-19-M10-fix-x.md", "docs/reviews/2026-09-19-M10-audit.md",
                    "docs/adr/README.md", "docs/adr/AUTHORING.md", "docs/adr/_template.md",
                    "docs/memo/archive/2026-01-01-old.md", "src/k3dge/x.py", "README.md"):
            self.assertFalse(pure_refs.is_screenable_new_doc(rel), rel)

    def test_blocks_until_acked(self):
        from k3dge.engine import gate_facts

        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            rel = "docs/memo/2026-09-19-y.md"
            out = pure_refs.find_unscreened_new_docs(ws, [rel])
            self.assertEqual(out, [("DOC_NEW_UNSCREENED", rel)])   # 只产 code + 事实，不产文案

            # 文案由声明面渲染（ADR-0026 §2.2：fact + 成对 options，不出疑问句）
            text = gate_facts.render("DOC_NEW_UNSCREENED", {"path": out[0][1]})
            self.assertIn("fact:", text)
            self.assertGreaterEqual(text.count("option:"), 2)
            self.assertNotIn("？", text)
            self.assertIn(f"k3dge doc screen {rel}", text)
            self.assertEqual(gate_facts.severity("DOC_NEW_UNSCREENED"), "block")

            pure_refs.record_screen_ack(ws, rel)
            self.assertEqual(pure_refs.find_unscreened_new_docs(ws, [rel]), [])

    def test_ack_records_conclusion_without_judging(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            rel = "docs/adr/0027-x.md"
            ack = pure_refs.record_screen_ack(ws, rel, into="docs/adr/0005-y.md")
            text = ack.read_text(encoding="utf-8")
            self.assertIn("merged-into docs/adr/0005-y.md", text)
            self.assertIn(f"path: {rel}", text)
            # 回执在 .protocol-ack/（ephemeral，已 gitignore），不污染受管文档
            self.assertIn(".protocol-ack/doc-screen", str(ack))

    def test_mixed_batch_only_flags_screenable(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            added = ["docs/generated/api.md", "docs/adr/0027-x.md", "src/x.py"]
            out = pure_refs.find_unscreened_new_docs(ws, added)
            self.assertEqual(len(out), 1)
            self.assertIn("docs/adr/0027-x.md", out[0][1])


class TestAdrNumberRetirement(unittest.TestCase):
    """编号退役账本：`Numbers are never reused` 的机检半边（票 adr_number_cutline）。

    病灶：AUTHORING 声称 `ADR_FILENAME_MISMATCH` 管复用，实际它只查文件名号↔H1 号一致；
    加上"被并者物理删除"+"本目录最大号+1"两条规则相打架 ⇒ 实测 19 个号被删过、6 个被发出两次。
    """

    def _ws_with_ledger(self, td):
        ws = Path(td)
        (ws / "docs" / "adr" / "obsolete").mkdir(parents=True)
        (ws / "docs" / "adr" / "0005-x.md").write_text("# ADR-0005: x\n", encoding="utf-8")
        (ws / "docs" / "adr" / "obsolete" / "README.md").write_text(
            "# Obsolete ADRs\n\n## 永久退役号（账本）\n\n"
            "| 号 | 曾是 | 退役方式 | 去向 | 删除 commit |\n| --- | --- | --- | --- | --- |\n"
            "| 0020 | harness-responsibility-split | 合并 | ADR-0005 §2.7 | `0fc2d3a` |\n\n"
            "### 曾被复用的号（存量不追，仅记账）\n\n"
            "| 号 | 旧占用 | 现役 |\n| --- | --- | --- |\n| 0008 | sibling | triggers |\n",
            encoding="utf-8")
        return ws

    def test_ledger_reads_only_the_retired_section(self):
        with tempfile.TemporaryDirectory() as td:
            ws = self._ws_with_ledger(td)
            led = pure_refs.retired_adr_numbers(ws)
            self.assertEqual(sorted(led), ["0020"])          # "曾被复用"表的 0008 不得混进来
            self.assertIn("harness-responsibility-split", led["0020"]["was"])
            self.assertIn("ADR-0005", led["0020"]["dest"])

    def test_reuse_of_retired_number_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            ws = self._ws_with_ledger(td)
            out = pure_refs.check_adr_number_reuse(ws, "docs/adr/0020-new-idea.md")
            self.assertEqual([c for c, _ in out], ["ADR_NUMBER_REUSE"])
            self.assertIn("ADR-0005 §2.7", out[0][1])       # 给去向，不只说"不行"

    def test_safe_number_passes(self):
        with tempfile.TemporaryDirectory() as td:
            ws = self._ws_with_ledger(td)
            self.assertEqual(pure_refs.check_adr_number_reuse(ws, "docs/adr/0021-y.md"), [])

    def test_live_number_not_flagged_as_reuse(self):
        """存量不追：baseline 前被复用且现役的号不得被本码误伤。"""
        with tempfile.TemporaryDirectory() as td:
            ws = self._ws_with_ledger(td)
            (ws / "docs" / "adr" / "0008-live.md").write_text("# ADR-0008: live\n", encoding="utf-8")
            self.assertEqual(pure_refs.check_adr_number_reuse(ws, "docs/adr/0008-live.md"), [])

    def test_obsolete_file_also_retires_the_number(self):
        """baseline 之后的退役是 obsolete/ 里的真文件（不进账本表），同样拦住复用。"""
        with tempfile.TemporaryDirectory() as td:
            ws = self._ws_with_ledger(td)
            (ws / "docs" / "adr" / "obsolete" / "0007-old.md").write_text("# ADR-0007\n", encoding="utf-8")
            out = pure_refs.check_adr_number_reuse(ws, "docs/adr/0007-new.md")
            self.assertEqual([c for c, _ in out], ["ADR_NUMBER_REUSE"])

    def test_ref_to_retired_number_gives_destination(self):
        with tempfile.TemporaryDirectory() as td:
            ws = self._ws_with_ledger(td)
            out = pure_refs.check_adr_ref_retired(ws, "docs/memo/x.md", "见 ADR-0020 与 ADR-0005")
            self.assertEqual([c for c, _ in out], ["ADR_REF_RETIRED"])
            self.assertIn("ADR-0005 §2.7", out[0][1])

    def test_reviews_and_archive_are_history_not_violations(self):
        """append-only 的历史记录引用"当时那条 ADR"，改写＝篡改事实 ⇒ 不报。"""
        with tempfile.TemporaryDirectory() as td:
            ws = self._ws_with_ledger(td)
            for rel in ("docs/reviews/2026-09-10-x.md", "docs/tasks/archive/M7/y.md"):
                self.assertEqual(pure_refs.check_adr_ref_retired(ws, rel, "见 ADR-0020"), [], rel)

    def test_repo_ledger_is_loaded_and_consistent(self):
        """自举：本仓账本 13 个退役号，且现役 14 条无一占用退役号。"""
        led = pure_refs.retired_adr_numbers(REPO)
        self.assertEqual(len(led), 13)
        self.assertEqual(sorted(led), ["0002", "0003", "0007", "0011", "0013", "0014",
                                       "0015", "0016", "0019", "0020", "0021", "0024", "0027"])
        live = pure_refs._live_adr_numbers(REPO)
        self.assertEqual(live & set(led), set())            # 退役号没有现役文件
        for name in sorted((REPO / "docs" / "adr").glob("0*.md")):
            self.assertEqual(
                pure_refs.check_adr_number_reuse(REPO, f"docs/adr/{name.name}"), [], name.name)

    def test_this_repo_has_no_number_hole(self):
        """1..最大号每个号都有现役文件或退役墓碑。跳号（0028 那种）在这里会红。"""
        self.assertEqual(pure_refs.check_adr_number_holes(REPO), [])

    def test_skipped_number_is_a_hole(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            adr = ws / "docs" / "adr"
            adr.mkdir(parents=True)
            (adr / "0001-a.md").write_text("# ADR-0001\n", encoding="utf-8")
            (adr / "0003-c.md").write_text("# ADR-0003\n", encoding="utf-8")
            out = pure_refs.check_adr_number_holes(ws)
            self.assertEqual([c for c, _, _f in out], ["ADR_NUMBER_HOLE"])
            self.assertIn("0002", out[0][1])
            self.assertIn("0003-c.md", out[0][1])
            self.assertEqual(out[0][2], {"path": "docs/adr/0003-c.md"})   # 锚点走 facts，不靠解析文案

    def test_ledger_fills_the_hole(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            adr = ws / "docs" / "adr"
            (adr / "obsolete").mkdir(parents=True)
            (adr / "0001-a.md").write_text("# ADR-0001\n", encoding="utf-8")
            (adr / "0003-c.md").write_text("# ADR-0003\n", encoding="utf-8")
            (adr / "obsolete" / "README.md").write_text(
                "## 永久退役号（账本）\n\n"
                "| 号 | 曾是 | 退役方式 | 去向 | 删除 commit |\n| --- | --- | --- | --- | --- |\n"
                "| 0002 | old | 合并 | ADR-0001 | `abc` |\n\n"
                "### 曾被复用的号（存量不追，仅记账）\n",
                encoding="utf-8")
            self.assertEqual(pure_refs.check_adr_number_holes(ws), [])


class TestTaskClosureRecord(unittest.TestCase):
    """done 票必须留结案记录（防"票里说待办、实际已做"的漂移）。

    实测来源：三张票的 blocking 与验收段全漂了，全靠人工扫才发现；根因之一是关票时
    **没有任何地方要求写下落地痕迹**（33 张 done 里只有 2 张有）。
    """

    REL = "docs/tasks/2026-09-16-fix-x.done.md"

    def _t(self, body: str) -> str:
        return f"---\nstatus: done\n---\n# t\n\n{body}"

    def test_missing_section_blocks(self):
        out = pure_refs.check_task_closure_record(self.REL, self._t("正文"))
        self.assertEqual([c for c, _ in out], ["TASK_CLOSURE_MISSING"])

    def test_empty_section_blocks(self):
        out = pure_refs.check_task_closure_record(self.REL, self._t("## 结案\n\n"))
        self.assertEqual([c for c, _ in out], ["TASK_CLOSURE_MISSING"])
        self.assertIn("空的", out[0][1])

    def test_any_of_the_closed_set_passes(self):
        for heading in ("## 结案", "## 落地", "## 关闭理由", "## 收尾", "## 回填", "## 进度"):
            self.assertEqual(
                pure_refs.check_task_closure_record(self.REL, self._t(f"{heading}\n- 有内容\n")), [],
                heading)

    def test_heading_with_qualifier_passes(self):
        """标题可带限定词（自然写法）：`## 落地（2026-09-19，①-⑥ 全部执行）`。"""
        self.assertEqual(
            pure_refs.check_task_closure_record(self.REL, self._t("## 落地（2026-09-19）\n- 内容\n")), [])

    def test_open_ticket_not_checked(self):
        self.assertEqual(
            pure_refs.check_task_closure_record("docs/tasks/2026-09-16-fix-x.md",
                                                "---\nstatus: idea\n---\n# t\n"), [])

    def test_repo_done_tickets_all_have_a_record(self):
        """自举：本仓每张 done 票都有结案记录（回填后应恒成立）。"""
        offenders = []
        for p in sorted(REPO.glob("docs/tasks/*.done.md")):
            rel = f"docs/tasks/{p.name}"
            for code, msg in pure_refs.check_task_closure_record(rel, p.read_text(encoding="utf-8")):
                offenders.append(msg)
        self.assertEqual(offenders, [])


class TestRetiredAdrDest(unittest.TestCase):
    """退役 ADR 必须写清去向（票 adr_merge_retirement_gap）。

    病灶：`reconcile_supersedes` 只自动化 `Supersedes:` 与 `Rejected`；**合并没有自动化**
    （13 个永久退役号里 12 个是合并），而 `merged-into` 此前全仓只有读、没有写方、没有闸
    ⇒ 忘写去向时退役卡片显示 retired 但去向空，读者仍找不到"这条去哪了"。
    """

    REL = "docs/adr/obsolete/0042-old-decisions.md"

    def _fm(self, body: str) -> str:
        return body

    def test_missing_dest_blocks(self):
        out = pure_refs.check_retired_adr_dest(self.REL, "---\nStatus: Superseded\n---\n# ADR-0042\n")
        self.assertEqual([c for c, _ in out], ["ADR_RETIRED_NO_DEST"])
        self.assertIn("merged-into", out[0][1])          # 提示里给出合法形态

    def test_three_legal_forms_pass(self):
        for body in ("---\nStatus: Superseded\nmerged-into: ADR-0005 §2.7\n---\n# ADR-0042\n",
                     "---\nStatus: Superseded\nsuperseded_by: ADR-0005\n---\n# ADR-0042\n",
                     "---\nStatus: Rejected\n---\n# ADR-0042\n"):
            self.assertEqual(pure_refs.check_retired_adr_dest(self.REL, body), [], body)

    def test_empty_value_does_not_count(self):
        """写了键但值为空 ⇒ 仍算没写（不许空壳过关）。"""
        out = pure_refs.check_retired_adr_dest(self.REL, "---\nmerged-into:\n---\n# ADR-0042\n")
        self.assertEqual([c for c, _ in out], ["ADR_RETIRED_NO_DEST"])

    def test_ledger_and_non_obsolete_skipped(self):
        bad = "---\nStatus: Superseded\n---\n# ADR-0042\n"
        self.assertEqual(pure_refs.check_retired_adr_dest("docs/adr/obsolete/README.md", bad), [])
        self.assertEqual(pure_refs.check_retired_adr_dest("docs/adr/obsolete/_template.md", bad), [])
        self.assertEqual(pure_refs.check_retired_adr_dest("docs/adr/0042-x.md", bad), [])

    def test_repo_obsolete_has_no_offender(self):
        """自举：本仓现状（obsolete/ 只有 README）⇒ 绿，不误伤。"""
        offenders = []
        for p in sorted((REPO / "docs" / "adr" / "obsolete").glob("*.md")):
            rel = f"docs/adr/obsolete/{p.name}"
            offenders += [m for _c, m in pure_refs.check_retired_adr_dest(rel, p.read_text(encoding="utf-8"))]
        self.assertEqual(offenders, [])


class TestRetiredDestRepoWideWiring(unittest.TestCase):
    """接线证明：`obsolete/` 默认不在现行视图里（iter_managed_files 排除退役面），
    所以 `k3dge check` 必须**显式扫**它，否则这条闸在仓库级永远不跑。"""

    def test_validate_docs_reports_obsolete_without_dest(self):
        import tempfile

        from k3dge.engine.doc_catalog import validate_docs

        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            obs = ws / "docs" / "adr" / "obsolete"
            obs.mkdir(parents=True)
            (obs / "0042-old.md").write_text("---\nStatus: Superseded\n---\n# ADR-0042\n", encoding="utf-8")
            codes = [v.rule_id for v in validate_docs(ws, types=["adr"])]
            self.assertIn("ADR_RETIRED_NO_DEST", codes)
            # 补上去向 ⇒ 绿
            (obs / "0042-old.md").write_text(
                "---\nStatus: Superseded\nmerged-into: ADR-0005 §2.7\n---\n# ADR-0042\n", encoding="utf-8")
            codes2 = [v.rule_id for v in validate_docs(ws, types=["adr"])]
            self.assertNotIn("ADR_RETIRED_NO_DEST", codes2)


class TestScreenTargetExists(unittest.TestCase):
    """回执声称"并入 X"时 X 必须存在（C 线残渣：此前不校验）。"""

    def test_missing_target_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            self.assertFalse(pure_refs.screen_target_exists(ws, "docs/adr/9999-nope.md"))
            self.assertFalse(pure_refs.screen_target_exists(ws, ""))
            self.assertFalse(pure_refs.screen_target_exists(ws, None))   # type: ignore[arg-type]

    def test_existing_target_passes(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            (ws / "docs" / "adr").mkdir(parents=True)
            (ws / "docs" / "adr" / "0005-x.md").write_text("# ADR-0005\n", encoding="utf-8")
            self.assertTrue(pure_refs.screen_target_exists(ws, "docs/adr/0005-x.md"))

    def test_directory_is_not_a_target(self):
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            (ws / "docs" / "adr").mkdir(parents=True)
            self.assertFalse(pure_refs.screen_target_exists(ws, "docs/adr"))


class TestIncidentIdSingleSource(unittest.TestCase):
    """incidents 身份唯一源＝文件名（票 incident_id_single_source）。

    实测病灶：11 份里 10 份的 `id:` 与文件名一致（纯副本），1 份**不一致**——
    `INC-20260826-REG-m3-task-truncate.md` 的 `id: INC-20260826-REG-01`，且没有任何消费者
    读它（`_card_id` 用 `path.stem`，schema 无 id 规则）⇒ 漂了无人知。
    """

    REL = "docs/incidents/INC-20260919-REG-x.md"

    def test_redundant_id_blocks(self):
        out = pure_refs.check_incident_id_redundant(
            self.REL, "---\nid: INC-20260919-REG-x\ntype: REG\n---\n# Incident: x\n")
        self.assertEqual([c for c, _ in out], ["INCIDENT_ID_REDUNDANT"])

    def test_without_id_passes(self):
        self.assertEqual(pure_refs.check_incident_id_redundant(
            self.REL, "---\ntype: REG\nseverity: P2\nstatus: open\n---\n# Incident: x\n"), [])

    def test_aux_and_non_incident_skipped(self):
        bad = "---\nid: whatever\n---\n# x\n"
        self.assertEqual(pure_refs.check_incident_id_redundant("docs/incidents/README.md", bad), [])
        self.assertEqual(pure_refs.check_incident_id_redundant("docs/incidents/AUTHORING.md", bad), [])
        self.assertEqual(pure_refs.check_incident_id_redundant("docs/tasks/x.md", bad), [])

    def test_repo_has_single_source(self):
        """自举：本仓 incident 全部无 `id`（迁移后应恒成立）。"""
        offenders = []
        for p in sorted((REPO / "docs" / "incidents").glob("INC-*.md")):
            rel = f"docs/incidents/{p.name}"
            offenders += [m for _c, m in pure_refs.check_incident_id_redundant(rel, p.read_text(encoding="utf-8"))]
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
