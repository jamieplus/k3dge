"""Outbound MCP client semantics: endpoint from .mcp.json only, peer isolation,
explicit downgrade (ADR-0006 §2.2 / §2.3.3 / §2.4)."""
from __future__ import annotations

import io
import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from k3dge.engine import pipeline_runner as pr


def _ws(root: Path, mcp_json: dict, pipeline: str) -> Path:
    (root / ".agent").mkdir(parents=True, exist_ok=True)
    (root / ".agent" / "pipeline.toml").write_text(pipeline, encoding="utf-8")
    (root / ".mcp.json").write_text(json.dumps(mcp_json), encoding="utf-8")
    (root / "docs" / "protocols").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "protocols" / "audit_default.md").write_text("# protocol\n", encoding="utf-8")
    return root


PIPE_MCP_MANUAL = """
[peers.k3dit]
[peers.k3dit.actions.audit]
transports = [
  { provider = "mcp", tool = "k3dit_run_audit", timeout = 5 },
  { provider = "manual", protocol = "docs/protocols/audit_default.md" },
]
"""


class EndpointResolution(unittest.TestCase):
    def test_absolute_command_must_exist(self) -> None:
        with TemporaryDirectory() as d:
            ws = Path(d)
            ok, note = pr.resolve_endpoint_command(ws, {"command": str(ws / "nope")})
            self.assertIsNone(ok)
            self.assertIn("not found", note)

    def test_bare_python_lands_on_venv_and_says_so(self) -> None:
        with TemporaryDirectory() as d:
            ws = Path(d)
            (ws / ".venv" / "bin").mkdir(parents=True)
            (ws / ".venv" / "bin" / "python").write_text("#!/bin/sh\n", encoding="utf-8")
            with mock.patch.object(pr.shutil, "which", return_value=None):
                cmd, note = pr.resolve_endpoint_command(ws, {"command": "python"})
            self.assertEqual(cmd, str(ws / ".venv" / "bin" / "python"))
            self.assertIn("(fallback", note)  # never a silent substitution

    def test_no_interpreter_at_all_is_a_failure_not_a_guess(self) -> None:
        with TemporaryDirectory() as d:
            ws = Path(d)
            with mock.patch.object(pr.shutil, "which", return_value=None):
                cmd, note = pr.resolve_endpoint_command(ws, {"command": "python"})
            self.assertIsNone(cmd)
            self.assertIn("not on PATH", note)

    def test_cwd_defaults_to_consuming_workspace(self) -> None:
        with TemporaryDirectory() as d:
            ws = Path(d)
            params = pr.build_server_params(ws, {"args": ["-m", "x.mcp"], "env": {"PYTHONPATH": "src"}}, "py")
            self.assertEqual(params["cwd"], str(ws.resolve()))
            self.assertEqual(params["env"], {"PYTHONPATH": "src"})
            self.assertEqual(params["args"], ["-m", "x.mcp"])


class PeerIsolation(unittest.TestCase):
    """A peer's transport may only reach that peer (the old code ran `k3dit <tool>` for everyone)."""

    def test_unwired_peer_never_borrows_another_server(self) -> None:
        with TemporaryDirectory() as d:
            ws = _ws(Path(d), {"mcpServers": {"k3dit": {"command": sys.executable, "args": ["-m", "k3dit.mcp"]}}}, PIPE_MCP_MANUAL)
            buf = io.StringIO()
            with mock.patch.object(pr, "call_mcp_tool") as fake:
                res = pr.run_action(ws, "k3lity.actions.quality", io=buf)  # not even declared -> not found
            self.assertFalse(res.ok)
            fake.assert_not_called()

    def test_k3lity_transport_targets_k3lity_endpoint(self) -> None:
        cfg = {
            "mcpServers": {
                "k3dit": {"command": "/usr/bin/false", "args": ["-m", "k3dit.mcp"]},
                "k3lity": {"command": "/usr/bin/false", "args": ["-m", "k3lity.mcp"]},
            }
        }
        pipe = """
[peers.k3lity]
[peers.k3lity.actions.quality]
transports = [ { provider = "mcp", tool = "k3lity_score", timeout = 5 } ]
"""
        with TemporaryDirectory() as d:
            ws = _ws(Path(d), cfg, pipe)
            seen = {}

            def fake(params, tool, arguments, timeout):
                seen["command"] = params["command"]
                seen["args"] = params["args"]
                seen["tool"] = tool
                return True, '{"ok": true}', ["k3lity_score"], ""

            with mock.patch.object(pr, "call_mcp_tool", side_effect=fake), mock.patch.object(
                pr, "resolve_endpoint_command", return_value=("/interp/python", "/interp/python")
            ):
                res = pr.run_action(ws, "k3lity.actions.quality", io=io.StringIO())
            self.assertTrue(res.ok, res.detail)
            self.assertEqual(seen["args"], ["-m", "k3lity.mcp"])  # NOT k3dit.mcp
            self.assertEqual(seen["tool"], "k3lity_score")
            self.assertEqual(res.provider, "mcp")


