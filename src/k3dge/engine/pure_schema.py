"""Zero-dependency doc-schema checks (stdlib only — NO k3dge imports).

Canonical implementation shared by `scripts/pre-commit` (via `src/` on
sys.path, no venv needed) and `engine/doc_catalog.py` (wraps results into
`Violation`). Moved verbatim out of `doc_catalog.py`; behavior must stay
identical — see `tests/unit/engine/test_pure_schema.py` cross-checks.

Return convention: every `check_*` returns `[(code, message, scope)]` with
scope `"file"` (attaches to the checked file) or `"schema"` (attaches to the
`.schema.json` itself, e.g. an invalid filename regex).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_HEADER_RE = re.compile(r"^-\s+\*\*([^*]+)\*\*:\s*(.+)$", re.MULTILINE)
_SECTION_NUM_RE = re.compile(r"^#{1,6}\s+(\d+(?:\.\d+)*)\b")

# Mirror of `doc_catalog.AUX_NAMES` — files never treated as managed docs.
# Drift-guarded: `test_pure_schema.py::test_aux_names_in_sync` asserts equality.
AUX_NAMES = frozenset(
    {
        "README.md",
        "_template.md",
        "AUTHORING.md",
        "summary.md",
        "SUMMARY.md",
        "LEFTOVERS.md",
        "leftovers.md",
    }
)

Check = Tuple[str, str, str]  # (code, message, scope "file"|"schema")


def parse_doc_schema(text: str) -> Optional[dict]:
    """Parse a ``.schema.json`` body. Empty → None; invalid JSON → ``_invalid``."""
    blob = (text or "").strip()
    if not blob:
        return None
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        return {"_invalid": True, "_raw": blob}
    return data if isinstance(data, dict) else {"_invalid": True}


def parse_frontmatter_pairs(content: str) -> List[tuple]:
    """Verbatim copy of `task_index._frontmatter_pairs` (kept duplicate-free by test).

    The ``---`` block must open on the first line and close inline; returns
    ``(original_key, value)`` pairs. Unclosed blocks are not frontmatter.
    """
    lines = content.splitlines()
    if len(lines) < 2 or lines[0].strip() != "---":
        return []
    pairs: List[tuple] = []
    for line in lines[1:]:
        if line.strip() == "---":
            return pairs
        if ":" in line:
            k, v = line.split(":", 1)
            pairs.append((k.strip(), v.strip()))
    return []


def parse_headers(text: str) -> Dict[str, str]:
    return {k.strip(): v.strip() for k, v in _HEADER_RE.findall(text)}


def check_section_order(text: str) -> Optional[Tuple[str, str]]:
    """First out-of-order/duplicate dotted heading, or None if the outline ascends."""
    numbers: List[Tuple[int, ...]] = []
    for line in text.splitlines():
        m = _SECTION_NUM_RE.match(line)
        if m:
            numbers.append(tuple(int(x) for x in m.group(1).split(".")))
    prev: Optional[Tuple[int, ...]] = None
    for cur in numbers:
        if prev is not None and cur <= prev:
            return (".".join(map(str, prev)), ".".join(map(str, cur)))
        prev = cur
    return None


def _status_ok(value: str, allowed: Iterable[str]) -> bool:
    v = value.strip()
    for item in allowed:
        try:
            if re.fullmatch(item, v):
                return True
        except re.error:
            if item == v:
                return True
    return False


def code_for(codes: Dict[str, Any], key: str, default: str) -> str:
    return str(codes.get(key) or default)


def check_filename(
    filename_pat: Optional[str],
    codes: Dict[str, Any],
    schema_rel: str,
    filename: str,
) -> Tuple[List[Check], str, bool]:
    """Returns (violations, ident, ok). `ok` False stops further checks (fatal)."""
    ident = Path(filename).stem
    if not filename_pat:
        return [], ident, True
    try:
        rgx = re.compile(filename_pat)
    except re.error as exc:
        return [(
            code_for(codes, "filename", "DOC_SCHEMA_INVALID"),
            f"{schema_rel} filename regex invalid: {exc}",
            "schema",
        )], ident, False
    m = rgx.match(Path(filename).name)
    if not m:
        return [(
            code_for(codes, "filename", "DOC_SCHEMA_INVALID"),
            f"filename does not match {filename_pat}: {Path(filename).name}",
            "file",
        )], ident, False
    if m.lastindex:
        ident = m.group(1)
    return [], ident, True


def check_h1(
    h1_pat: Optional[str],
    codes: Dict[str, Any],
    text: str,
    filename: str,
    ident: str,
) -> List[Check]:
    if not h1_pat:
        return []
    filled = h1_pat.replace("{id}", re.escape(ident))
    if not re.search(filled, text, re.MULTILINE | re.IGNORECASE):
        return [(
            code_for(codes, "h1", "DOC_SCHEMA_INVALID"),
            f"H1 does not match `{h1_pat}` (id={ident}): {filename}",
            "file",
        )]
    return []


def check_sections_when(
    sections_when: Optional[Dict[str, Any]],
    codes: Dict[str, Any],
    filename: str,
    text: str,
) -> List[Check]:
    out: List[Check] = []
    for frag, secs in (sections_when or {}).items():
        if frag and frag in Path(filename).name:
            for sec in secs or []:
                if sec not in text:
                    out.append((
                        code_for(codes, "sections_when", "DOC_SCHEMA_INVALID"),
                        f"required section '{sec}' missing in {Path(filename).name} (matched '{frag}')",
                        "file",
                    ))
    return out


def check_sections(
    sections: Optional[List[str]],
    codes: Dict[str, Any],
    filename: str,
    text: str,
) -> List[Check]:
    out: List[Check] = []
    for heading in sections or []:
        if heading not in text:
            try:
                ok = bool(re.search(heading, text, re.MULTILINE))
            except re.error:
                ok = False
            if not ok:
                out.append((
                    code_for(codes, "sections", "DOC_SCHEMA_INVALID"),
                    f"missing section `{heading}`: {Path(filename).name}",
                    "file",
                ))
    return out


def check_section_ordering(
    enabled: Any,
    codes: Dict[str, Any],
    filename: str,
    text: str,
) -> List[Check]:
    if not enabled:
        return []
    bad = check_section_order(text)
    if bad:
        return [(
            code_for(codes, "section_order", "DOC_SECTION_ORDER"),
            f"section number out of order (must ascend): {bad[0]} before {bad[1]}: {Path(filename).name}",
            "file",
        )]
    return []


def check_frontmatter(
    fm_spec: Optional[Dict[str, Any]],
    codes: Dict[str, Any],
    filename: str,
    text: str,
) -> List[Check]:
    if not fm_spec:
        return []
    out: List[Check] = []
    fm = dict(parse_frontmatter_pairs(text))
    for key, rule in fm_spec.items():
        val = fm.get(key, "")
        if rule == "date":
            if not _DATE_RE.match(val):
                out.append((
                    code_for(codes, "frontmatter", "DOC_SCHEMA_INVALID"),
                    f"{key} missing or not YYYY-MM-DD: {Path(filename).name}",
                    "file",
                ))
        elif isinstance(rule, list):
            if not _status_ok(val, rule):
                out.append((
                    code_for(codes, "frontmatter", "DOC_SCHEMA_INVALID"),
                    f"{key}={val!r} not in {rule}: {Path(filename).name}",
                    "file",
                ))
    return out


def check_headers(
    hdr_spec: Optional[Dict[str, Any]],
    codes: Dict[str, Any],
    filename: str,
    text: str,
) -> List[Check]:
    if not hdr_spec:
        return []
    out: List[Check] = []
    hdrs = parse_headers(text)
    fm = dict(parse_frontmatter_pairs(text))
    for key, rule in hdr_spec.items():
        val = hdrs.get(key) or fm.get(key.lower()) or fm.get(key) or ""
        if isinstance(rule, list) and not _status_ok(val, [str(x) for x in rule]):
            out.append((
                code_for(codes, "headers", "DOC_SCHEMA_INVALID"),
                f"{key}={val!r} not in {rule}: {Path(filename).name}",
                "file",
            ))
    return out


def check_index_ref(
    index_text: str,
    token: str,
    codes: Dict[str, Any],
    index_rel: str,
    filename: str,
) -> List[Check]:
    if not re.search(rf"^\|\s*{re.escape(token)}\s*\|", index_text, re.MULTILINE) and token not in index_text:
        return [(
            code_for(codes, "index", "DOC_SCHEMA_INVALID"),
            f"{index_rel} has no row for `{token}`: {Path(filename).name}",
            "file",
        )]
    return []


def check_content(
    schema: Dict[str, Any],
    filename: str,
    text: str,
    ident: str,
) -> List[Check]:
    """Content checks (need text + ident; caller must pass the filename gate first)."""
    codes = schema.get("codes") or {}
    out: List[Check] = []
    out += check_h1(schema.get("h1"), codes, text, filename, ident)
    out += check_sections_when(schema.get("sections_when"), codes, filename, text)
    out += check_sections(schema.get("sections"), codes, filename, text)
    out += check_section_ordering(schema.get("section_order"), codes, filename, text)
    out += check_frontmatter(schema.get("frontmatter"), codes, filename, text)
    out += check_headers(schema.get("headers"), codes, filename, text)
    return out


def check_file(
    schema: Dict[str, Any],
    filename: str,
    text: str,
    *,
    schema_rel: str = ".schema.json",
) -> Tuple[List[Check], str, bool]:
    """File-local structure checks. Returns (violations, ident, filename_ok).

    Convenience wrapper = `check_filename` then `check_content`. Prefer the
    split calls when read errors must precede content checks (text unavailable).
    Cross-file concerns (ident uniqueness, index membership) stay with caller.
    """
    codes = schema.get("codes") or {}
    out, ident, ok = check_filename(schema.get("filename"), codes, schema_rel, filename)
    if not ok:
        return out, ident, False
    out += check_content(schema, filename, text, ident)
    return out, ident, True
