"""pre-commit 三层闸的接线测试（2026-09-21 起实现归 `k3dge.engine.doc_gate`，脚本只是薄壳）。"""
import unittest
from pathlib import Path

from k3dge.engine import doc_gate as hook

ROOT = Path(__file__).resolve().parents[3]

hook.set_workspace(ROOT)

# 唯一源形状：元数据只在 frontmatter，正文不复写（TASK_BODY_META_REDUNDANT）
TASK_GOOD = (
    "---\nstatus: idea\npriority: P2\ndate: 2026-09-16\n---\n\n"
    "# t\n\n- **可检索摘要**: 一句话\n"
)


class TestSchemaGateWiring(unittest.TestCase):
    def _run(self, files, blobs, orphan_warns=()):
        from k3dge.engine import gate_facts

        orig_staged = hook._staged_bytes
        orig_orphans = hook._orphan_warnings
        self._consulted: list = []

        def _staged(rel):
            # ocr2-541：未知路径不得静默回 None（`_run_schema_gate` 把 None 读成
            # "跳过这个文件"）——否则 blobs 键打错 / doc_files 过滤漂了 / 改读工作树，
            # 都能让"干净通过"变空转。这里大声失败并记录真被问过的路径。
            if rel not in blobs:
                raise AssertionError(f"gate 读了未知 staged 路径（blobs 缺键/过滤漂了）：{rel}")
            self._consulted.append(rel)
            return blobs[rel]

        hook._staged_bytes = _staged
        hook._orphan_warnings = lambda _refs: list(orphan_warns)
        try:
            pure_schema, pure_refs = hook._load_pure()
            self.assertIsNotNone(pure_schema)
            # 档位查声明面（与 main() 同口径）
            return hook.run_schema_gate(files, pure_schema, pure_refs, gate_facts)
        finally:
            hook._staged_bytes = orig_staged
            hook._orphan_warnings = orig_orphans

    def test_clean_doc_passes(self):
        errs, warns = self._run(
            ["docs/tasks/2026-09-16-fix-x.md"],
            {"docs/tasks/2026-09-16-fix-x.md": TASK_GOOD.encode()},
        )
        # ocr2-543：先证 schema 真被发现（否则 `schema is None ⇒ 跳过 check_file`，
        # "干净"可能是"没查"），再证该文件真被读过 staged bytes。
        ps = hook._load_pure()[0]
        schema, _err = hook._load_type_schema("tasks", ps)
        self.assertIsNotNone(schema, "docs/tasks/.schema.json 未发现 ⇒ check_file 被跳过")
        self.assertIn("docs/tasks/2026-09-16-fix-x.md", self._consulted)
        self.assertEqual(errs, [])
        self.assertEqual(warns, [])

    def test_bad_filename_blocks(self):
        errs, _warns = self._run(
            ["docs/memo/nodate.md"],
            {"docs/memo/nodate.md": b"# note\n"},
        )
        self.assertTrue(any("filename does not match" in e for e in errs), errs)

    def test_bad_frontmatter_blocks(self):
        errs, _warns = self._run(
            ["docs/adr/0001-x.md"],
            {"docs/adr/0001-x.md": b"---\nStatus: Bogus\n---\n# ADR-0001: x\n"},
        )
        self.assertTrue(any("Status=" in e for e in errs), errs)

    def test_number_hole_blocks_the_commit(self):
        """提交硬闸：号池有空洞时，staged 的 ADR 过不了 schema gate。

        ocr2-544：用 `set_workspace`（不是直接改 `hook.WS`）并在**切走之前**载入纯模块，
        避免 `_load_pure()` 把临时仓的 `src` 塞进 `sys.path` 并留下永久缓存项。
        """
        import tempfile

        from k3dge.engine import gate_facts

        pure_schema, pure_refs = hook._load_pure()      # WS 仍是 ROOT：从真树载入
        self.assertIsNotNone(pure_schema)
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            adr = ws / "docs" / "adr"
            adr.mkdir(parents=True)
            (adr / "0001-a.md").write_text("# ADR-0001: a\n", encoding="utf-8")
            (adr / "0003-c.md").write_text("# ADR-0003: c\n", encoding="utf-8")
            prev = hook.WS
            self.addCleanup(hook.set_workspace, prev)
            hook.set_workspace(ws)
            orig_staged = hook._staged_bytes
            hook._staged_bytes = lambda rel: b"# ADR-0003: c\n" if rel == "docs/adr/0003-c.md" else None
            try:
                errs, _warns = hook.run_schema_gate(
                    ["docs/adr/0003-c.md"], pure_schema, pure_refs, gate_facts)
            finally:
                hook._staged_bytes = orig_staged
        self.assertTrue(any("ADR_NUMBER_HOLE" in e for e in errs), errs)
        self.assertTrue(any("0002" in e for e in errs), errs)

    def test_dangling_adr_blocks(self):
        errs, _warns = self._run(
            ["docs/tasks/2026-09-16-fix-x.md"],
            {"docs/tasks/2026-09-16-fix-x.md": (TASK_GOOD + "\nsee ADR-0099\n").encode()},
        )
        self.assertTrue(any("DANGLING_ADR_REF" in e for e in errs), errs)

    def test_conflict_marker_blocks(self):
        errs, _warns = self._run(
            ["docs/tasks/2026-09-16-fix-x.md"],
            {"docs/tasks/2026-09-16-fix-x.md": (TASK_GOOD + "<<<<<<< HEAD\n").encode()},
        )
        self.assertTrue(any("MD_CONFLICT_MARKER" in e for e in errs), errs)

    def test_orphan_is_warn_only(self):
        from k3dge.engine.gate_facts import severity as gate_facts_severity

        errs, warns = self._run(
            ["docs/tasks/2026-09-16-fix-x.md"],
            {"docs/tasks/2026-09-16-fix-x.md": TASK_GOOD.encode()},
            orphan_warns=[("ORPHAN_TEST", "tests/unit/test_lonely.py: no matrix ref",
                           {"path": "tests/unit/test_lonely.py"})],
        )
        self.assertEqual(errs, [])
        self.assertEqual(len(warns), 1)
        # 档位来自声明（warn），文案来自声明面（fact + 成对 options），不是 hook 里拼的
        self.assertEqual(gate_facts_severity("ORPHAN_TEST"), "warn")
        self.assertIn("fact:", warns[0])
        self.assertGreaterEqual(warns[0].count("option:"), 2)

    def test_non_utf8_blocks(self):
        errs, _warns = self._run(
            ["docs/tasks/2026-09-16-fix-x.md"],
            {"docs/tasks/2026-09-16-fix-x.md": b"\xff\xfe bad"},
        )
        self.assertTrue(any("MD_ENCODING" in e for e in errs), errs)

    def test_pure_loads_without_venv(self):
        # the whole point: stdlib-only import from the src tree
        pure_schema, pure_refs = hook._load_pure()
        self.assertTrue(hasattr(pure_schema, "check_file"))
        self.assertTrue(hasattr(pure_refs, "check_dangling_adr"))




