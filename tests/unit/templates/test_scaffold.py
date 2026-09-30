import json
import os
import tempfile
import unittest
from pathlib import Path

from k3dge.templates.scaffold import scaffold




class TestScaffoldProblemsChannel(unittest.TestCase):
    """脚手架的失败必须有通道：执行位可补、坏输入出声、用户键不被抹（ocr-368..372）。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.target = Path(self._tmp.name) / "p"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_exec_bit_is_restored_on_existing_file(self) -> None:
        from k3dge.templates.scaffold import _write_if_missing

        self.target.mkdir(parents=True)
        f = self.target / "scripts" / "gate.sh"
        f.parent.mkdir(parents=True)
        f.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        f.chmod(0o644)                      # 跨_fs/checkout 丢 mode
        _write_if_missing(f, "别的\n", executable=True)
        self.assertTrue(os.stat(f).st_mode & 0o111, "重复跑 init 永远修不回执行位")
        self.assertEqual(f.read_text(encoding="utf-8"), "#!/usr/bin/env bash\n")   # 内容仍不动

    def test_manifest_problems_come_back_in_the_channel(self) -> None:
        from k3dge.templates.scaffold import scaffold

        (self.target / ".agent").mkdir(parents=True)
        (self.target / ".agent" / "manifest.json").write_text("{ 坏 json", encoding="utf-8")
        problems = scaffold(self.target, name="p")
        self.assertTrue([m for m in problems if "manifest.json" in m], problems)

    def test_user_keys_survive_domain_upgrade(self) -> None:
        from k3dge.templates.scaffold import scaffold

        (self.target / ".agent").mkdir(parents=True)
        (self.target / ".agent" / "manifest.json").write_text(json.dumps({
            "name": "old", "package_root": "lib", "ignore": ["vendor/**"],
            "version": "9.9.9", "self_hosting": True, "domains": {}}) + "\n", encoding="utf-8")
        self.assertEqual(scaffold(self.target, name="p"), [])
        data = json.loads((self.target / ".agent" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(data["package_root"], "lib")
        self.assertEqual(data["ignore"], ["vendor/**"])
        self.assertEqual(data["version"], "9.9.9")
        self.assertTrue(data["self_hosting"])
        self.assertIn("p", data["domains"])

    def test_corrupt_mcp_json_is_a_problem(self) -> None:
        from k3dge.templates.scaffold import scaffold

        self.target.mkdir(parents=True)
        (self.target / ".mcp.json").write_text("{ nope", encoding="utf-8")
        problems = scaffold(self.target, name="p")
        self.assertTrue([m for m in problems if ".mcp.json" in m], problems)
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
