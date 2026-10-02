import contextlib
import io
import os
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from k3dge.cli.main import build_parser, main
from k3dge.engine.evaluator import ConsistencyEngine
import shutil


class TestEvidenceAndPorcelain(unittest.TestCase):
    """日志写不进必须出声；porcelain 的重命名行不得当成路径（ocr-380/381/384）。"""

    def test_append_log_failure_is_loud(self) -> None:
        """写不进必须出声（ocr-380）。

        旧夹具靠 `chmod(0o000)`——uid 0（Docker/CI 常是 root）根本不受权限位约束、
        Windows 上是 no-op：追加**成功**、无 WARN，测红成"代码回归"。改成可移植的
        必然失败：把日志路径位置放一个**目录** ⇒ open(path,"a") 恒 IsADirectoryError。
        """
        from k3dge.cli.main import _append_log

        ws = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, ws, ignore_errors=True)
        (ws / "logs").mkdir()
        (ws / "logs" / "k3dge.log").mkdir()        # 目录冒充日志文件：跨平台必败
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            _append_log(ws, "check rc=0")
        self.assertIn("WARN", err.getvalue(), "证据面失败静默 ⇒ 复盘误判'没跑过'")

    def test_porcelain_rename_lines_take_new_path(self) -> None:
        from k3dge.cli.main import _porcelain_paths

        got = _porcelain_paths(
            "R  src/b.py\0src/a.py\0 M src/c.py\0A  docs/x.md\0?? src/é.md\0")
        self.assertEqual(got, ["src/b.py", "src/c.py", "docs/x.md", "src/é.md"])

    def test_mcp_err_normalizes_path_separators(self) -> None:
        import json as _json

        from k3dge.cli.mcp import _err

        payload = _json.loads(_err("WorkspaceOutsideRoot", "x", path="C:\\ws\\sub"))
        self.assertEqual(payload["path"], "C:/ws/sub")


