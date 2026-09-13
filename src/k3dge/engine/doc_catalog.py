"""Managed-docs catalog: schema gate, thin index, list/where.

Per-type structure gate is ``docs/<type>/.schema.json`` (hidden, English name).
No file → no structure gate (downstream-safe). Index cards are filename +
frontmatter + first heading only — never the body.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from k3dge.engine.models import Violation

SCHEMA_FILE = ".schema.json"
INDEX_REL = "docs/generated/docs-index.json"
AUTHORING_FILE = "AUTHORING.md"
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
SKIP_TYPES = frozenset({"generated"})
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_FM_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
_TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_SUMMARY_RE = re.compile(r"可检索摘要[：:]\s*(.+)")
_HEADER_RE = re.compile(r"^-\s+\*\*([^*]+)\*\*:\s*(.+)$", re.MULTILINE)


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


def _type_dir(workspace: Path, typ: str) -> Path:
    return workspace / "docs" / typ


def iter_doc_types(workspace: Path) -> List[str]:
    root = workspace / "docs"
    if not root.is_dir():
        return []
    out = []
    for p in sorted(root.iterdir()):
        if p.is_dir() and p.name not in SKIP_TYPES and not p.name.startswith("."):
            out.append(p.name)
    return out


def _is_aux(path: Path) -> bool:
    return path.name in AUX_NAMES


def iter_managed_files(workspace: Path, typ: str, *, include_archive: bool = False) -> List[Path]:
    d = _type_dir(workspace, typ)
    if not d.is_dir():
        return []
    files: List[Path] = []
    for p in sorted(d.rglob("*.md")):
        if _is_aux(p):
            continue
        if not include_archive and "archive" in p.relative_to(d).parts:
            continue
        files.append(p)
    return files


def _frontmatter(text: str) -> Dict[str, str]:
    m = _FM_RE.match(text)
    meta: Dict[str, str] = {}
    if not m:
        return meta
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta


def _headers(text: str) -> Dict[str, str]:
    return {k.strip(): v.strip() for k, v in _HEADER_RE.findall(text)}


def _card_id(typ: str, path: Path, filename_re: Optional[re.Pattern[str]] = None) -> str:
    if typ == "adr":
        m = re.match(r"^(\d{4})-", path.name)
        return f"ADR-{m.group(1)}" if m else path.stem
    if typ == "incidents":
        return path.stem
    if filename_re is not None:
        m = filename_re.match(path.name)
        if m and m.lastindex:
            return m.group(1)
    return path.stem


def _tokens(text: str, title: str) -> str:
    sm = _SUMMARY_RE.search(text[:2000])
    if sm:
        return sm.group(1).strip()[:120]
    return title[:120]


def build_card(workspace: Path, typ: str, path: Path) -> dict:
    rel = str(path.relative_to(workspace)).replace("\\", "/")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {"path": rel, "type": typ, "id": path.stem, "title": path.stem, "status": "", "tokens": ""}
    fm = _frontmatter(text)
    headers = _headers(text)
    tm = _TITLE_RE.search(text)
    title = (tm.group(1).strip() if tm else path.stem)[:200]
    status = fm.get("Status") or fm.get("status") or headers.get("Status") or ""
    ident = _card_id(typ, path)
    return {
        "path": rel,
        "type": typ,
        "id": ident,
        "title": title,
        "status": status,
        "tokens": _tokens(text, title),
    }


def build_docs_index(workspace: Path, *, include_archive: bool = False) -> dict:
    docs = []
    for typ in iter_doc_types(workspace):
        for path in iter_managed_files(workspace, typ, include_archive=include_archive):
            docs.append(build_card(workspace, typ, path))
    docs.sort(key=lambda c: (c["type"], c["path"]))
    return {"docs": docs}


def write_docs_index(workspace: Path) -> Path:
    payload = build_docs_index(workspace)
    dest = workspace / INDEX_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return dest


def list_docs(
    workspace: Path,
    *,
    typ: Optional[str] = None,
    ident: Optional[str] = None,
    q: Optional[str] = None,
    include_archive: bool = False,
) -> List[dict]:
    cards = build_docs_index(workspace, include_archive=include_archive)["docs"]
    if typ:
        cards = [c for c in cards if c["type"] == typ]
    if ident:
        needle = ident.strip().upper()
        cards = [
            c
            for c in cards
            if c["id"].upper() == needle or c["id"].upper() == f"ADR-{needle}" or c["path"].upper().endswith(
                f"/{needle}.MD"
            )
        ]
    if q:
        ql = q.lower()
        cards = [
            c
            for c in cards
            if ql in c["title"].lower()
            or ql in c["tokens"].lower()
            or ql in c["id"].lower()
            or ql in c.get("status", "").lower()
        ]
    return cards


def where_doc(workspace: Path, ident: str) -> List[dict]:
    return list_docs(workspace, ident=ident)


# Body scan: coordinates only. Never attach snippet/text (context hygiene).
GREP_MAX_FILES = 20
GREP_MAX_LINES_PER_FILE = 8


def grep_docs(
    workspace: Path,
    query: str,
    *,
    typ: Optional[str] = None,
    line: bool = False,
    include_archive: bool = False,
    max_files: int = GREP_MAX_FILES,
    ignore_case: bool = True,
) -> List[dict]:
    """Scan managed doc bodies; return ``path`` or ``path``+``line`` only.

    No snippet field is ever populated. Caps files and per-file line hits.
    ``query`` is a regex; invalid patterns are treated as literals.
    """
    q = (query or "").strip()
    if not q:
        return []
    flags = re.IGNORECASE if ignore_case else 0
    try:
        rgx = re.compile(q, flags)
    except re.error:
        rgx = re.compile(re.escape(q), flags)
    types = [typ] if typ else iter_doc_types(workspace)
    hits: List[dict] = []
    files_used = 0
    for t in types:
        if files_used >= max_files:
            break
        for path in iter_managed_files(workspace, t, include_archive=include_archive):
            if files_used >= max_files:
                break
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            rel = str(path.relative_to(workspace)).replace("\\", "/")
            if not line:
                if rgx.search(text):
                    hits.append({"path": rel})
                    files_used += 1
                continue
            n = 0
            matched_file = False
            for i, raw in enumerate(text.splitlines(), start=1):
                if rgx.search(raw):
                    hits.append({"path": rel, "line": i})
                    n += 1
                    matched_file = True
                    if n >= GREP_MAX_LINES_PER_FILE:
                        break
            if matched_file:
                files_used += 1
    return hits


def _code(schema: dict, key: str, default: str = "DOC_SCHEMA_INVALID") -> str:
    codes = schema.get("codes") or {}
    return str(codes.get(key) or default)


_SECTION_NUM_RE = re.compile(r"^#{1,6}\s+(\d+(?:\.\d+)*)\b")


def check_section_order(text: str) -> Optional[Tuple[str, str]]:
    """Return (prev_number, this_number) for the first out-of-order/duplicate heading.

    A valid outline's dotted section numbers (`## 1`, `### 2.1`, `#### 2.1.1`) are
    strictly increasing in document order when compared as integer tuples: parents
    precede children, siblings ascend, and it never steps back. Inserting a new
    subsection out of position (or reusing a number) breaks this. Returns None if ok
    or if the doc has no numbered sections.
    """
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


def _schema_rel(typ: str) -> str:
    return f"docs/{typ}/{SCHEMA_FILE}"


def _load_schema(workspace: Path, typ: str) -> Tuple[Optional[dict], Optional[Violation]]:
    path = _type_dir(workspace, typ) / SCHEMA_FILE
    rel = _schema_rel(typ)
    if not path.is_file():
        return None, None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return None, Violation(
            "DOC_SCHEMA_INVALID",
            f"cannot read {rel}: {exc}",
            file_path=rel,
        )
    schema = parse_doc_schema(text)
    if schema is None:
        return None, None
    if schema.get("_invalid"):
        return None, Violation(
            "DOC_SCHEMA_INVALID",
            f"{rel} is not a JSON object",
            file_path=rel,
        )
    return schema, None


# k3dit:leftover Q-3 CC40 _validate_file 拆校验分支为子函数
def _validate_filename(typ, schema, path, rel, seen):
    pat = schema.get("filename")
    ident = path.stem
    if pat:
        try:
            rgx = re.compile(pat)
        except re.error as exc:
            return [Violation("DOC_SCHEMA_INVALID",
                              f"{_schema_rel(typ)} filename regex invalid: {exc}",
                              file_path=_schema_rel(typ))], ident, False
        m = rgx.match(path.name)
        if not m:
            return [Violation(_code(schema, "filename"),
                              f"filename does not match {pat}: {path.name}", file_path=rel)], ident, False
        if m.lastindex:
            ident = m.group(1)
            seen.setdefault(ident, []).append(path.name)
    return [], ident, True


def _validate_h1(schema, text, path, rel, ident):
    out: List[Violation] = []
    h1_pat = schema.get("h1")
    if h1_pat:
        filled = h1_pat.replace("{id}", re.escape(ident))
        if not re.search(filled, text, re.MULTILINE | re.IGNORECASE):
            out.append(Violation(_code(schema, "h1"),
                                f"H1 does not match `{h1_pat}` (id={ident}): {path.name}", file_path=rel))
    return out


def _validate_sections_when(schema, path, text, rel):
    out: List[Violation] = []
    for frag, secs in (schema.get("sections_when") or {}).items():
        if frag and frag in path.name:
            for sec in secs or []:
                if sec not in text:
                    out.append(Violation(_code(schema, "sections_when"),
                                        f"required section '{sec}' missing in {path.name} (matched '{frag}')",
                                        file_path=rel))
    return out


def _validate_sections(schema, path, text, rel):
    out: List[Violation] = []
    for heading in schema.get("sections") or []:
        if heading not in text:
            try:
                ok = bool(re.search(heading, text, re.MULTILINE))
            except re.error:
                ok = False
            if not ok:
                out.append(Violation(_code(schema, "sections"),
                                    f"missing section `{heading}`: {path.name}", file_path=rel))
    return out


def _validate_section_order(schema, path, text, rel):
    if schema.get("section_order"):
        bad = check_section_order(text)
        if bad:
            return [Violation(_code(schema, "section_order", "DOC_SECTION_ORDER"),
                              f"section number out of order (must ascend): {bad[0]} before {bad[1]}: {path.name}",
                              file_path=rel)]
    return []


def _validate_frontmatter(schema, path, text, rel):
    fm_spec = schema.get("frontmatter") or {}
    if not fm_spec:
        return []
    out: List[Violation] = []
    fm = _frontmatter(text)
    for key, rule in fm_spec.items():
        val = fm.get(key, "")
        if rule == "date":
            if not _DATE_RE.match(val):
                out.append(Violation(_code(schema, "frontmatter"),
                                    f"{key} missing or not YYYY-MM-DD: {path.name}", file_path=rel))
        elif isinstance(rule, list):
            if not _status_ok(val, rule):
                out.append(Violation(_code(schema, "frontmatter"),
                                    f"{key}={val!r} not in {rule}: {path.name}", file_path=rel))
    return out


def _validate_headers(schema, path, text, rel):
    hdr_spec = schema.get("headers") or {}
    if not hdr_spec:
        return []
    out: List[Violation] = []
    hdrs = _headers(text)
    fm = _frontmatter(text)
    for key, rule in hdr_spec.items():
        val = hdrs.get(key) or fm.get(key.lower()) or fm.get(key) or ""
        if isinstance(rule, list) and not _status_ok(val, [str(x) for x in rule]):
            out.append(Violation(_code(schema, "headers"),
                                f"{key}={val!r} not in {rule}: {path.name}", file_path=rel))
    return out


def _validate_index(workspace, typ, schema, path, rel, ident):
    index_rel = schema.get("index")
    if not index_rel:
        return []
    idx_path = _type_dir(workspace, typ) / index_rel
    idx_text = idx_path.read_text(encoding="utf-8") if idx_path.is_file() else ""
    token = ident
    if not re.search(rf"^\|\s*{re.escape(token)}\s*\|", idx_text, re.MULTILINE) and token not in idx_text:
        return [Violation(_code(schema, "index"),
                          f"{index_rel} has no row for `{token}`: {path.name}", file_path=rel)]
    return []


def _validate_file(workspace: Path, typ: str, path: Path, schema: dict, seen: dict) -> List[Violation]:
    rel = str(path.relative_to(workspace)).replace("\\", "/")
    out, ident, ok = _validate_filename(typ, schema, path, rel, seen)
    if not ok:
        return out
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        out.append(Violation(_code(schema, "filename"), f"cannot read: {exc}", file_path=rel))
        return out
    out += _validate_h1(schema, text, path, rel, ident)
    out += _validate_sections_when(schema, path, text, rel)
    out += _validate_sections(schema, path, text, rel)
    out += _validate_section_order(schema, path, text, rel)
    out += _validate_frontmatter(schema, path, text, rel)
    out += _validate_headers(schema, path, text, rel)
    out += _validate_index(workspace, typ, schema, path, rel, ident)
    return out

def validate_docs(workspace: Path, types: Optional[Iterable[str]] = None) -> List[Violation]:
    """Structure-only gate. Types without ``.schema.json`` are skipped."""
    violations: List[Violation] = []
    wanted = list(types) if types is not None else iter_doc_types(workspace)
    for typ in wanted:
        schema, err = _load_schema(workspace, typ)
        if err:
            violations.append(err)
            continue
        if not schema:
            continue
        seen: dict[str, List[str]] = {}
        for path in iter_managed_files(workspace, typ, include_archive=False):
            violations.extend(_validate_file(workspace, typ, path, schema, seen))
        if schema.get("filename") and "(" in str(schema.get("filename")):
            for ident, names in seen.items():
                if len(names) > 1:
                    rel = str((_type_dir(workspace, typ) / names[0]).relative_to(workspace)).replace("\\", "/")
                    violations.append(
                        Violation(
                            _code(schema, "unique"),
                            f"id collision {ident}: {', '.join(names)}",
                            file_path=rel,
                        )
                    )
    return violations


def validate_docs_index(workspace: Path) -> List[Violation]:
    """DOC_INDEX_STALE when the on-disk projection does not match a rebuild."""
    expected = build_docs_index(workspace)
    dest = workspace / INDEX_REL
    if not dest.is_file():
        return []
    try:
        actual = json.loads(dest.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [Violation("DOC_INDEX_STALE", f"{INDEX_REL} unreadable: {exc}", file_path=INDEX_REL)]
    if actual != expected:
        return [
            Violation(
                "DOC_INDEX_STALE",
                f"{INDEX_REL} is stale; run `k3dge sync`",
                file_path=INDEX_REL,
            )
        ]
    return []


_ADR_REF_RE = re.compile(r"ADR-(\d{4})")
_TITLE_TOK_RE = re.compile(r"[A-Za-z][A-Za-z0-9]+")
_TOKEN_STOP = frozenset(
    {"adr", "the", "and", "of", "for", "to", "a", "an", "in", "on", "with", "via", "is", "are", "not", "or", "by"}
)


def _adr_text(workspace: Path, card: dict) -> str:
    p = workspace / card["path"]
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _significant_tokens(title: str) -> set:
    return {t.lower() for t in _TITLE_TOK_RE.findall(title or "")} - _TOKEN_STOP


def analyze_adr_coverage(workspace: Path) -> dict:
    """ADR set self-consistency facts (non-judgmental). k3dit decides conflict.

    Returns ``adr_count`` + ``findings``: scope overlap (two live ADRs sharing
    significant title tokens) and pointer issues (dangling / superseded-still-referenced).
    Deterministic, O(n) pairwise; surfaces candidates, never judges.
    """
    cards = [c for c in build_docs_index(workspace)["docs"] if c.get("type") == "adr"]
    ids = {c["id"] for c in cards}
    live = {
        c["id"]
        for c in cards
        if not re.search(r"superseded", (c.get("status") or ""), re.IGNORECASE)
    }
    findings: List[dict] = []
    for c in cards:
        refs = {f"ADR-{r}" for r in _ADR_REF_RE.findall(_adr_text(workspace, c))}
        for rid in refs:
            if rid == c["id"]:
                continue
            if rid not in ids:
                findings.append(
                    {"type": "pointer_dangling", "severity": "warn", "a": c["id"], "b": rid,
                     "detail": f"{c['id']} references missing {rid}"}
                )
            elif rid not in live:
                findings.append(
                    {"type": "pointer_stale", "severity": "warn", "a": c["id"], "b": rid,
                     "detail": f"{c['id']} cites superseded {rid} as current"}
                )
    live_cards = [c for c in cards if c["id"] in live]
    toks = {c["id"]: _significant_tokens(c.get("title", "")) for c in live_cards}
    for i in range(len(live_cards)):
        for j in range(i + 1, len(live_cards)):
            a, b = live_cards[i], live_cards[j]
            inter = toks[a["id"]] & toks[b["id"]]
            if inter and len(inter) >= 2:
                findings.append(
                    {"type": "scope_overlap", "severity": "info", "a": a["id"], "b": b["id"],
                     "detail": f"shared scope tokens: {sorted(inter)}"}
                )
    return {"adr_count": len(cards), "findings": findings}
