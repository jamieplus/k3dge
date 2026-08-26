import json
import tempfile
import unittest
from pathlib import Path

from k3dge.engine import contract
from k3dge.engine.manifest import Manifest
from k3dge.sync.generator import render_readme_layout, sync_all

SPEC = """# Domain Specification: core
- **Status**: Active
- **Module Path**: `src/core`
- **Contract Hash**:
- **Last Updated**: 2026-08-19
## 1. Domain Boundary & Responsibilities
## 2. Public Interfaces & Type Contracts
<!-- k3dge:interfaces-start -->
```python
```
<!-- k3dge:interfaces-end -->
## 3. State Machine & Invariants
## 4. Verification Matrix
"""


class TestGenerator(unittest.TestCase):
    def test_sync_writes_hash_and_interface(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".agent").mkdir()
            (root / ".agent" / "manifest.json").write_text(
                json.dumps(
                    {
                        "package_root": "src",
                        "domains": {
                            "core": {"src": "src/core", "spec": "docs/specs/core/spec.md"}
                        },
                        "ignore": [],
                    }
                )
            )
            (root / "src" / "core").mkdir(parents=True)
            (root / "src" / "core" / "mod.py").write_text(
                "def foo(x: int) -> int:\n    return x\n"
            )
            (root / "docs" / "specs" / "core").mkdir(parents=True)
            spec = root / "docs" / "specs" / "core" / "spec.md"
            spec.write_text(SPEC)

            changed, docs_updated = sync_all(root)
            self.assertEqual(changed, ["core"])
            # manual docs are machine-generated under docs/reference/ (no agent needed)
            self.assertTrue(docs_updated)
            self.assertTrue((root / "docs/reference/api.md").exists())
            self.assertTrue((root / "docs/reference/domains.md").exists())

            content = spec.read_text()
            iface = contract.collect_domain_interface(root / "src" / "core")
            h = contract.compute_hash(iface)
            self.assertIn(f"sha256:{h}", content)
            self.assertNotIn("# mod.py", content)
            self.assertIn("foo(x: int) -> int", content)
            api = (root / "docs/reference/api.md").read_text()
            self.assertIn("# mod.py", api)

    def test_render_readme_layout(self) -> None:
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
                                "description": "核心模块",
                            }
                        },
                        "ignore": [],
                    }
                )
            )
            readme = root / "README.md"
            readme.write_text(
                "# T\n\n## 布局\n\n<!-- k3dge:layout-start -->\nold content\n<!-- k3dge:layout-end -->\n"
            )

            manifest = Manifest.load(root)
            result = render_readme_layout(root, manifest)
            self.assertEqual(result, readme)
            content = readme.read_text()
            self.assertIn("| core | `src/core` | `docs/specs/core/spec.md` | 核心模块 |", content)
            self.assertNotIn("old content", content)

            self.assertIsNone(render_readme_layout(root, manifest))


if __name__ == "__main__":
    unittest.main()
