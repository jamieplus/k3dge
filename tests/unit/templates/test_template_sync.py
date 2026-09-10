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
            "tasks-readme.md",
            "tasks/_template.md",
            "branches-readme.md",
            "branches/_template.md",
            "memo-readme.md",
            "memo/_template.md",
            "adr/_template.md",
            "adr/AUTHORING.md",
            "adr/.schema.json",
            "tasks/AUTHORING.md",
            "memo/AUTHORING.md",
            "branches/AUTHORING.md",
            "incidents/AUTHORING.md",
            "reviews/AUTHORING.md",
            "reviews/LEFTOVERS.md",
            "tasks/.schema.json",
            "memo/.schema.json",
            "branches/.schema.json",
            "incidents/.schema.json",
            "rules/00-core-discipline.md",
            "rules/01-docs-structure.md",
            "rules/02-simplification.md",
            "rules/03-self-contained.md",
            "rules/04-milestone.md",
            "rules/05-branches.md",
            "rules/06-memo.md",
            "rules/07-audit.md",
            "rules/09-absorption.md",
            "rules/10-structure-over-prose.md",
            "agent-readme.md",
            "protocols/audit_default.md",
            "protocols/verify_default.md",
        ]
        for name in expected:
            with self.subTest(asset=name):
                self.assertTrue((ASSETS / name).exists(), f"missing asset {name}")


if __name__ == "__main__":
    unittest.main()
