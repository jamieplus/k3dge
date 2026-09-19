"""pre-commit hook integration: schema gate wiring (git calls stubbed)."""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _load_hook():
    mod_name = "k3dge_precommit_hook"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    import importlib.machinery
    loader = importlib.machinery.SourceFileLoader(mod_name, str(ROOT / "scripts" / "pre-commit"))
    spec = importlib.util.spec_from_loader(mod_name, loader)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    loader.exec_module(mod)
    return mod


hook = _load_hook()

# 唯一源形状：元数据只在 frontmatter，正文不复写（TASK_BODY_META_REDUNDANT）
TASK_GOOD = (
    "---\nstatus: idea\npriority: P2\ndate: 2026-09-16\n---\n\n"
    "# t\n\n- **可检索摘要**: 一句话\n"
)


class TestSchemaGateWiring(unittest.TestCase):
    def _run(self, files, blobs, orphan_warns=()):
        orig_staged = hook._staged_bytes
        orig_orphans = hook._orphan_warnings
        hook._staged_bytes = lambda rel: blobs.get(rel)
        hook._orphan_warnings = lambda _refs: list(orphan_warns)
        try:
            pure_schema, pure_refs = hook._load_pure()
            self.assertIsNotNone(pure_schema)
            return hook.run_schema_gate(files, pure_schema, pure_refs)
        finally:
            hook._staged_bytes = orig_staged
            hook._orphan_warnings = orig_orphans

    def test_clean_doc_passes(self):
        errs, warns = self._run(
            ["docs/tasks/2026-09-16-fix-x.md"],
            {"docs/tasks/2026-09-16-fix-x.md": TASK_GOOD.encode()},
        )
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
        errs, warns = self._run(
            ["docs/tasks/2026-09-16-fix-x.md"],
            {"docs/tasks/2026-09-16-fix-x.md": TASK_GOOD.encode()},
            orphan_warns=["[ORPHAN_TEST] tests/unit/test_lonely.py: ..."],
        )
        self.assertEqual(errs, [])
        self.assertEqual(len(warns), 1)

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


if __name__ == "__main__":
    unittest.main()


class TestScreenGateWiring(unittest.TestCase):
    """pre-commit 接线：新增受管文档未排查 ⇒ 阻断；回执后放行；工具坏不阻断。"""

    def _pure_refs(self):
        _ps, pr = hook._load_pure()
        self.assertIsNotNone(pr)
        return pr

    def test_added_and_acked_paths(self):
        import tempfile

        pr = self._pure_refs()
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            rel = "docs/memo/2026-09-19-y.md"
            orig = hook.WS
            hook.WS = ws
            try:
                self.assertEqual(len(hook.run_screen_gate([rel], pr)), 1)
                pr.record_screen_ack(ws, rel)
                self.assertEqual(hook.run_screen_gate([rel], pr), [])
                self.assertEqual(hook.run_screen_gate([], pr), [])
            finally:
                hook.WS = orig

    def test_broken_tool_does_not_block(self):
        class Boom:
            def find_unscreened_new_docs(self, *_a, **_k):
                raise RuntimeError("boom")

        self.assertEqual(hook.run_screen_gate(["docs/adr/0027-x.md"], Boom()), [])
