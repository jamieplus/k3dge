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
from k3dge.engine.pure_schema import check_content as _pure_check_content
from k3dge.engine.pure_schema import check_filename as _pure_check_filename
from k3dge.engine.pure_schema import check_index_ref as _pure_check_index_ref
from k3dge.engine.pure_schema import check_section_order  # noqa: F401 — re-export for tests/callers
from k3dge.engine.pure_schema import parse_doc_schema  # single source (was duplicated here)
from k3dge.engine.task_index import _frontmatter_pairs

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

_TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_FM_BLOCK_RE = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n", re.S)
_SUMMARY_RE = re.compile(r"可检索摘要[：:]\s*(.+)")
_HEADER_RE = re.compile(r"^-\s+\*\*([^*]+)\*\*:\s*(.+)$", re.MULTILINE)


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


def _body(text: str) -> str:
    """正文＝去掉开头 `---` … `---` frontmatter 块。

    为何必要：frontmatter 里的 YAML 注释（`# …`）对朴素解析器就是 H1。实测：12/14 条
    ADR 的 title 被抽成注释首行（「Append-only after Accepted…」），污染 `doc list`
    与 `docs/generated/docs-index.json`。标题只能来自正文的真 H1。
    """
    m = _FM_BLOCK_RE.match(text)
    return text[m.end():] if m else text


def build_card(workspace: Path, typ: str, path: Path) -> dict:
    rel = str(path.relative_to(workspace)).replace("\\", "/")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {"path": rel, "type": typ, "id": path.stem, "title": path.stem, "status": "", "tokens": ""}
    fm = dict(_frontmatter_pairs(text))
    headers = _headers(text)
    tm = _TITLE_RE.search(_body(text))
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


def _compile_query(q: str, ignore_case: bool):
    """编译为 regex；非法模式回退为字面量。"""
    flags = re.IGNORECASE if ignore_case else 0
    try:
        return re.compile(q, flags)
    except re.error:
        return re.compile(re.escape(q), flags)


def _grep_file(rgx, rel: str, text: str, line: bool) -> List[dict]:
    """单文件命中 → [{path}|{path,line}]；无命中空。行模式每文件封顶。"""
    out: List[dict] = []
    if not line:
        if rgx.search(text):
            out.append({"path": rel})
        return out
    n = 0
    for i, raw in enumerate(text.splitlines(), start=1):
        if rgx.search(raw):
            out.append({"path": rel, "line": i})
            n += 1
            if n >= GREP_MAX_LINES_PER_FILE:
                break
    return out


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
    rgx = _compile_query(q, ignore_case)
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
            found = _grep_file(rgx, rel, text, line)
            if found:
                hits.extend(found)
                files_used += 1
    return hits


def _code(schema: dict, key: str, default: str = "DOC_SCHEMA_INVALID") -> str:
    codes = schema.get("codes") or {}
    return str(codes.get(key) or default)





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
            detail={"path": rel},
        )
    schema = parse_doc_schema(text)
    if schema is None:
        return None, None
    if schema.get("_invalid"):
        return None, Violation(
            "DOC_SCHEMA_INVALID",
            f"{rel} is not a JSON object",
            file_path=rel,
            detail={"path": rel},
        )
    return schema, None


def _validate_file(workspace: Path, typ: str, path: Path, schema: dict, seen: dict) -> List[Violation]:
    """Structure gate via `pure_schema` (single implementation) + workspace-owned checks.

    File-local checks (filename/h1/sections/order/frontmatter/headers) delegate
    to `pure_schema.check_file`; ident-uniqueness bookkeeping and the index-file
    read stay here (cross-file I/O owned by the engine).
    """
    rel = str(path.relative_to(workspace)).replace("\\", "/")
    codes = schema.get("codes") or {}
    schema_rel = _schema_rel(typ)
    out: List[Violation] = []
    pure_violations, ident, filename_ok = _pure_check_filename(
        schema.get("filename"), codes, schema_rel, path.name)
    for code, msg, scope in pure_violations:
        out.append(Violation(code, msg, file_path=(schema_rel if scope == "schema" else rel)))
    if not filename_ok:
        return out
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [Violation(
            _code(schema, "filename"),
            f"cannot read: {exc}",
            file_path=rel,
        )]
    for code, msg, scope in _pure_check_content(schema, path.name, text, ident):
        out.append(Violation(code, msg, file_path=(schema_rel if scope == "schema" else rel)))
    seen.setdefault(ident, []).append(path.name)
    index_rel = schema.get("index")
    if index_rel:
        idx_path = _type_dir(workspace, typ) / index_rel
        idx_text = idx_path.read_text(encoding="utf-8") if idx_path.is_file() else ""
        for code, msg, _scope in _pure_check_index_ref(idx_text, ident, codes, index_rel, path.name):
            out.append(Violation(code, msg, file_path=rel))
    # 编号退役账本（baseline 之前的物理删除也在账上）：复用号 + 引用退役号
    from k3dge.engine import pure_refs as _pr

    for code, msg in _pr.check_adr_number_reuse(workspace, rel):
        out.append(Violation(code, msg, file_path=rel, detail={"path": rel}))
    for code, msg in _pr.check_adr_ref_retired(workspace, rel, text):
        out.append(Violation(code, msg, file_path=rel, detail={"path": rel}))
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
        return [Violation("DOC_INDEX_STALE", f"unreadable: {exc}", file_path=INDEX_REL,
                          detail={"reason": f"不可读：{exc}"})]
    if actual != expected:
        return [
            Violation(
                "DOC_INDEX_STALE",
                "stale",
                file_path=INDEX_REL,
                detail={"reason": "盘上内容与按当前 docs/ 重建的结果不同"},
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
