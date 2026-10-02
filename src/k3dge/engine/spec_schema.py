"""L0 structural validation of spec files."""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

#: 必需节：标题**锚定到全名**——只允许可选编号前缀，且必须是模板的 `## N. <全名>` 形状。
#: 旧判据的两个洞（注释承诺过、正则没做到，t-248）：
#: ①关键词短写让 `## Domain Boundary Draft Notes` 这类"带尾巴的旁节"顶掉正式节
#:   （`Domain Boundary\b` 在它身上成立）；②`#{2,3}` 让子级 `### 1. …全名…` 也算数，
#:   而模板/全部现行 spec 的节都是 `## ` 级——子级顶正式节＝同一文件里两套层级打架。
#: `SPEC_MISSING_SECTION` 是 block 闸 ⇒ 两类都是假绿面（322）。
#: §3（State Machine & Invariants）**不在机检集**：它是模板约定，内容由人管（t-249 已登记）。
_HEADING_PREFIX = r"^##[ \t]+(?:\d+[.)]?[ \t]+)?"
# 行尾必须锚死：只锚开头 + `\b` 会让 `## 1. Domain Boundary & Responsibilities Extra`
# 也通过，与"必须是模板 `## N. <全名>` 形状"的承诺不符（ocr2-079）。尾空白容忍，余字不认。
_HEADING_SUFFIX = r"[ \t]*$"
REQUIRED_SECTIONS: List[Tuple[str, "re.Pattern[str]"]] = [
    ("Domain Boundary & Responsibilities",
     re.compile(_HEADING_PREFIX + r"Domain Boundary & Responsibilities" + _HEADING_SUFFIX, re.MULTILINE)),
    ("Public Interfaces & Type Contracts",
     re.compile(_HEADING_PREFIX + r"Public Interfaces & Type Contracts" + _HEADING_SUFFIX, re.MULTILINE)),
    ("Verification Matrix",
     re.compile(_HEADING_PREFIX + r"Verification Matrix" + _HEADING_SUFFIX, re.MULTILINE)),
]

#: 64 位摘要必须**整串**匹配：`{64}` 无边界断言时，128 位（两个 digest 连写/复制多尾字符）
#: 会被静默截成合法 64 位，回执显示的是被截断的值（323）。
#: 尾部锚到**行尾**（允许结尾反引号/空白）：旧 `(?![0-9a-f])` 只挡 hex 续写，`<64hex>zz`
#: 这类尾部垃圾仍被当合法摘要（ocr2-318）——手改坏的摘要行会静默过 CONTRACT_DRIFT 检查。
CONTRACT_HASH_RE = re.compile(
    r"\*\*Contract Hash\*\*:[ \t]*`?sha256:([0-9a-f]{64})`?[ \t]*$",
    re.IGNORECASE | re.MULTILINE)


def _strip_fences(text: str) -> str:
    """去掉 ``` / ~~~ 围栏块（示例/生成的投影符不得顶替真实小节，ocr2-319）。"""
    out: List[str] = []
    in_fence = None  # (marker_char, open_len)
    for line in text.splitlines():
        m = re.match(r"^(`{3,}|~{3,})", line)
        if m:
            marker = m.group(1)
            if in_fence is None:
                in_fence = (marker[0], len(marker))
            elif marker[0] == in_fence[0] and len(marker) >= in_fence[1]:
                in_fence = None
            continue
        if in_fence is None:
            out.append(line)
    return "\n".join(out)


def validate_structure(content: str) -> List[str]:
    errors: List[str] = []
    body = _strip_fences(content)
    for name, pattern in REQUIRED_SECTIONS:
        if not pattern.search(body):
            errors.append(f"missing required section '{name}'")
    return errors


def extract_contract_hash(content: str) -> Optional[str]:
    match = CONTRACT_HASH_RE.search(content)
    if not match:
        return None
    # 大小写归一：正则带 IGNORECASE，但下游（`contract.py` 的 CONTRACT_DRIFT、sync/generator、
    # mcp）全部与 `hexdigest()` 的**小写**串比 ⇒ 手写大写哈希会被判成漂移（324）
    return match.group(1).lower()
