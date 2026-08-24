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


if __name__ == "__main__":
    unittest.main()