class TestCli(unittest.TestCase):
    def test_parser_has_audit(self):
        actions = build_parser()._subparsers._group_actions[0].choices  # type: ignore[attr-defined]
        self.assertIn("audit", actions)
        # bundle 交付面已**下沉为 audit 子动词**：顶层不再有 bundle，但 audit 仍有它。
        self.assertNotIn("bundle", actions)
        audit_action_choices = next(
            a.choices for a in actions["audit"]._actions if getattr(a, "dest", "") == "audit_action"
        )  # type: ignore[attr-defined]
        self.assertIn("bundle", audit_action_choices)

    def test_audit_submit_no_peer(self):

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
                # 对等审计线动词已退休（2026-09-26）：一律**明确拒绝**并给指引（不静默、不崩）
                for verb in ("submit", "status", "show", "materialize", "close", "advance"):
                    self.assertEqual(main(["audit", verb, "X"]), 1, verb)
            finally:
                os.chdir(cwd)

    def test_milestone_audit_submit_persists(self):
        """回归（真跑 M8 发现 code-1）：`milestone audit-submit` 曾引未定义的 `ms` → NameError。"""

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

    def test_milestone_audit_runs_the_flow(self):
        """回归（2026-09-27 真跑发现）：棘轮退休后 `milestone audit` 的入口**悬空**——只剩 `print(msg)`，
        抛 `UnboundLocalError`，审计腿根本没跑。此测试钉住"入口必须真调 `run_audit_flow`"。

        悬空入口正是本仓最怕的一类缺陷：**声明了没人接**（AGENTS「到达环」）——所以判据落在"调用"上，
        而不是"有没有这段代码"。
        """
        from k3dge.engine import milestone_audit as ma

        calls = {}

        def _fake_flow(ws, mid, **kw):
            calls["args"] = (ws, mid)
            return "rejected", "审计被拒：理由 X"

        orig = ma.run_audit_flow
        ma.run_audit_flow = _fake_flow          # type: ignore[assignment]
        try:
            with tempfile.TemporaryDirectory() as d:
                ws = Path(d)
                (ws / ".agent").mkdir()
                (ws / "docs").mkdir()
                # CLI 的工作区＝`_find_workspace(Path.cwd())`：不 chdir 进沙箱，上面这套
                # `.agent/`＋`docs/` 布置全为空转，测的意义随 pytest 启动目录漂移（t-040）。
                cwd = os.getcwd()
                os.chdir(ws)
                try:
                    out = io.StringIO()
                    with contextlib.redirect_stdout(out):
                        rc = main(["milestone", "audit", "M9"])
                    self.assertEqual(rc, 1)                     # rejected ⇒ 退 1
                    self.assertIn("审计被拒：理由 X", out.getvalue())
                    self.assertEqual(calls["args"][1], "M9")    # 真把里程碑 id 传了下去
                    self.assertEqual(Path(str(calls["args"][0])).resolve(), ws.resolve(),
                                     "解析出的工作区没有传下去——流程靠它定位账本/侧车")
                finally:
                    os.chdir(cwd)
        finally:
            ma.run_audit_flow = orig            # type: ignore[assignment]

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
            , encoding="utf-8")
            (repo / "src" / "core").mkdir(parents=True)
            (repo / "docs" / "specs" / "core").mkdir(parents=True)
            (repo / "src/core/mod.py").write_text("def foo(x: int) -> int:\n    return x\n", encoding="utf-8")
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
            , encoding="utf-8")
            subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
            (repo / "src/core/mod.py").write_text("def foo(x: int, y: str) -> int:\n    return x\n", encoding="utf-8")
            # run check via ConsistencyEngine directly to avoid cwd side effects
            report = ConsistencyEngine(repo).evaluate()
            self.assertFalse(report.passed)
            # also verify CLI main returns 1 when workspace is the temp repo
            # need to chdir

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

        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
            (repo / ".agent").mkdir()
            (repo / ".agent" / "manifest.json").write_text(json.dumps({"package_root": "src", "domains": {}}), encoding="utf-8")
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

        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
            (repo / ".agent").mkdir()
            (repo / ".agent" / "manifest.json").write_text(
                json.dumps({"package_root": "src", "domains": {}})
            , encoding="utf-8")
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

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ws = root / "k3dge"
            peer = root / "k3che"
            ws.mkdir()
            (ws / ".agent").mkdir()
            (ws / ".agent" / "manifest.json").write_text(json.dumps({"package_root": "src", "domains": {}}), encoding="utf-8")
            (ws / ".agent" / "pipeline.toml").write_text(
                "[peers.k3che]\nscope = \"cache\"\ntransports = [{ provider = \"mcp\", tool = \"k3che_search\" }]\n"
            , encoding="utf-8")
            (peer / "src" / "k3che").mkdir(parents=True)
            (peer / "src" / "k3che" / "mcp.py").write_text("def main():\n    pass\n", encoding="utf-8")
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

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ws = root / "k3dge"
            peer = root / "k3che"
            ws.mkdir()
            (ws / ".agent").mkdir()
            (ws / ".agent" / "manifest.json").write_text(json.dumps({"package_root": "src", "domains": {}}), encoding="utf-8")
            (ws / ".agent" / "pipeline.toml").write_text(
                "[peers.k3che]\nscope = \"cache\"\ntransports = [{ provider = \"mcp\", tool = \"k3che_search\" }]\n"
            , encoding="utf-8")
            (ws / ".mcp.json").write_text(
                json.dumps({"mcpServers": {"k3che": {"command": "python", "args": ["-m", "k3che.mcp"]}}})
            , encoding="utf-8")
            (peer / "src" / "k3che").mkdir(parents=True)
            (peer / "src" / "k3che" / "mcp.py").write_text("def main():\n    pass\n", encoding="utf-8")
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




def test_find_workspace_confines_to_mcp_root():
    """ADR-0026：MCP 服务根存在时 workspace_path 越界报错；显式 opt-in 才放行。"""

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


def test_status_deep_vs_summary(monkeypatch, tmp_path, capsys):
    """ADR-0008 §2：默认摘要前 10 + 还有 N 条提示；--deep 出全量。

    隔离工作区与配置（t-039）：旧 `_find_workspace` 打桩成 `Path(".")`——截断上限读的是
    **真仓**的 `[gates.output] default_lines`（="10" 才成立），`_emit_all_hints` 也扫真
    checkout ⇒ `"more" not in out2` 这种全输出子串判据可被任何提示措辞打破或假通过。
    现在：临时 ws 显式钉 default_lines=10，断言收窄到 Unfinished 块。
    """
    import argparse

    from k3dge.cli import main as m
    from k3dge.cli import status as st

    ws = tmp_path / "ws"
    (ws / ".agent").mkdir(parents=True)
    (ws / ".agent" / "pipeline.toml").write_text("[gates.output]\ndefault_lines = 10\n",
                                                 encoding="utf-8")

    obj = {
        "ok": True, "domains": ["d"], "gate_passed": True, "modified_domains": [],
        "drift": [], "pipeline": {"configured": True, "issues": []},
        "unfinished_tasks": [{"task": f"t{i}", "title": f"T{i}", "status": "idea"} for i in range(12)],
        "next": None, "cache": None,
    }
    monkeypatch.setattr(st, "workspace_status", lambda w: obj)
    monkeypatch.setattr(m, "_find_workspace", lambda *a, **k: ws)
    assert m.cmd_status(argparse.Namespace(json=False, deep=False)) == 0
    lines = capsys.readouterr().out.splitlines()
    block = [ln for ln in lines
             if ln.startswith("Unfinished") or ln.strip().startswith("- [") or " more" in ln]
    body = "\n".join(block)
    assert "Unfinished tasks (12)" in body, body
    assert sum(1 for ln in block if ln.strip().startswith("- [")) == 10, body
    assert "2 more" in body and "T11" not in body, body
    assert m.cmd_status(argparse.Namespace(json=False, deep=True)) == 0
    lines2 = capsys.readouterr().out.splitlines()
    rows2 = [ln for ln in lines2 if ln.strip().startswith("- [")]
    assert len(rows2) == 12, lines2
    assert any("T11" in ln for ln in rows2)
    assert not [ln for ln in lines2 if " more (" in ln], lines2


