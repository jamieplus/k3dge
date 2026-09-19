"""cache 角色的第一消费者：doc-audit 相关文档前路由（service 语义，不进判定）。"""
from __future__ import annotations

import json
import pathlib
import unittest
from tempfile import TemporaryDirectory
from unittest import mock

from k3dge.engine.doc_audit import (
    _attach_k3che_hints,
    _related_doc_hints,
    _similar_task_hints,
    run_doc_audit,
)
from k3dge.engine.pipeline_runner import TransportResult

WS = pathlib.Path(__file__).resolve().parents[3]

HITS = json.dumps({"ok": True, "kind": "hits", "results": [
    {"path": "docs/adr/0006-mcp-foreign-harness-injection.md", "title": "ADR-0006", "score": 9.1},
    {"path": "docs/guides/mcp-bridge.md", "title": "MCP Bridge", "score": 7.0},
]})


def _ws_with_task(root: pathlib.Path) -> pathlib.Path:
    (root / "docs" / "tasks").mkdir(parents=True)
    t = root / "docs" / "tasks" / "2026-09-03-M7-audit-doc-audit-demo.md"
    t.write_text("# doc-audit: demo\n\n- **Status**: idea\n", encoding="utf-8")
    return t


class TestHints(unittest.TestCase):
    def test_hints_parsed_from_mcp_envelope(self):
        with TemporaryDirectory() as d:
            ws = pathlib.Path(d)
            ok = TransportResult(True, "mcp", "x", payload=HITS)
            with mock.patch("k3dge.engine.pipeline_runner.run_action", return_value=ok):
                hints = _related_doc_hints(ws, ["docs/adr/0006.md"])
            self.assertEqual(len(hints), 2)
            self.assertEqual(hints[0][0], "docs/adr/0006-mcp-foreign-harness-injection.md")

    def test_skip_provider_degrades_to_no_hints_never_errors(self):
        with TemporaryDirectory() as d:
            ws = pathlib.Path(d)
            skipped = TransportResult(True, "skip", "skipped", skipped=True)
            with mock.patch("k3dge.engine.pipeline_runner.run_action", return_value=skipped):
                self.assertEqual(_related_doc_hints(ws, ["docs/x.md"]), [])
            broken = TransportResult(True, "mcp", "x", payload="not-json")
            with mock.patch("k3dge.engine.pipeline_runner.run_action", return_value=broken):
                self.assertEqual(_related_doc_hints(ws, ["docs/x.md"]), [])

    def test_attach_writes_and_refreshes_block_idempotently(self):
        with TemporaryDirectory() as d:
            ws = pathlib.Path(d)
            t = _ws_with_task(ws)
            ok = TransportResult(True, "mcp", "x", payload=HITS)
            with mock.patch("k3dge.engine.pipeline_runner.run_action", return_value=ok):
                self.assertEqual(_attach_k3che_hints(ws, ["docs/adr/0006.md"]), 2)
                self.assertEqual(_attach_k3che_hints(ws, ["docs/adr/0006.md"]), 2)  # 再跑一次不叠加
            body = t.read_text(encoding="utf-8")
            self.assertEqual(body.count("k3che · 服务性前路由"), 1)
            self.assertIn("docs/guides/mcp-bridge.md", body)
            self.assertNotIn("mcp-bridge.md`\n- `docs/guides/mcp-bridge.md", body)

    def test_run_doc_audit_end_to_end_attaches_hints(self):
        with TemporaryDirectory() as d:
            ws = pathlib.Path(d)
            (ws / ".agent").mkdir()
            (ws / "docs" / "tasks").mkdir(parents=True)

            def fake_action(_ws, ref, **kw):
                if ref.startswith("cache."):
                    return TransportResult(True, "mcp", "x", payload=HITS)
                return TransportResult(True, "manual", "ok")

            with mock.patch("k3dge.engine.pipeline_runner.run_action", side_effect=fake_action), \
                 mock.patch("k3dge.engine.doc_audit._changed_docs", return_value=["docs/adr/0006.md"]), \
                 mock.patch("k3dge.engine.milestone_pointer.get_current_milestone", return_value="M1"):
                status, msg = run_doc_audit(ws)
            self.assertEqual(status, "reported")
            tasks = [p for p in (ws / "docs" / "tasks").glob("*.md") if "doc_audit" in p.name or "doc-audit" in p.name]
            self.assertEqual(len(tasks), 1)
            self.assertIn("服务性前路由", tasks[0].read_text(encoding="utf-8"))


