"""L0 structural validation of spec files."""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

#: 必需节：标题**锚定**（只允许可选编号前缀 + 可选尾注）。`.*关键词` 的"任意位置包含"
#: 会让 `### Sub-domain Boundary Notes` / `## Domain Boundary Draft Notes` 之类的旁节
#: 顶掉正式节，而 `SPEC_MISSING_SECTION` 是 block 闸 ⇒ 假绿（322）。
_HEADING_PREFIX = r"^#{2,3}[ \t]+(?:\d+[.)]?[ \t]+)?"
REQUIRED_SECTIONS: List[Tuple[str, "re.Pattern[str]"]] = [
    ("Domain Boundary & Responsibilities",
     re.compile(_HEADING_PREFIX + r"Domain Boundary\b", re.MULTILINE)),
    ("Public Interfaces & Type Contracts",
     re.compile(_HEADING_PREFIX + r"Public Interfaces\b", re.MULTILINE)),
    ("Verification Matrix",
     re.compile(_HEADING_PREFIX + r"Verification Matrix\b", re.MULTILINE)),
]

#: 64 位摘要必须**整串**匹配：`{64}` 无边界断言时，128 位（两个 digest 连写/复制多尾字符）
#: 会被静默截成合法 64 位，回执显示的是被截断的值（323）。
CONTRACT_HASH_RE = re.compile(
    r"\*\*Contract Hash\*\*:\s*`?sha256:([0-9a-f]{64})(?![0-9a-f])`?",
    re.IGNORECASE)


def validate_structure(content: str) -> List[str]:
    errors: List[str] = []
    for name, pattern in REQUIRED_SECTIONS:
        if not pattern.search(content):
            errors.append(f"missing required section '{name}'")
    return errors


def extract_contract_hash(content: str) -> Optional[str]:
    match = CONTRACT_HASH_RE.search(content)
    if not match:
        return None
    # 大小写归一：正则带 IGNORECASE，但下游（`contract.py` 的 CONTRACT_DRIFT、sync/generator、
    # mcp）全部与 `hexdigest()` 的**小写**串比 ⇒ 手写大写哈希会被判成漂移（324）
    return match.group(1).lower()