def test_audit_bundle_manual_entry_lands_report_like_the_leg(monkeypatch):
    """手动入口与封板腿**效果唯一**：`k3dge audit bundle` 也必须落报告+提交（共用 `land_report`）。

    流程体检出处（2026-09-27）：手动入口此前只跑 consume，报告不落盘、不提交 ⇒ "同一模块同一参数"
    只是形式（判定面看不到产物）。

    `cmd_audit` 的工作区＝`_find_workspace(Path.cwd())`（`--into` 只决定 target），**必须 chdir 进
    沙箱**（t-037）：否则 (a) 建好的 `.agent/` 从不被用，(b) 收尾的 `_append_log` 把
    `logs/k3dge.log` 写进**跑测试的真仓**——测的意义随 pytest 启动目录漂移。
    """
    from k3dge.engine import audit_bundle as ab

    calls = {}
    orig_consume, orig_land = ab.consume, ab.land_report
    ab.consume = lambda t, b, **k: {"ok": True, "apply": {"ok": True, "files": ["src/a.py"]},
                                    "facts": {"job_id": "j1"}}
    ab.land_report = lambda w, m, out, **k: (calls.update(extra=list(k.get("extra_files") or []), mid=m)
                                             or {"ok": True, "report": "docs/reviews/x.md", "commit": "c" * 40})
    try:
        import contextlib
        import io
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            (ws / ".agent").mkdir()
            (ws / "bundle").mkdir()
            (ws / "bundle" / "manifest.json").write_text('{"bundle_version": 1}', encoding="utf-8")
            monkeypatch.chdir(ws)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["audit", "bundle", str(ws / "bundle"), "--into", str(ws)])
            assert rc == 0
            assert calls.get("extra") == ["src/a.py"] and "landed" in out.getvalue()
            assert calls.get("mid") == "local", calls        # 绝不能用包路径当里程碑 id
            # 工作区解析真的落在沙箱：审计行写进 ws/logs，而不是启动目录
            log = ws / "logs" / "k3dge.log"
            assert log.is_file() and "audit bundle" in log.read_text(encoding="utf-8")
    finally:
        ab.consume, ab.land_report = orig_consume, orig_land


def test_audit_bundle_manual_entry_fails_clear_when_landing_fails(monkeypatch):
    """落地失败必须**退非零**（否则"看着成功、其实没落"＝正是要消灭的那类无实效）。

    同 t-037：chdir 进沙箱，`_append_log` 不再往真仓的 `logs/k3dge.log` 添行。
    """
    from k3dge.engine import audit_bundle as ab

    orig_consume, orig_land = ab.consume, ab.land_report
    ab.consume = lambda t, b, **k: {"ok": True, "apply": {"ok": True, "files": []}, "facts": {}}
    ab.land_report = lambda w, m, out, **k: {"ok": False, "error": "REPORT_PERSIST_FAILED",
                                             "detail": "bad id"}
    try:
        import contextlib
        import io
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            (ws / ".agent").mkdir()
            (ws / "bundle").mkdir()
            (ws / "bundle" / "manifest.json").write_text('{"bundle_version": 1}', encoding="utf-8")
            monkeypatch.chdir(ws)
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = main(["audit", "bundle", str(ws / "bundle"), "--into", str(ws)])
            assert rc == 1 and "落报告/提交失败" in err.getvalue()
            assert (ws / "logs" / "k3dge.log").is_file()     # 失败轮也留证据，且留在沙箱
    finally:
        ab.consume, ab.land_report = orig_consume, orig_land


if __name__ == "__main__":
    # 本文件混装 TestCase 类与模块级 pytest 函数（t-041）：`unittest.main()` 只发现前者，
    # ADR-0026 MCP 封闭性与 audit-bundle 落地这两组**安全/数据完整性**回归会在直跑时静默消失。
    try:
        import pytest
    except ImportError:                                # pragma: no cover
        unittest.main()
    else:
        raise SystemExit(pytest.main([__file__, "-q"]))
