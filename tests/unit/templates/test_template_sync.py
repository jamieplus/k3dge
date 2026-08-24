import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
ASSETS = ROOT / "src/k3dge/templates/assets"

PAIRS = [
    ("gate.py", "scripts/gate.py"),
    ("gate.sh", "scripts/gate.sh"),
    ("init.sh", "scripts/init.sh"),
    ("generate-docs.sh", "scripts/generate-docs.sh"),
    ("generate-docs.ps1", "scripts/generate-docs.ps1"),
    ("gate.ps1", "scripts/gate.ps1"),
    ("init.ps1", "scripts/init.ps1"),
    ("k3dge-init-wrapper.sh", "k3dge-init.sh"),
    ("k3dge-init-wrapper.ps1", "k3dge-init.ps1"),
    ("agents.md", "AGENTS.md"),
    ("agent-readme.md", ".agent/README.md"),
    ("rules/00-core-discipline.md", ".agent/rules/00-core-discipline.md"),
    ("rules/01-docs-structure.md", ".agent/rules/01-docs-structure.md"),
    ("rules/02-simplification.md", ".agent/rules/02-simplification.md"),
    ("rules/03-self-contained.md", ".agent/rules/03-self-contained.md"),
]


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
            "architecture.md.template",
            "reviews-readme.md",
            "tasks-readme.md",
            "branches-readme.md",
            "memo-readme.md",
            "rules/00-core-discipline.md",
            "rules/01-docs-structure.md",
            "rules/02-simplification.md",
            "rules/03-self-contained.md",
            "agent-readme.md",
        ]
        for name in expected:
            with self.subTest(asset=name):
                self.assertTrue((ASSETS / name).exists(), f"missing asset {name}")


if __name__ == "__main__":
    unittest.main()
