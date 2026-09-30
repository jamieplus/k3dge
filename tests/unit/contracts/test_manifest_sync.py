"""Full-consistency contract: manifest domains <-> docs/specs directories.

The evaluator only checks *touched* domains; this test asserts the FULL 1:1
mapping at CI time so drift (missing spec / orphan spec dir / missing tests
dir) is caught even when nothing in that domain was touched.
"""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / ".agent" / "manifest.json"
SPECS_DIR = ROOT / "docs" / "specs"


class TestManifestSpecsFullSync(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        # `domains` 缺失/被改名/被清空时旧写法静默回落 `{}` ⇒ 三条逐域断言全部空转仍报绿，
        # 而本文件的存在理由恰恰是抓"没人动的域漂了"（t-029）。空集必须是**红**。
        dom = self.manifest.get("domains")
        self.assertIsInstance(dom, dict, f"manifest.domains 不是对象：{type(dom).__name__}")
        self.assertTrue(dom, ".agent/manifest.json 的 domains 为空 ⇒ 本文件的 1:1 一致性核判空转")
        self.domains = dom

    def test_manifest_is_present(self) -> None:
        self.assertTrue(MANIFEST.exists(), ".agent/manifest.json missing")

    def test_every_domain_has_all_registered_paths(self) -> None:
        for domain, cfg in self.domains.items():
            with self.subTest(domain=domain):
                for key in ("src", "spec", "tests"):
                    self.assertIn(key, cfg, f"domain '{domain}' missing '{key}'")
                    path = ROOT / cfg[key]
                    self.assertTrue(path.exists(), f"domain '{domain}' {key} path missing: {cfg[key]}")

    def test_every_domain_has_spec_dir(self) -> None:
        for domain, cfg in self.domains.items():
            spec_dir = (ROOT / cfg["spec"]).parent
            self.assertTrue(
                spec_dir.is_dir(), f"domain '{domain}' spec dir missing: {spec_dir}"
            )

    def test_no_orphan_spec_dirs(self) -> None:
        registered = {(ROOT / cfg["spec"]).parent.name for cfg in self.domains.values()}
        actual = {p.name for p in SPECS_DIR.iterdir() if p.is_dir() and p.name != "_template"}
        orphans = actual - registered
        self.assertEqual(orphans, set(), f"spec dirs without manifest domain: {sorted(orphans)}")

    def test_spec_files_have_required_sections_and_hash(self) -> None:
        from k3dge.engine import spec_schema

        for domain, cfg in self.domains.items():
            with self.subTest(domain=domain):
                content = (ROOT / cfg["spec"]).read_text(encoding="utf-8")
                self.assertEqual(
                    spec_schema.validate_structure(content),
                    [],
                    f"spec for '{domain}' missing required sections",
                )
                self.assertIsNotNone(
                    spec_schema.extract_contract_hash(content),
                    f"spec for '{domain}' has no contract hash (run 'k3dge sync')",
                )


if __name__ == "__main__":
    unittest.main()
