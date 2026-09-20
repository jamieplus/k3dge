"""cache 角色的第一消费者：doc-audit 相关文档前路由（service 语义，不进判定）。"""
from __future__ import annotations

import json
import pathlib
import unittest
from tempfile import TemporaryDirectory
from unittest import mock

from k3dge.engine.task_write import _similar_task_hints
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