class TestScreenGateWiring(unittest.TestCase):
    """pre-commit 接线：新增受管文档未排查 ⇒ 阻断；回执后放行；工具坏不阻断。"""

    def _pure_refs(self):
        _ps, pr = hook._load_pure()
        self.assertIsNotNone(pr)
        return pr

    def test_added_and_acked_paths(self):
        import tempfile

        from k3dge.engine import gate_facts

        pr = self._pure_refs()
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            rel = "docs/memo/2026-09-19-y.md"
            orig = hook.WS
            hook.WS = ws
            try:
                out = hook.run_screen_gate([rel], pr, gate_facts)
                self.assertEqual([sev for sev, _ in out], ["block"])   # 档位查表，不写死
                self.assertIn("fact:", out[0][1])                       # 文案查表，不在 hook 里拼
                pr.record_screen_ack(ws, rel)
                self.assertEqual(hook.run_screen_gate([rel], pr, gate_facts), [])
                self.assertEqual(hook.run_screen_gate([], pr, gate_facts), [])
            finally:
                hook.WS = orig

    def test_without_declaration_falls_back_to_plain(self):
        """声明面不可用 ⇒ 回落 `[code] 事实`，绝不因为工具坏而放行或崩掉。"""
        import tempfile

        pr = self._pure_refs()
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            orig, hook.WS = hook.WS, ws
            try:
                res = hook.run_screen_gate(["docs/memo/2026-09-19-y.md"], pr, None)
                # 先断形状再索引（t-294）：回退路径哪天不出 finding，`[0]` 的 IndexError
                # 伪装成测试崩溃，把"兜底没接线"这个真信号丢在 traceback 里
                self.assertEqual(len(res), 1, res)
                sev, text = res[0]
                self.assertEqual(sev, "block")
                self.assertEqual(text, "[DOC_NEW_UNSCREENED] docs/memo/2026-09-19-y.md")
            finally:
                hook.WS = orig

    def test_broken_tool_does_not_block(self):
        class Boom:
            def find_unscreened_new_docs(self, *_a, **_k):
                raise RuntimeError("boom")

        self.assertEqual(hook.run_screen_gate(["docs/adr/0028-x.md"], Boom()), [])


