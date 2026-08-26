import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from k3dge.cli.main import build_parser, main
from k3dge.engine.evaluator import ConsistencyEngine


class TestCli(unittest.TestCase):
    def test_parser_has_check_sync_milestone(self):
        parser = build_parser()
        actions = [a for a in parser._subparsers._group_actions[0].choices]  # type: ignore[attr-defined]
        self.assertIn("check", actions)
        self.assertIn("sync", actions)
        self.assertIn("milestone", actions)
        self.assertIn("init", actions)
        self.assertNotIn("audit", actions)
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


if __name__ == "__main__":
    unittest.main()
