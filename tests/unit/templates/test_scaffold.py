import json
import os
import tempfile
import unittest
from pathlib import Path

from k3dge.templates.scaffold import scaffold


class TestScaffold(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.target = Path(self._tmp.name) / "project"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_generates_tree(self) -> None:
        scaffold(self.target)
        self.assertTrue((self.target / ".agent" / "manifest.json").exists())
        self.assertTrue((self.target / "AGENTS.md").exists())
        self.assertTrue((self.target / ".pre-commit-config.yaml").exists())
        self.assertTrue((self.target / "docs" / "specs" / "_template" / "spec.md").exists())
        self.assertTrue((self.target / "docs" / "adr").is_dir())
        self.assertTrue((self.target / "docs" / "tasks").is_dir())
        self.assertTrue((self.target / "docs" / "guides").is_dir())
        self.assertTrue((self.target / "docs" / "generated").is_dir())
        self.assertTrue((self.target / "docs" / "tasks").is_dir())
        self.assertTrue((self.target / "docs" / "tasks" / "README.md").exists())
        self.assertTrue((self.target / "docs" / "adr" / ".schema.json").is_file())
        self.assertTrue((self.target / "docs" / "adr" / "AUTHORING.md").is_file())
        self.assertTrue((self.target / "docs" / "tasks" / ".schema.json").is_file())
        self.assertTrue((self.target / "docs" / "tasks" / "AUTHORING.md").is_file())
        self.assertTrue((self.target / "docs" / "memo" / ".schema.json").is_file())
        self.assertTrue((self.target / "docs" / "branches" / ".schema.json").is_file())

        manifest = json.loads((self.target / ".agent" / "manifest.json").read_text())
        self.assertIn("domains", manifest)
        self.assertIn("project", manifest["domains"])
        self.assertTrue((self.target / "src" / "project" / "__init__.py").is_file())
        self.assertTrue((self.target / "docs" / "specs" / "project" / "spec.md").is_file())
        self.assertTrue((self.target / "docs" / "guides" / "mcp-bridge.md").is_file())
        self.assertTrue((self.target / "docs" / "guides" / "downstream.md").is_file())
        self.assertTrue((self.target / ".gitignore").is_file())
        reviews = (self.target / "docs" / "reviews" / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("2026-08-25-pass1", reviews)
        leftovers = self.target / "docs" / "reviews" / "LEFTOVERS.md"
        self.assertTrue(leftovers.is_file())
        self.assertNotIn("2026-08-25-pass1", leftovers.read_text(encoding="utf-8"))
        self.assertIn("LEFTOVERS.md", reviews)

        readme = self.target / ".agent" / "README.md"
        self.assertTrue(readme.exists())
        self.assertIn("机器配置目录", readme.read_text(encoding="utf-8"))

        for name in (
            "00-core-discipline.md",
            "01-docs-structure.md",
            "02-simplification.md",
            "03-self-contained.md",
        ):
            path = self.target / ".agent" / "rules" / name
            self.assertTrue(path.exists(), name)
            text = path.read_text(encoding="utf-8")
            self.assertGreater(len(text.strip()), 80, name)
            self.assertIn("ADR-0010", text)
        two = (self.target / ".agent" / "rules" / "02-simplification.md").read_text()
        self.assertIn("procedural discipline", two)
        zero = (self.target / ".agent" / "rules" / "00-core-discipline.md").read_text().strip()
        self.assertNotEqual(zero, "# Rule 00: Core Discipline")

    def test_scripts_are_executable(self) -> None:
        scaffold(self.target)
        gate = self.target / "scripts" / "gate.sh"
        init = self.target / "k3dge-init.sh"
        self.assertTrue(os.access(gate, os.X_OK))
        self.assertTrue(os.access(init, os.X_OK))

    def test_idempotent(self) -> None:
        scaffold(self.target)
        agents = self.target / "AGENTS.md"
        agents.write_text("custom")
        scaffold(self.target)
        self.assertEqual(agents.read_text(), "custom")

    def test_empty_manifest_upgraded_to_first_domain(self) -> None:
        (self.target / ".agent").mkdir(parents=True)
        (self.target / ".agent" / "manifest.json").write_text(
            json.dumps(
                {
                    "name": "project",
                    "version": "0.1.0",
                    "package_root": "src",
                    "domains": {},
                    "ignore": [],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        scaffold(self.target, name="k3dit")
        data = json.loads((self.target / ".agent" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(data["name"], "k3dit")
        self.assertIn("k3dit", data["domains"])
        self.assertTrue((self.target / "src" / "k3dit" / "__init__.py").is_file())

    def test_pipeline_peers_declared_so_birth_not_red(self) -> None:
        """item 3：scaffold 把 pipeline 绑定的 peer 以 stub 写进 .mcp.json，出生不报 PIPELINE_PEER_UNWIRED。"""
        from k3dge.engine.pipeline_schema import validate_pipeline_config

        scaffold(self.target)
        servers = json.loads((self.target / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
        self.assertIn("k3dge", servers)
        self.assertIn("k3dit", servers)  # pipeline 绑定的 peer 已登记
        self.assertIn("k3che", servers)
        codes = [c for c, _ in validate_pipeline_config(self.target)]
        self.assertNotIn("PIPELINE_PEER_UNWIRED", codes, validate_pipeline_config(self.target))


if __name__ == "__main__":
    unittest.main()
