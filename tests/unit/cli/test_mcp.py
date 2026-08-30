import json
import tempfile
import unittest
from pathlib import Path

from k3dge.cli import mcp


class TestMcp(unittest.TestCase):
    def test_manifest_missing_is_error_json(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            payload = json.loads(mcp.get_manifest_resource(workspace_path=d))
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"], "ManifestNotFound")

    def test_invalid_milestone_action(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            payload = json.loads(
                mcp.k3dge_milestone_control("explode", "M1", workspace_path=d)
            )
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"], "InvalidAction")

    def test_protocol_resolve_returns_content(self) -> None:
        root = Path(__file__).resolve().parents[3]
        payload = json.loads(mcp.k3dge_protocol_resolve("audit", workspace_path=str(root)))
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["task_type"], "audit")
        self.assertTrue(payload["exists"])
        self.assertIn("Audit Protocol", payload["content"])

    def test_protocol_resource_unknown_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            payload = json.loads(mcp.get_protocol_resource("nope", workspace_path=d))
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"], "ProtocolNotFound")

    def test_protocol_resolve_by_path_returns_content(self) -> None:
        root = Path(__file__).resolve().parents[3]
        target = str(root / "docs/reviews/2026-08-27-sample.md")
        payload = json.loads(mcp.k3dge_protocol_resolve(path=target, workspace_path=str(root)))
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["task_type"], "audit")
        self.assertIn("Audit Protocol", payload["content"])

    def test_protocol_resolve_by_path_no_match(self) -> None:
        root = Path(__file__).resolve().parents[3]
        target = str(root / "src/k3dge/cli/main.py")
        payload = json.loads(mcp.k3dge_protocol_resolve(path=target, workspace_path=str(root)))
        self.assertTrue(payload["ok"])
        self.assertIsNone(payload["task_type"])
        self.assertFalse(payload["exists"])

    def test_protocol_challenge_required_for_reviews(self) -> None:
        root = Path(__file__).resolve().parents[3]
        target = str(root / "docs/reviews/2026-08-27-sample.md")
        payload = json.loads(
            mcp.k3dge_protocol_challenge(path=target, task_id="T1", workspace_path=str(root))
        )
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["required"])
        self.assertEqual(len(payload["challenge"]), 12)

    def test_protocol_challenge_not_required_for_src(self) -> None:
        root = Path(__file__).resolve().parents[3]
        target = str(root / "src/k3dge/cli/main.py")
        payload = json.loads(
            mcp.k3dge_protocol_challenge(path=target, task_id="T1", workspace_path=str(root))
        )
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["required"])
        self.assertIsNone(payload["challenge"])

    def test_protocol_ticket_returns_checklist(self) -> None:
        root = Path(__file__).resolve().parents[3]
        target = str(root / "docs/reviews/2026-08-27-sample.md")
        payload = json.loads(mcp.k3dge_protocol_ticket(path=target, workspace_path=str(root)))
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["required"])
        self.assertTrue(any("12" in c for c in payload["constraints"]))

    def test_protocol_ticket_validation_catches_missing(self) -> None:
        root = Path(__file__).resolve().parents[3]
        target = str(root / "docs/reviews/2026-08-27-sample.md")
        ticket = {"protocol": "audit", "task_id": "T1", "binding": []}
        payload = json.loads(mcp.k3dge_protocol_ticket(path=target, ticket=ticket, workspace_path=str(root)))
        self.assertFalse(payload["ok"])
        self.assertTrue(payload["errors"])

    def test_protocol_verify_soft_gate_advise(self) -> None:
        root = Path(__file__).resolve().parents[3]
        target = str(root / "docs/reviews/2026-08-27-sample.md")
        payload = json.loads(mcp.k3dge_protocol_verify(path=target, task_id="T1", workspace_path=str(root)))
        self.assertEqual(payload["verdict"], "advise")
        self.assertIn("remediation", payload)

    def test_protocol_report_writes_incident(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".agent").mkdir()
            (root / ".agent" / "manifest.json").write_text("{}")
            payload = json.loads(
                mcp.k3dge_protocol_report(
                    detail="agent ignored the gate", path="docs/reviews/x.md", task_type="audit", workspace_path=d
                )
            )
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["incident"].endswith(".md"))

    def test_domain_spec_unregistered(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".agent").mkdir()
            (root / ".agent" / "manifest.json").write_text(
                json.dumps({"package_root": "src", "domains": {}})
            )
            payload = json.loads(mcp.get_domain_spec_resource("nope", workspace_path=d))
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

    def test_align_checkpoint_payload(self) -> None:
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
            self.assertIn("checkpoint", payload)
            self.assertEqual(payload["checkpoint"]["timeout_seconds"], 60)
            self.assertEqual(payload["checkpoint"]["default"], "N")


if __name__ == "__main__":
    unittest.main()
