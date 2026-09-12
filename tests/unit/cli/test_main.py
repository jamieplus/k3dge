import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from k3dge.cli.main import build_parser, main
from k3dge.engine.evaluator import ConsistencyEngine


class TestCli(unittest.TestCase):
    def test_parser_has_audit(self):
        actions = build_parser()._subparsers._group_actions[0].choices  # type: ignore[attr-defined]
        self.assertIn("audit", actions)
        self.assertNotIn("bundle", actions)   # 审计线模型：bundle 交付面已废

    def test_audit_submit_no_peer(self):
        import os

        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            subprocess.run(["git", "init", "-qb", "main", str(d)], check=True, capture_output=True)
            (d / "src").mkdir()
            (d / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "-A"], cwd=d, check=True, capture_output=True)
            subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "i"],
                           cwd=d, check=True, capture_output=True)
            cwd = os.getcwd()
            os.chdir(d)
            try:
                rc2 = main(["audit", "submit"])  # 无 .mcp.json ⇒ 对端不可达 ⇒ rc 1，不崩
                self.assertEqual(rc2, 1)
                rc3 = main(["audit", "status", "J-ghost"])  # status 半边同样不许 AttributeError
                self.assertEqual(rc3, 1)
                rc4 = main(["audit", "show"])  # 读本地账，无单也 ok
                self.assertEqual(rc4, 0)
                rc5 = main(["audit", "materialize", "--oid", "HEAD", "--dest", "mat"])
                self.assertEqual(rc5, 0)  # 只读物化，不碰线
                self.assertTrue((d / "mat" / "src" / "a.py").is_file())
            finally:
                os.chdir(cwd)

    def test_milestone_audit_submit_persists(self):
        """回归（真跑 M8 发现 code-1）：`milestone audit-submit` 曾引未定义的 `ms` → NameError。"""
        import os

        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            subprocess.run(["git", "init", "-qb", "main", str(d)], check=True, capture_output=True)
            (d / "docs" / "reviews").mkdir(parents=True)
            rpt = d / "r.md"
            rpt.write_text(
                "| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| X1 | 2026-09-11 | 低 | P3 | 规范 | d | l | 已修 | - | - | - | - |\n",
                encoding="utf-8",
            )
            cwd = os.getcwd()
            os.chdir(d)
            try:
                rc = main(["milestone", "audit-submit", "M1", "--file", str(rpt)])
            finally:
                os.chdir(cwd)
            self.assertEqual(rc, 0)
            self.assertTrue(any((d / "docs" / "reviews").glob("*M1*audit*.md")))

    def test_parser_has_check_sync_milestone(self):
        parser = build_parser()
        actions = [a for a in parser._subparsers._group_actions[0].choices]  # type: ignore[attr-defined]
        self.assertIn("check", actions)
        self.assertIn("sync", actions)
        self.assertIn("milestone", actions)
        self.assertIn("init", actions)
        self.assertIn("mcp", actions)
        self.assertIn("task", actions)
        self.assertIn("version", actions)
        self.assertIn("doc", actions)
        self.assertIn("audit", actions)  # ⑩ 转正（此前为未授权预留）
        task = parser._subparsers._group_actions[0].choices["task"]
        action = next(a for a in task._actions if a.dest == "task_action")
        self.assertIn("list", action.choices)
        check = parser._subparsers._group_actions[0].choices["check"]
        self.assertTrue(any(a.dest == "force_full" for a in check._actions))

    def test_check_exit_nonzero_on_drift(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "tester"], cwd=repo, check=True, capture_output=True)
            (repo / ".agent").mkdir()
            (repo / ".agent" / "manifest.json").write_text(
                json.dumps(
                    {
                        "package_root": "src",
                        "domains": {"core": {"src": "src/core", "spec": "docs/specs/core/spec.md"}},
                        "ignore": [],
                    }
                )
            )
            (repo / "src" / "core").mkdir(parents=True)
            (repo / "docs" / "specs" / "core").mkdir(parents=True)
            (repo / "src/core/mod.py").write_text("def foo(x: int) -> int:\n    return x\n")
            (repo / "docs/specs/core/spec.md").write_text(
                "# Domain Specification: core\n"
                "- **Status**: Active\n"
                "- **Module Path**: `src/core`\n"
                "- **Contract Hash**: `sha256:" + "0" * 64 + "`\n"
                "- **Last Updated**: 2026-08-19\n"
                "## 1. Domain Boundary & Responsibilities\n"
                "## 2. Public Interfaces & Type Contracts\n"
                "<!-- k3dge:interfaces-start -->\n```python\n```\n<!-- k3dge:interfaces-end -->\n"
                "## 3. State Machine & Invariants\n"
                "## 4. Verification Matrix\n"
            )
            subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
            (repo / "src/core/mod.py").write_text("def foo(x: int, y: str) -> int:\n    return x\n")
            # run check via ConsistencyEngine directly to avoid cwd side effects
            report = ConsistencyEngine(repo).evaluate()
            self.assertFalse(report.passed)
            # also verify CLI main returns 1 when workspace is the temp repo
            # need to chdir
            import os

            old = Path.cwd()
            try:
                os.chdir(repo)
                code = main(["check"])
                self.assertEqual(code, 1)
                # --json variant should be valid JSON with passed=false
                import io
                import contextlib

                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    code_json = main(["check", "--json"])
                self.assertEqual(code_json, 1)
                data = json.loads(buf.getvalue())
                self.assertFalse(data["passed"])
                self.assertTrue(any(v["rule_id"] == "CONTRACT_DRIFT" for v in data["violations"]))
            finally:
                os.chdir(old)

    def test_milestone_status_no_tasks_exits_one(self):
        import os

        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
            (repo / ".agent").mkdir()
            (repo / ".agent" / "manifest.json").write_text(json.dumps({"package_root": "src", "domains": {}}))
            (repo / "docs" / "tasks").mkdir(parents=True)
            old = Path.cwd()
            try:
                os.chdir(repo)
                self.assertEqual(main(["milestone", "status", "M1"]), 1)
            finally:
                os.chdir(old)

    def test_status_next_is_isomorphic_across_exits(self):
        """ADR-0008: the routing line must be visible on all three exits identically.

        Regression for the second half of the `status` bug: the human path printed
        [NEXT] but `status --json` and MCP `k3dge_status` had no `next` field at all,
        so machine consumers could not see the routing at all.
        """
        import contextlib
        import io
        import os

        from k3dge.cli.mcp import k3dge_status

        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            (repo / ".agent").mkdir(parents=True)
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
            (repo / ".agent" / "manifest.json").write_text(
                json.dumps({"package_root": "src", "domains": {}}), encoding="utf-8"
            )
            (repo / "docs" / "tasks").mkdir(parents=True)
            # a pinned finding is the highest-precedence routing state
            (repo / "src").mkdir()
            (repo / "src" / "mod.py").write_text("def f():\n    # k3dit:pending T-ISO-1\n    return 1\n", encoding="utf-8")

            old = Path.cwd()
            try:
                os.chdir(repo)
                human = io.StringIO()
                with contextlib.redirect_stdout(human):
                    code = main(["status"])
                json_buf = io.StringIO()
                with contextlib.redirect_stdout(json_buf):
                    main(["status", "--json"])
            finally:
                os.chdir(old)

            self.assertEqual(code, 0)
            h = human.getvalue()
            self.assertIn("[NEXT] state=pending_findings", h)
            data = json.loads(json_buf.getvalue())
            self.assertIn("next", data)
            self.assertEqual(data["next"]["state"], "pending_findings")
            self.assertGreaterEqual(data["next"]["pending"], 1)
            mcp = json.loads(k3dge_status(workspace_path=str(repo)))
            self.assertEqual(mcp["next"], data["next"])  # all three exits agree


    def test_status_renders_and_ignores_doc_aux(self):
        """Regression: `cmd_status` referenced an unbound `workspace`, so the tail of the
        command (NEXT + hints) raised NameError and `status` never finished cleanly.
        Also asserts docs/tasks/AUTHORING.md is not reported as an unfinished task.
        """
        import contextlib
        import io
        import os

        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
            (repo / ".agent").mkdir()
            (repo / ".agent" / "manifest.json").write_text(
                json.dumps({"package_root": "src", "domains": {}}), encoding="utf-8"
            )
            (repo / "docs" / "tasks").mkdir(parents=True)
            (repo / "docs" / "tasks" / "AUTHORING.md").write_text(
                "# Authoring\n\nStructure gate is `.schema.json`.\n", encoding="utf-8"
            )
            (repo / "docs" / "tasks" / "2026-09-02-M1-feat-demo.md").write_text(
                "# Demo task\n- **Status**: idea\n- **Milestone**: M1\n", encoding="utf-8"
            )
            old = Path.cwd()
            buf = io.StringIO()
            try:
                os.chdir(repo)
                with contextlib.redirect_stdout(buf):
                    code = main(["status"])
                    buf2 = io.StringIO()
                    with contextlib.redirect_stdout(buf2):
                        list_code = main(["task", "list", "--json"])
            finally:
                os.chdir(old)
            out = buf.getvalue()
            self.assertEqual(code, 0, f"status must finish without NameError; got:\n{out}")
            self.assertIn("Unfinished tasks (1):", out)
            self.assertIn("Demo task", out)
            self.assertNotIn("Authoring", out)
            self.assertNotIn("Traceback", out)
            data = json.loads(buf2.getvalue())
            self.assertEqual(data["count"], 1)
            self.assertEqual(data["tasks"][0]["path"], "docs/tasks/2026-09-02-M1-feat-demo.md")

    def test_task_list_json(self):
        import os
        import contextlib
        import io

        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
            (repo / ".agent").mkdir()
            (repo / ".agent" / "manifest.json").write_text(
                json.dumps({"package_root": "src", "domains": {}})
            )
            (repo / "docs" / "tasks").mkdir(parents=True)
            (repo / "docs" / "tasks" / "2026-08-25-fix-foo.md").write_text(
                "# Do foo\n\n- **Status**: idea\n- **Milestone**: M2\n- **Priority**: P1\n",
                encoding="utf-8",
            )
            old = Path.cwd()
            try:
                os.chdir(repo)
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    code = main(["task", "list", "--json"])
                self.assertEqual(code, 0)
                data = json.loads(buf.getvalue())
                self.assertTrue(data["ok"])
                self.assertEqual(data["count"], 1)
                self.assertEqual(data["tasks"][0]["title"], "Do foo")
                self.assertEqual(data["tasks"][0]["status"], "idea")
                self.assertEqual(data["tasks"][0]["milestone"], "M2")
                self.assertEqual(data["tasks"][0]["priority"], "P1")
            finally:
                os.chdir(old)

    def test_init_creates_harness(self):
        import os

        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "proj"
            old = Path.cwd()
            try:
                os.chdir(Path(d))
                code = main(["init", str(target), "--name", "demo"])
                self.assertEqual(code, 0)
                self.assertTrue((target / ".agent" / "manifest.json").exists())
                self.assertTrue((target / "docs" / "specs" / "demo" / "spec.md").exists())
                self.assertTrue((target / "src" / "demo" / "__init__.py").exists())
            finally:
                os.chdir(old)

    def test_mcp_sync_adds_peer_pythonpath(self):
        import os
        import contextlib
        import io

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ws = root / "k3dge"
            peer = root / "k3che"
            ws.mkdir()
            (ws / ".agent").mkdir()
            (ws / ".agent" / "manifest.json").write_text(json.dumps({"package_root": "src", "domains": {}}))
            (ws / ".agent" / "pipeline.toml").write_text(
                "[peers.k3che]\nscope = \"cache\"\ntransports = [{ provider = \"mcp\", tool = \"k3che_search\" }]\n"
            )
            (peer / "src" / "k3che").mkdir(parents=True)
            (peer / "src" / "k3che" / "mcp.py").write_text("def main():\n    pass\n")
            subprocess.run(["git", "init", "-b", "main"], cwd=ws, check=True, capture_output=True)
            old = Path.cwd()
            try:
                os.chdir(ws)
                buf = io.StringIO()
                err = io.StringIO()
                with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
                    code = main(["mcp", "sync"])
                self.assertEqual(code, 0)
                data = json.loads((ws / ".mcp.json").read_text(encoding="utf-8"))
                k3che = data["mcpServers"]["k3che"]
                self.assertEqual(k3che["args"], ["-m", "k3che.mcp"])
                self.assertEqual(k3che["env"]["PYTHONPATH"], os.path.join("..", "k3che", "src"))
            finally:
                os.chdir(old)

    def test_mcp_sync_repairs_peer_pythonpath(self):
        import os
        import contextlib
        import io

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ws = root / "k3dge"
            peer = root / "k3che"
            ws.mkdir()
            (ws / ".agent").mkdir()
            (ws / ".agent" / "manifest.json").write_text(json.dumps({"package_root": "src", "domains": {}}))
            (ws / ".agent" / "pipeline.toml").write_text(
                "[peers.k3che]\nscope = \"cache\"\ntransports = [{ provider = \"mcp\", tool = \"k3che_search\" }]\n"
            )
            (ws / ".mcp.json").write_text(
                json.dumps({"mcpServers": {"k3che": {"command": "python", "args": ["-m", "k3che.mcp"]}}})
            )
            (peer / "src" / "k3che").mkdir(parents=True)
            (peer / "src" / "k3che" / "mcp.py").write_text("def main():\n    pass\n")
            subprocess.run(["git", "init", "-b", "main"], cwd=ws, check=True, capture_output=True)
            old = Path.cwd()
            try:
                os.chdir(ws)
                buf = io.StringIO()
                err = io.StringIO()
                with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
                    code = main(["mcp", "sync"])
                self.assertEqual(code, 0)
                data = json.loads((ws / ".mcp.json").read_text(encoding="utf-8"))
                self.assertEqual(data["mcpServers"]["k3che"]["env"]["PYTHONPATH"], os.path.join("..", "k3che", "src"))
            finally:
                os.chdir(old)

    def test_workspace_status_shared_by_cli_and_mcp(self):
        import os

        ws = Path(__file__).resolve().parents[3]
        if not (ws / ".agent" / "manifest.json").exists():
            self.skipTest("no manifest in repo root")
        from k3dge.cli.status import workspace_status
        from k3dge.cli.mcp import k3dge_status

        cli = workspace_status(ws)
        keys = ["domains", "gate_passed", "modified_domains", "drift", "pipeline", "unfinished_tasks"]
        for k in keys:
            self.assertIn(k, cli)
        mcp = json.loads(k3dge_status(workspace_path=str(ws)))
        # MCP tool must delegate to the same implementation, not re-scan — identical shape.
        for k in keys:
            self.assertEqual(cli[k], mcp[k])