class TestDeclaredFactsSelfCheck(unittest.TestCase):
    """声明面 ↔ 产出点：声明里的占位键必须被检查器喂到（2026-09-21 起 `facts_of` 有生产消费者）。"""

    def test_missing_facts_are_reported(self):
        from k3dge.engine import gate_facts

        missing = hook.missing_declared_facts("CONTRACT_DRIFT", {"path": "docs/specs/x.md"}, gate_facts)
        self.assertIn("expected_hash", missing)
        self.assertIn("actual_hash", missing)

    def test_complete_facts_report_nothing(self):
        from k3dge.engine import gate_facts

        facts = {"path": "x", "expected_hash": "a", "actual_hash": "b"}
        self.assertEqual(hook.missing_declared_facts("CONTRACT_DRIFT", facts, gate_facts), [])

    def test_undeclared_code_is_not_reported(self):
        from k3dge.engine import gate_facts

        self.assertEqual(hook.missing_declared_facts("SOMETHING_NEW", {}, gate_facts), [])

    def test_gate_feeds_missing_facts_into_the_channel(self):
        """ocr2-545：`_add()` 是 `missing_declared_facts` 的**唯一生产消费者**——
        直接调纯 helper 证明不了接线。这里让一个声明的 code 要求未被喂的键，
        触发它后断言 `hook._MISSING_FACTS` 收到 (code, key)。"""
        from unittest import mock

        from k3dge.engine import gate_facts

        ps, pr = hook._load_pure()
        self.assertIsNotNone(ps)
        files = ["docs/tasks/2026-09-16-fix-x.md"]
        blobs = {"docs/tasks/2026-09-16-fix-x.md": (TASK_GOOD + "\nsee ADR-0099\n").encode()}
        orig_staged = hook._staged_bytes
        hook._staged_bytes = lambda rel: blobs.get(rel)
        try:
            # 触发 DANGLING_ADR_REF，但让声明面要求两个从未提供的键
            with mock.patch.object(gate_facts, "facts_of",
                                   return_value=["expected_hash", "actual_hash"]):
                hook.run_schema_gate(files, ps, pr, gate_facts)
        finally:
            hook._staged_bytes = orig_staged
        self.assertIn(("DANGLING_ADR_REF", "expected_hash"), hook._MISSING_FACTS)
        self.assertIn(("DANGLING_ADR_REF", "actual_hash"), hook._MISSING_FACTS)


class TestSchemaGateFailClosedWithoutDeclaration(unittest.TestCase):
    """`gate_facts` 不可用时档位不得一律降为 warn（ocr2-246）。"""

    def test_block_code_stays_block(self) -> None:
        from k3dge.engine import doc_gate

        ps, pr = doc_gate._load_pure()
        self.assertIsNotNone(ps)
        files = ["docs/tasks/2026-09-16-fix-x.md"]
        blobs = {"docs/tasks/2026-09-16-fix-x.md": (TASK_GOOD + "<<<<<<< HEAD\n").encode()}
        orig = doc_gate._staged_bytes
        doc_gate._staged_bytes = lambda rel: blobs.get(rel)
        try:
            errs, warns = doc_gate.run_schema_gate(files, ps, pr, None)
        finally:
            doc_gate._staged_bytes = orig
        self.assertTrue(any("MD_CONFLICT_MARKER" in e for e in errs), (errs, warns))

    def test_warn_fallback_synced_with_declaration(self) -> None:
        from k3dge.engine import doc_gate, gate_facts

        declared = {c for c, d in gate_facts.GATE_FACTS.items()
                    if d.get("severity") in ("warn", "observe")}
        self.assertEqual(doc_gate._WARN_FALLBACK, frozenset(declared))


class TestCheckOneUsesIndex(unittest.TestCase):
    """doc-gate 看的是 **index**，不是工作树（ocr2-244）。"""

    def test_untracked_readme_does_not_satisfy_gate(self) -> None:
        import tempfile

        from k3dge.engine import doc_gate

        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            td = ws / "docs" / "memo"
            td.mkdir(parents=True)
            (td / "README.md").write_text("# r\n", encoding="utf-8")      # 只在工作树
            (td / "AUTHORING.md").write_text("# a\n", encoding="utf-8")
            prev, doc_gate.WS = doc_gate.WS, ws
            orig = doc_gate._staged_present
            doc_gate._staged_present = lambda rel: False                  # index 里啥都没有
            try:
                errs = doc_gate.check_one("docs/memo/x.md")
            finally:
                doc_gate._staged_present = orig
                doc_gate.WS = prev
            self.assertTrue(errs, errs)


if __name__ == "__main__":
    unittest.main()
