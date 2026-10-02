"""cache 角色的第一消费者：doc-audit 相关文档前路由（service 语义，不进判定）。"""

import json
import pathlib
import unittest
from tempfile import TemporaryDirectory
from unittest import mock

from k3dge.engine.task_write import _similar_task_hints
from k3dge.engine.pipeline_runner import TransportResult

def _ws_with_task(root: pathlib.Path) -> pathlib.Path:
    (root / "docs" / "tasks").mkdir(parents=True, exist_ok=True)
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
            # patch 落在**定义模块** `pipeline_runner.run_action`，只因 `task_write._similar_task_hints`
            # 在函数体内延迟 `from ... import run_action`（t-081）：哪天提到模块级，patch 变 no-op、
            # 真传输会被调（单测里跑活 peer）。断"mock 真被调用"——不生效立即红，而不是静默打真网络。
            with mock.patch("k3dge.engine.pipeline_runner.run_action", return_value=hit) as mk:
                hints = _similar_task_hints(ws, "whatever", exclude=None)
            self.assertTrue(mk.called, "patch 未命中解析路径——延迟 import 可能被移到了模块级")
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
                # 只断**结构**：闸码头 + fact 行 + 候选路径行——文案（含"不阻断、不裁决"）
                # 属 gate_facts 声明面，改措辞不该红本测（t-082）。档位语义单独用声明面核对。
                from k3dge.engine import gate_facts
                self.assertIn("[DUP_CHECK]", out)
                self.assertIn("fact:", out)
                self.assertIn("docs/tasks/archive/old-0.md", out)
                self.assertEqual(gate_facts.severity("DUP_CHECK"), "observe",
                                 "cache 第一消费者必须走 observe 档（不进判定、不阻断）")
                # service 挂掉：无提示，创建照旧成功
                with mock.patch("k3dge.engine.pipeline_runner.run_action",
                                return_value=TransportResult(True, "skip", "s", skipped=True)):
                    buf2 = _io.StringIO()
                    with contextlib.redirect_stdout(buf2):
                        rc2 = main(["task", "create", "Dupcheck Demo B", "--type", "feat", "--milestone", "M1"])
                self.assertEqual(rc2, 0)
                self.assertNotIn("[DUP_CHECK]", buf2.getvalue())

                # 既有票在场：命中走**真 CLI** 显示路径（t-080——`_ws_with_task` 曾是
                # 定义了没人用的死夹具，"有票的工作区"这一场景到底没没覆盖无从判断）
                task = _ws_with_task(ws)
                rel = task.relative_to(ws).as_posix()
                hit3 = TransportResult(True, "mcp", "x", payload=json.dumps(
                    {"ok": True, "results": [{"path": rel, "title": "doc-audit: demo", "score": 9.9}]}))
                with mock.patch("k3dge.engine.pipeline_runner.run_action", return_value=hit3):
                    buf3 = _io.StringIO()
                    with contextlib.redirect_stdout(buf3):
                        rc3 = main(["task", "create", "Dupcheck Demo C", "--type", "feat",
                                    "--milestone", "M1"])
                self.assertEqual(rc3, 0)
                self.assertIn(rel, buf3.getvalue(), buf3.getvalue())
            finally:
                os.chdir(old)


if __name__ == "__main__":
    unittest.main()
