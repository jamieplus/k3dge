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
    """旁节/带尾巴的标题不得顶掉正式节（block 闸假绿，ocr-322；t-248）。

    旧测喂的是 `### Sub-domain…`——那**本来**就不匹配行锚定前缀，绿灯给的是虚假安心；
    真会骗过旧判据（关键词短写 + `#{2,3}`）的是这两形：`## Domain Boundary Draft Notes`
    （短词后接空白＝旧 `Domain Boundary\b` 成立）与子级 `### 1. …全名…`。
    判据升到"全名 + 仅 `##`"后，这两种**必须**各被记一次 missing。
    """
    # ① 短词 + 尾巴：旧判据会当 §1 已满足
    draft = ("# Spec\n\n## Domain Boundary Draft Notes\n\n"
             "## Public Interfaces\n\n## Verify Matrix\n")
    assert len(spec_schema.validate_structure(draft)) == 3, spec_schema.validate_structure(draft)
    # ② 子级标题顶正式节：旧 `#{2,3}` 会认
    sub = ("# Spec\n\n### 1. Domain Boundary & Responsibilities\n\n"
           "### 2. Public Interfaces & Type Contracts\n\n### 4. Verification Matrix\n")
    assert len(spec_schema.validate_structure(sub)) == 3, spec_schema.validate_structure(sub)
    ok = ("# Spec\n\n## 1. Domain Boundary & Responsibilities\n\n"
          "## 2. Public Interfaces & Type Contracts\n\n## 4. Verification Matrix\n")
    assert spec_schema.validate_structure(ok) == []


def test_section_three_is_not_machine_enforced() -> None:
    """t-249：§3（State Machine & Invariants）**有意**不进 block 机检集——模板 ship 四节，
    `validate_structure` 只锚定 interfaces/matrix/boundary 三处结构闸。旧 `ok` 夹具漏 §3
    仍绿，把这条沉默约定**锁成了缺陷**；这里把它摊开成显式断言（要机检 §3 的人先改这里）。
    """
    no_three = ("# Spec\n\n## 1. Domain Boundary & Responsibilities\n\n"
                "## 2. Public Interfaces & Type Contracts\n\n## 4. Verification Matrix\n")
    assert spec_schema.validate_structure(no_three) == []   # §3 缺席：不报（当前约定）
    # 对照：真正必需三节缺一个就要报——证明上面不是"永远返回空"的假绿
    assert len(spec_schema.validate_structure(
        "# Spec\n\n## 2. Public Interfaces & Type Contracts\n\n## 4. Verification Matrix\n")) == 1


def test_hash_must_be_exactly_64_hex() -> None:
    """两侧边界都要钉（t-250）：`{64}` 松成 `{64,}`、或去掉尾部的负向前瞻，
    旧测（只喂 128 与整 64）都看不见——63/65/非 hex 正是 CONTRACT_DRIFT 与
    hexdigest() 比对会撞上的形状。"""
    assert spec_schema.extract_contract_hash(f"- **Contract Hash**: sha256:{'a'*128}") is None
    assert spec_schema.extract_contract_hash(f"- **Contract Hash**: sha256:{'a'*64}") == "a" * 64
    for bad in ("a" * 63, "a" * 65, "g" * 64, "a" * 32):   # 截短/超长/非 hex（大小写混不算拒）
        assert spec_schema.extract_contract_hash(f"- **Contract Hash**: sha256:{bad}") is None, bad


def test_hash_case_normalized_to_lowercase() -> None:
    # 正则 IGNORECASE，但下游全与小写 hexdigest 比（ocr-324）
    assert spec_schema.extract_contract_hash(
        f"- **Contract Hash**: sha256:{'A'*64}") == "a" * 64


if __name__ == "__main__":
    unittest.main()