class TestStatusObservability(unittest.TestCase):
    def _ws(self, root):
        ws = pathlib.Path(root)
        (ws / ".agent").mkdir()
        (ws / ".agent" / "manifest.json").write_text('{"package_root":"src","domains":{}}', encoding="utf-8")
        (ws / "docs" / "tasks").mkdir(parents=True)
        return ws

    def test_no_k3che_dir_never_spawns(self):
        from tempfile import TemporaryDirectory
        from k3dge.cli.status import workspace_status

        with TemporaryDirectory() as d:
            ws = self._ws(d)
            with mock.patch("k3dge.engine.pipeline_runner.run_action", side_effect=AssertionError("不该被调用")):
                st = workspace_status(ws)
            self.assertIsNone(st["cache"])

    def test_stats_envelope_surfaces_in_json_and_text(self):
        import io as _io
        import contextlib
        from tempfile import TemporaryDirectory

        from k3dge.cli.main import main
        from k3dge.cli.status import workspace_status

        stats = json.dumps({"ok": True, "total": 3, "hits": 2, "hit_rate": 0.667, "indexed": 118, "persisted": True})
        with TemporaryDirectory() as d:
            ws = self._ws(d)
            (ws / ".k3che").mkdir()
            hit = TransportResult(True, "mcp", "x", payload=stats)

            def fake(_ws, ref, **kw):
                assert ref == "cache.stats", ref
                return hit

            with mock.patch("k3dge.engine.pipeline_runner.run_action", side_effect=fake):
                st = workspace_status(ws)
                self.assertEqual(st["cache"]["total"], 3)
                buf = _io.StringIO()
                with contextlib.redirect_stdout(buf):
                    rc = main(["status"])
            text = buf.getvalue()
            self.assertEqual(rc, 0)
            self.assertIn("Cache (k3che): 3 queries, hits 2, hit_rate 0.67, indexed 118", text)
            self.assertIn("观测展示，不参与任何判定", text)


class TestDupCheck(unittest.TestCase):
    def _env(self, n=4):
        return json.dumps({"ok": True, "results": [
            {"path": f"docs/tasks/archive/old-{i}.md", "title": f"Old {i}", "score": 9 - i} for i in range(n)
        ]})

    def test_engine_helper_excludes_self_and_caps(self):
        with TemporaryDirectory() as d:
            ws = pathlib.Path(d)
            hit = TransportResult(True, "mcp", "x", payload=self._env())
            ex = ws / "docs" / "tasks" / "new.md"
            with mock.patch("k3dge.engine.pipeline_runner.run_action", return_value=hit):
                hints = _similar_task_hints(ws, "whatever", exclude=None)
            self.assertEqual(len(hints), 3)
            hit2 = TransportResult(True, "mcp", "x", payload=json.dumps({"ok": True, "results": [
                {"path": "docs/tasks/new.md", "title": "self"}, {"path": "docs/x.md", "title": "keep"}]}))
            with mock.patch("k3dge.engine.pipeline_runner.run_action", return_value=hit2):
                hints2 = _similar_task_hints(ws, "whatever", exclude=ex)
            self.assertEqual([h[0] for h in hints2], ["docs/x.md"])

    def test_engine_helper_degrades_silently(self):
        with TemporaryDirectory() as d:
            ws = pathlib.Path(d)
            skipped = TransportResult(True, "skip", "skipped", skipped=True)
            with mock.patch("k3dge.engine.pipeline_runner.run_action", return_value=skipped):
                self.assertEqual(_similar_task_hints(ws, "t"), [])
            bad = TransportResult(True, "mcp", "x", payload="nope")
            with mock.patch("k3dge.engine.pipeline_runner.run_action", return_value=bad):
                self.assertEqual(_similar_task_hints(ws, "t"), [])

    def test_cli_create_shows_dup_check_and_never_blocks(self):
        import io as _io

        from k3dge.cli.main import main
        import contextlib
        import os
        import subprocess

        with TemporaryDirectory() as d:
            ws = pathlib.Path(d)
            (ws / ".agent").mkdir()
            subprocess.run(["git", "init", "-b", "main"], cwd=ws, check=True, capture_output=True)
            (ws / ".agent" / "manifest.json").write_text('{"package_root":"src","domains":{}}', encoding="utf-8")
            old = pathlib.Path.cwd()
            try:
                os.chdir(ws)
                with mock.patch("k3dge.engine.pipeline_runner.run_action",
                                return_value=TransportResult(True, "mcp", "x", payload=self._env())):
                    buf = _io.StringIO()
                    with contextlib.redirect_stdout(buf):
                        rc = main(["task", "create", "Dupcheck Demo A", "--type", "feat", "--milestone", "M1"])
                out = buf.getvalue()
                self.assertEqual(rc, 0)
                # 档位与文案来自 gate_facts 声明面（code=DUP_CHECK，observe 档）
                self.assertIn("[DUP_CHECK]", out)
                self.assertIn("fact:", out)
                self.assertIn("docs/tasks/archive/old-0.md", out)
                self.assertIn("不阻断、不裁决", out)
                # service 挂掉：无提示，创建照旧成功
                with mock.patch("k3dge.engine.pipeline_runner.run_action",
                                return_value=TransportResult(True, "skip", "s", skipped=True)):
                    buf2 = _io.StringIO()
                    with contextlib.redirect_stdout(buf2):
                        rc2 = main(["task", "create", "Dupcheck Demo B", "--type", "feat", "--milestone", "M1"])
                self.assertEqual(rc2, 0)
                self.assertNotIn("[DUP_CHECK]", buf2.getvalue())
            finally:
                os.chdir(old)


if __name__ == "__main__":
    unittest.main()
