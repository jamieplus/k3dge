import json
import tempfile
import unittest
from pathlib import Path

from k3dge.cli import mcp


class TestMcp(unittest.TestCase):
    def test_manifest_missing_is_error_json(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            payload = json.loads(mcp.get_manifest_resource_for(Path(d)))
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"], "ManifestNotFound")

    def test_invalid_milestone_action(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            payload = json.loads(
                mcp.k3dge_milestone_control("explode", "M1", workspace_path=d)
            )
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"], "InvalidAction")

    def test_domain_spec_unregistered(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".agent").mkdir()
            (root / ".agent" / "manifest.json").write_text(
                json.dumps({"package_root": "src", "domains": {}})
            )
            payload = json.loads(mcp.get_domain_spec_resource_for("nope", Path(d)))
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"], "DomainNotRegistered")

    def test_verify_collects_once(self) -> None:
        import unittest.mock as mock

        from k3dge.engine import contract as contract_mod

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".agent").mkdir()
            (root / ".agent" / "manifest.json").write_text(
                json.dumps(
                    {
                        "package_root": "src",
                        "domains": {
                            "core": {
                                "src": "src/core",
                                "spec": "docs/specs/core/spec.md",
                            }
                        },
                    }
                )
            )
            (root / "src/core").mkdir(parents=True)
            (root / "docs/specs/core").mkdir(parents=True)
            (root / "src/core/mod.py").write_text("def foo() -> int:\n    return 1\n")
            iface = contract_mod.collect_domain_interface(root / "src/core")
            h = contract_mod.compute_hash(iface)
            (root / "docs/specs/core/spec.md").write_text(
                f"**Contract Hash**: `sha256:{h}`\n", encoding="utf-8"
            )
            calls = {"n": 0}
            real = contract_mod.collect_domain_interface

            def wrapped(*a, **k):
                calls["n"] += 1
                return real(*a, **k)

            with mock.patch(
                "k3dge.engine.contract.collect_domain_interface", side_effect=wrapped
            ):
                payload = json.loads(
                    mcp.k3dge_verify_domain_contract("core", workspace_path=d)
                )
            self.assertTrue(payload["ok"])
            self.assertEqual(calls["n"], 1)

    def test_task_list_json(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".agent").mkdir()
            (root / ".agent" / "manifest.json").write_text(
                json.dumps({"package_root": "src", "domains": {}})
            )
            (root / "docs" / "tasks").mkdir(parents=True)
            (root / "docs" / "tasks" / "open.md").write_text(
                "# Open item\n- **Status**: deferred\n- **Priority**: P3\n",
                encoding="utf-8",
            )
            payload = json.loads(mcp.k3dge_task_list(workspace_path=d, status="deferred"))
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["count"], 1)
            self.assertEqual(payload["tasks"][0]["title"], "Open item")
            self.assertEqual(payload["tasks"][0]["priority"], "P3")
            empty = json.loads(mcp.k3dge_task_list(workspace_path=d, milestone_id="M9"))
            self.assertEqual(empty["count"], 0)

    def test_sync_and_task_create_done(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".agent").mkdir()
            (root / ".agent" / "manifest.json").write_text(
                json.dumps({"package_root": "src", "domains": {}, "name": "t", "version": "0.1.0"})
            )
            (root / "docs" / "tasks").mkdir(parents=True)
            sync_payload = json.loads(mcp.k3dge_sync(workspace_path=d))
            self.assertTrue(sync_payload["ok"])
            created = json.loads(
                mcp.k3dge_task_create("Wire MCP sync", typ="feat", workspace_path=d)
            )
            self.assertTrue(created["ok"], created)
            path = created["path"]
            self.assertTrue((root / path).is_file())
            done = json.loads(mcp.k3dge_task_done(path, workspace_path=d))
            self.assertTrue(done["ok"], done)
            self.assertTrue(str(done["path"]).endswith(".done.md"))
            ver = json.loads(mcp.k3dge_version(action="show", workspace_path=d))
            self.assertTrue(ver["ok"])
            self.assertEqual(ver["version"], "0.1.0")

    def test_align_payload_no_checkpoint(self) -> None:
        import subprocess

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".agent").mkdir()
            (root / ".agent" / "manifest.json").write_text(
                json.dumps({"package_root": "src", "domains": {"k": {"src": "src/k", "spec": "docs/specs/k/spec.md", "tests": "tests/unit/k"}}}),
            )
            (root / "src/k").mkdir(parents=True)
            (root / "docs/specs/k").mkdir(parents=True)
            (root / "src/k/mod.py").write_text("def foo() -> int:\n    return 1\n")
            from k3dge.engine import contract

            iface = contract.collect_domain_interface(root / "src/k")
            h = contract.compute_hash(iface)
            (root / "docs/specs/k/spec.md").write_text(
                f"# Domain Specification: k\n- **Status**: Active\n- **Module Path**: `src/k`\n- **Contract Hash**: `sha256:{h}`\n- **Last Updated**: 2026-08-25\n"
                "## 1. Domain Boundary & Responsibilities\n## 2. Public Interfaces & Type Contracts\n"
                "<!-- k3dge:interfaces-start -->\n```python\n" + iface + "\n```\n<!-- k3dge:interfaces-end -->\n"
                "## 3. State Machine & Invariants\n## 4. Verification Matrix\n| TC-1 | L1 | x | y | `tests/unit/k/test_foo.py` |\n",
                encoding="utf-8",
            )
            (root / "tests/unit/k").mkdir(parents=True)
            (root / "tests/unit/k/test_foo.py").write_text("def test_foo():\n    assert True\n")
            (root / "docs" / "tasks").mkdir(parents=True)
            (root / "docs" / "tasks" / "2026-08-25-M9-audit-foo.md").write_text(
                "# Foo\n- **Status**: done\n- **Milestone**: M9\n", encoding="utf-8"
            )
            (root / "docs" / "reviews").mkdir(parents=True)
            subprocess.run(["git", "init", "-b", "main"], cwd=root, capture_output=True)
            subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=root, capture_output=True)
            subprocess.run(["git", "config", "user.name", "t"], cwd=root, capture_output=True)
            subprocess.run(["git", "add", "-A"], cwd=root, capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=root, capture_output=True)
            payload = json.loads(mcp.k3dge_milestone_control("align", "M9", workspace_path=d))
            self.assertTrue(payload["aligned"], payload)
            # align no longer carries a checkpoint nor "seal_eligible"; 预审（形式闸）全绿时
            # 下一步就是 seal（审计由 seal 相位 2 自己跑，ADR-0004 §2.1.9）。
            self.assertNotIn("checkpoint", payload)
            self.assertNotIn("seal_eligible", payload)
            self.assertIn("next", payload)
            self.assertEqual(payload["next"]["state"], "seal_ready")