if __name__ == "__main__":
    unittest.main()


def test_find_workspace_confines_to_mcp_root():
    """ADR-0026：MCP 服务根存在时 workspace_path 越界报错；显式 opt-in 才放行。"""
    import os
    import tempfile
    from pathlib import Path

    from k3dge.cli.main import _find_workspace

    saved = {k: os.environ.get(k) for k in ("K3DGE_MCP_ROOT", "K3DGE_ALLOW_EXTERNAL_WORKSPACE")}
    try:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            root = tmp / "root"
            (root / "sub").mkdir(parents=True)
            outside = tmp / "outside"
            outside.mkdir()
            os.environ["K3DGE_MCP_ROOT"] = str(root)
            os.environ.pop("K3DGE_ALLOW_EXTERNAL_WORKSPACE", None)
            assert _find_workspace(workspace_path=str(root / "sub")) == (root / "sub").resolve()
            try:
                _find_workspace(workspace_path=str(outside))
                raise AssertionError("越界应 raise")
            except ValueError:
                pass
            os.environ["K3DGE_ALLOW_EXTERNAL_WORKSPACE"] = "1"
            assert _find_workspace(workspace_path=str(outside)) == outside.resolve()
            os.environ.pop("K3DGE_MCP_ROOT", None)
            assert _find_workspace(workspace_path=str(outside)) == outside.resolve()
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_status_deep_vs_summary(monkeypatch, capsys):
    """ADR-0008 §2：默认摘要前 10 + 还有 N 条提示；--deep 出全量。"""
    import argparse

    from k3dge.cli import main as m
    from k3dge.cli import status as st

    obj = {
        "ok": True, "domains": ["d"], "gate_passed": True, "modified_domains": [],
        "drift": [], "pipeline": {"configured": True, "issues": []},
        "unfinished_tasks": [{"task": f"t{i}", "title": f"T{i}", "status": "idea"} for i in range(12)],
        "next": None, "cache": None,
    }
    monkeypatch.setattr(st, "workspace_status", lambda ws: obj)
    monkeypatch.setattr(m, "_find_workspace", lambda *a, **k: Path("."))
    assert m.cmd_status(argparse.Namespace(json=False, deep=False)) == 0
    out = capsys.readouterr().out
    assert "Unfinished tasks (12)" in out and "2 more" in out and "T11" not in out
    assert m.cmd_status(argparse.Namespace(json=False, deep=True)) == 0
    out2 = capsys.readouterr().out
    assert "T11" in out2 and "more" not in out2
