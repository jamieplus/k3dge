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




def test_only_canonical_headings_satisfy_sections() -> None:
    """`### Sub-domain Boundary Notes` 不得顶掉正式节（block 闸假绿，ocr-322）。"""
    bogus = ("# Spec\n\n### Sub-domain Boundary Notes\n\n### Interfaces Overview\n"
             "\n### Verify Matrix\n")
    errs = spec_schema.validate_structure(bogus)
    assert len(errs) == 3, errs
    ok = ("# Spec\n\n## 1. Domain Boundary & Responsibilities\n\n"
          "## 2. Public Interfaces & Type Contracts\n\n## 4. Verification Matrix\n")
    assert spec_schema.validate_structure(ok) == []


def test_hash_must_be_exactly_64_hex() -> None:
    # 两个 digest 连写（128 位）不得被静默截成合法 64 位（ocr-323）
    assert spec_schema.extract_contract_hash(f"- **Contract Hash**: sha256:{'a'*128}") is None
    assert spec_schema.extract_contract_hash(f"- **Contract Hash**: sha256:{'a'*64}") == "a" * 64


def test_hash_case_normalized_to_lowercase() -> None:
    # 正则 IGNORECASE，但下游全与小写 hexdigest 比（ocr-324）
    assert spec_schema.extract_contract_hash(
        f"- **Contract Hash**: sha256:{'A'*64}") == "a" * 64


if __name__ == "__main__":
    unittest.main()