class TestAuditPromptRouting(unittest.TestCase):
    def test_is_doc_scope(self) -> None:
        self.assertTrue(mcp._is_doc_scope("docs/adr/0001.md"))
        self.assertTrue(mcp._is_doc_scope("adr"))
        self.assertTrue(mcp._is_doc_scope("tasks/foo.md"))
        self.assertFalse(mcp._is_doc_scope("src/k3dge/engine/doc_catalog.py"))
        self.assertFalse(mcp._is_doc_scope(""))
        self.assertFalse(mcp._is_doc_scope("k3dge/cli/main.py"))

    def test_doc_scope_routes_to_doc_audit_section(self) -> None:
        out = mcp.k3dge_5pass_audit_prompt(2, "docs/adr/0001.md", "snip")
        self.assertIn("Doc Audit section", out)
        self.assertNotIn("Execute only Pass 2", out)

    def test_code_scope_routes_to_5pass(self) -> None:
        out = mcp.k3dge_5pass_audit_prompt(3, "src/k3dge/engine/doc_catalog.py", "snip")
        self.assertIn("Execute only Pass 3", out)
        self.assertNotIn("Doc Audit section", out)


if __name__ == "__main__":
    unittest.main()


def test_server_alive_under_mcp2():
    """mcp 2.x 下 k3dge 入向面必须真活着（曾因 resource 严格校验落回 _DummyMCP 而长期 DEAD）。"""
    import asyncio

    import k3dge.cli.mcp as km

    if km.FastMCP is None or type(km.mcp).__name__ == "_DummyMCP":
        import pytest

        pytest.skip("mcp package not installed in this env")
    tools = {x.name for x in asyncio.run(km.mcp.list_tools())}
    assert "k3dge_check" in tools and "k3dge_status" in tools, tools
    uris = {r.uri for r in asyncio.run(km.mcp.list_resources())}
    assert "spec://manifest" in uris, uris


class TestMcpExitIsomorphism(unittest.TestCase):
    def test_check_and_task_list_carry_same_next(self) -> None:
        import unittest.mock as mock

        from k3dge.cli import status as status_mod
        from k3dge.engine import nextstep

        ns = nextstep.NextStep.from_state("audit_suggested", "M1", reasons=["x"])
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".agent").mkdir()
            (root / ".agent" / "manifest.json").write_text(
                json.dumps({"package_root": "src", "domains": {}})
            )
            with mock.patch.object(status_mod, "lifecycle_next", return_value=ns):
                chk = json.loads(mcp.k3dge_check(workspace_path=d))
                tl = json.loads(mcp.k3dge_task_list(workspace_path=d))
        self.assertEqual(chk["next"], ns.render_mcp())
        self.assertEqual(tl["next"], ns.render_mcp())
