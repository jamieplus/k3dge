import pathlib
import unittest

from k3dge.engine.pairs import PAIRS

ROOT = pathlib.Path(__file__).resolve().parents[3]
ASSETS = ROOT / "src/k3dge/templates/assets"


class TestTemplateSync(unittest.TestCase):
    """Assets in src/k3dge/templates/assets must stay identical to the repo's own scripts."""

    def test_templates_match_repo_scripts(self) -> None:
        for asset, rel in PAIRS:
            with self.subTest(asset=asset):
                tpl = (ASSETS / asset).read_text().rstrip("\n")
                act = (ROOT / rel).read_text().rstrip("\n")
                self.assertEqual(tpl, act, f"{asset} drifted from {rel}")

    def test_all_expected_assets_exist(self) -> None:
        expected = [
            "agents.md",
            "spec.md.template",
            "pre-commit.yaml.template",
            "docs.toml.template",
            "pipeline.toml.template",
            "architecture.md.template",
            "reviews-readme.md",
            "mcp-bridge.md.template",
            "downstream.md",
            "gitignore.template",
            "pre-commit-sentinel.sh",
            "tasks-readme.md",
            "branches-readme.md",
            "memo-readme.md",
            "rules/00-core-discipline.md",
            "rules/01-docs-structure.md",
            "rules/02-simplification.md",
            "rules/03-self-contained.md",
            "rules/04-milestone.md",
            "rules/05-branches.md",
            "rules/06-memo.md",
            "rules/07-audit.md",
            "rules/09-absorption.md",
            "agent-readme.md",
            "protocols/audit_default.md",
            "protocols/verify_default.md",
            "protocols/adr_default.md",
            "protocols/incident_default.md",
            "protocols/task_default.md",
            "protocols/meta_protocol.md",
        ]
        for name in expected:
            with self.subTest(asset=name):
                self.assertTrue((ASSETS / name).exists(), f"missing asset {name}")


if __name__ == "__main__":
    unittest.main()
