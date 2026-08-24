import unittest

from k3dge.engine import spec_schema

VALID = """# Domain Specification: core
## 1. Domain Boundary & Responsibilities
## 2. Public Interfaces & Type Contracts
## 3. State Machine & Invariants
## 4. Verification Matrix
"""


class TestSpecSchema(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(spec_schema.validate_structure(VALID), [])

    def test_missing_sections(self):
        errors = spec_schema.validate_structure("## 1. Domain Boundary\n")
        self.assertTrue(any("Public Interfaces" in e for e in errors))
        self.assertTrue(any("Verification Matrix" in e for e in errors))

    def test_extract_hash(self):
        content = "- **Contract Hash**: `sha256:" + "a" * 64 + "`"
        self.assertEqual(spec_schema.extract_contract_hash(content), "a" * 64)

    def test_no_hash(self):
        self.assertIsNone(spec_schema.extract_contract_hash("no hash here"))


if __name__ == "__main__":
    unittest.main()
