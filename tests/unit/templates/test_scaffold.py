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
        self.assertTrue((self.target / "docs" / "reference").is_dir())
        self.assertTrue((self.target / "docs" / "tasks").is_dir())
        self.assertTrue((self.target / "docs" / "tasks" / "README.md").exists())

        manifest = json.loads((self.target / ".agent" / "manifest.json").read_text())
        self.assertIn("domains", manifest)

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
            self.assertIn("ADR 0012", text)
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


if __name__ == "__main__":
    unittest.main()
