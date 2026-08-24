"""L0 structural validation of spec files."""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

REQUIRED_SECTIONS: List[Tuple[str, "re.Pattern[str]"]] = [
    ("Domain Boundary & Responsibilities", re.compile(r"^#{2,3}\s+.*Domain Boundary", re.MULTILINE)),
    ("Public Interfaces & Type Contracts", re.compile(r"^#{2,3}\s+.*Public Interfaces", re.MULTILINE)),
    ("Verification Matrix", re.compile(r"^#{2,3}\s+.*Verification Matrix", re.MULTILINE)),
]

CONTRACT_HASH_RE = re.compile(r"\*\*Contract Hash\*\*:\s*`?sha256:([0-9a-f]{64})`?", re.IGNORECASE)


def validate_structure(content: str) -> List[str]:
    errors: List[str] = []
    for name, pattern in REQUIRED_SECTIONS:
        if not pattern.search(content):
            errors.append(f"missing required section '{name}'")
    return errors


def extract_contract_hash(content: str) -> Optional[str]:
    match = CONTRACT_HASH_RE.search(content)
    return match.group(1) if match else None