class DowngradeIsLoud(unittest.TestCase):
    def test_fallthrough_warns_prints_and_appends_the_audit_trail(self) -> None:
        cfg = {"mcpServers": {"k3dit": {"command": "python", "args": ["-m", "k3dit.mcp"]}}}
        with TemporaryDirectory() as d:
            ws = _ws(Path(d), cfg, PIPE_MCP_MANUAL)
            (ws / "logs").mkdir(parents=True, exist_ok=True)
            (ws / "logs" / "k3dge.log").write_text("PRE-EXISTING LINE\n", encoding="utf-8")
            buf = io.StringIO()
            with mock.patch.object(pr, "resolve_endpoint_command", return_value=("py", "py")), mock.patch.object(
                pr, "call_mcp_tool", return_value=(False, "MCPError: Connection closed", [], "")
            ):
                res = pr.run_action(ws, "k3dit.actions.audit", io=buf)
            out = buf.getvalue()
            self.assertIn("WARN[DOWNGRADE]", out)
            self.assertIn("mcp->manual", out)
            self.assertIn("Connection closed", out)  # reason, not a bare "fell through"
            self.assertIn("NOT an independent audit", out)  # manual must say what it is
            logged = (ws / "logs" / "k3dge.log").read_text(encoding="utf-8")
            self.assertIn("PRE-EXISTING LINE", logged)  # the trail is appended, not overwritten
            self.assertIn("WARN[DOWNGRADE]", logged)
            self.assertTrue(res.ok)  # manual is a legal landing spot
            self.assertEqual(res.downgrades, [r for r in res.downgrades])
            self.assertTrue(len(res.downgrades) >= 1)

    def test_skip_is_recorded(self) -> None:
        pipe = """
[peers.k3che]
transports = [ { provider = "mcp", tool = "k3che_search", timeout = 5 }, { provider = "skip" } ]
"""
        with TemporaryDirectory() as d:
            ws = _ws(Path(d), {"mcpServers": {}}, pipe)
            buf = io.StringIO()
            res = pr.run_action(ws, "k3che.search", io=buf)
            self.assertTrue(res.skipped)
            logged = (ws / "logs" / "k3dge.log").read_text(encoding="utf-8")
            self.assertIn("HARNESS_SKIP", logged)
            self.assertIn("WARN[DOWNGRADE] action=k3che.search mcp->skip", buf.getvalue())


class ArgumentsFlow(unittest.TestCase):
    def test_transport_args_and_caller_arguments_reach_the_tool(self) -> None:
        cfg = {"mcpServers": {"k3dit": {"command": "python", "args": ["-m", "k3dit.mcp"]}}}
        pipe = """
[peers.k3dit]
[peers.k3dit.actions.audit]
transports = [ { provider = "mcp", tool = "k3dit_run_audit", args = { target_scope = "code" }, timeout = 5 } ]
"""
        with TemporaryDirectory() as d:
            ws = _ws(Path(d), cfg, pipe)
            captured = {}

            def fake(params, tool, arguments, timeout):
                captured["arguments"] = arguments
                return True, "ok", [tool], ""

            with mock.patch.object(pr, "call_mcp_tool", side_effect=fake), mock.patch.object(
                pr, "resolve_endpoint_command", return_value=("py", "py")
            ):
                pr.run_action(ws, "k3dit.actions.audit", io=io.StringIO(), arguments={"pass_number": 3})
            self.assertEqual(captured["arguments"]["target_scope"], "code")  # from pipeline.toml
            self.assertEqual(captured["arguments"]["pass_number"], 3)  # from the caller
            # 契约 §1：不做隐式注入——只有调用方显式给出的事实会过线
            self.assertNotIn("workspace_path", captured["arguments"])


class ContractSurface(unittest.TestCase):
    def test_run_action_signature_stays_sync_and_documented(self) -> None:
        import inspect

        sig = inspect.signature(pr.run_action)
        self.assertEqual(
            list(sig.parameters), ["workspace", "action_ref", "io", "timeout_default", "arguments"]
        )

    def test_probe_reports_per_server_without_touching_the_gate(self) -> None:
        cfg = {"mcpServers": {"k3dit": {"command": "python", "args": ["-m", "k3dit.mcp"]}}}
        with TemporaryDirectory() as d:
            ws = _ws(Path(d), cfg, PIPE_MCP_MANUAL)
            with mock.patch.object(pr, "call_mcp_tool", return_value=(True, "", ["k3dit_run_audit"], "")), \
                 mock.patch.object(pr, "resolve_endpoint_command", return_value=("py", "py")):
                rows = pr.probe_servers(ws)
            self.assertEqual(len(rows), 1)
            name, ok, _detail, tools = rows[0]
            self.assertEqual((name, ok), ("k3dit", True))
            self.assertEqual(tools, ["k3dit_run_audit"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


class TestPayloadChannel(unittest.TestCase):
    def test_mcp_payload_is_untruncated_while_detail_is_a_preview(self) -> None:
        big = "x" * 5000
        with TemporaryDirectory() as d:
            ws = _ws(Path(d), {"mcpServers": {"k3dit": {"command": "python", "args": ["-m", "k3dit.mcp"]}}},
                     PIPE_MCP_MANUAL)
            with mock.patch.object(pr, "resolve_endpoint_command", return_value=("py", "py")), \
                 mock.patch.object(pr, "call_mcp_tool", return_value=(True, big, ["t"], "")):
                res = pr.run_action(ws, "k3dit.actions.audit", io=io.StringIO())
            self.assertTrue(res.ok)
            self.assertEqual(res.payload, big)
            self.assertIn("截断；完整响应见 payload", res.detail)
            self.assertLess(len(res.detail), len(big))

    def test_cli_payload_keeps_raw_stdout(self) -> None:
        pipe = """
[peers.k3dit]
[peers.k3dit.actions.audit]
transports = [ { provider = "cli", command = "printf hello", timeout = 5 } ]
"""
        with TemporaryDirectory() as d:
            ws = _ws(Path(d), {"mcpServers": {}}, pipe)
            res = pr.run_action(ws, "k3dit.actions.audit", io=io.StringIO())
            self.assertTrue(res.ok)
            self.assertEqual(res.payload, "hello")
