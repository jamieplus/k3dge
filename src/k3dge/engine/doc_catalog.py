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


def iter_managed_files(workspace: Path, typ: str, *, include_archive: bool = False,
                       include_retired: bool = False) -> List[Path]:
    """受管文件；`archive/` 与 `obsolete/` 默认**排除**（低权威/退役面）。

    `obsolete/` 是退役面（ADR 合并/被取代的去处）：默认不出现在现行视图里，
    但要**可寻址**——`--include-retired` 时纳入，卡片带 `retired: True` + 去向，
    免得退役 ADR 在寻址面上彻底隐身（票 adr_number_cutline 的漏项）。
    """
    d = _type_dir(workspace, typ)
    if not d.is_dir():
        return []
    files: List[Path] = []
    for p in sorted(d.rglob("*.md")):
        if _is_aux(p):
            continue
        parts = p.relative_to(d).parts
        if not include_archive and "archive" in parts:
            continue
        if not include_retired and "obsolete" in parts:
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
    card = {
        "path": rel,
        "type": typ,
        "id": ident,
        "title": title,
        "status": status,
        "tokens": _tokens(text, title),
    }
    if "obsolete" in Path(rel).parts:
        # 退役面：带上"这条去哪了"，否则读者只知道文件躺在这儿
        card["retired"] = True
        dest = (fm.get("merged-into") or fm.get("merged_into")
                or fm.get("superseded_by") or fm.get("Superseded-by") or "")
        card["dest"] = str(dest).strip()
    return card


def build_docs_index(workspace: Path, *, include_archive: bool = False,
                     include_retired: bool = False) -> dict:
    docs = []
    for typ in iter_doc_types(workspace):
        for path in iter_managed_files(workspace, typ, include_archive=include_archive,
                                       include_retired=include_retired):
            docs.append(build_card(workspace, typ, path))
    docs.sort(key=lambda c: (c["type"], c["path"]))
    return {"docs": docs}


def retired_ledger_cards(workspace: Path) -> List[dict]:
    """退役账本（`docs/adr/obsolete/README.md` 的表）→ 卡片。

    这 13 个号**没有墓碑文件**（baseline 之前被物理删除），若不在此投影，
    `doc where ADR-0020` 只会说"not found"——退役号在寻址面彻底隐身。
    """
    from k3dge.engine import pure_refs

    ledger_rel = "docs/adr/obsolete/README.md"
    out: List[dict] = []
    for num, info in sorted(pure_refs.retired_adr_numbers(workspace).items()):
        out.append({
            "path": ledger_rel,
            "type": "adr",
            "id": f"ADR-{num}",
            "title": f"（已退役）{info.get('was', '')}".strip(),
            "status": "Retired",
            "tokens": str(info.get("dest", "")),
            "retired": True,
            "dest": str(info.get("dest", "")),
            "ledger": ledger_rel,
        })
    return out


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
    include_retired: bool = False,
) -> List[dict]:
    cards = build_docs_index(workspace, include_archive=include_archive,
                             include_retired=include_retired)["docs"]
    if include_retired and typ in (None, "adr"):
        seen = {c["id"] for c in cards}
        cards = cards + [c for c in retired_ledger_cards(workspace) if c["id"] not in seen]
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


def where_doc(workspace: Path, ident: str, *, include_retired: bool = True) -> List[dict]:
    """按 id 解析路径。**默认含退役面**——退役号要能查到"曾是/去向"，而不是 not found。"""
    rows = list_docs(workspace, ident=ident, include_retired=include_retired)
    if rows or not include_retired:
        return rows
    return list_docs(workspace, ident=ident, include_retired=True)


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
    # `typ` 来自 CLI/MCP（不可信/模型可控）：直接用会绕过 `iter_doc_types` 的全部过滤
    #（`SKIP_TYPES`、`.` 开头、非目录），`generated`/`..`/隐藏面都会被扫（ocr2-054）。
    # 只认"当前真实存在的受管类型"；指名不存在的类型 ⇒ 空结果，不回落全量（回落等于放大）。
    _allowed = set(iter_doc_types(workspace))
    types = [typ] if (typ and typ in _allowed) else ([] if typ else iter_doc_types(workspace))
    hits: List[dict] = []
    files_used = 0
    scanned = 0
    scan_cap = max(max_files * 8, max_files)   # 只按**命中**数封顶 ⇒ 不命中的查询会把全类型文件读一遍
    for t in types:                            # 与 docstring "Caps files and per-file line hits" 不符（ocr-231）
        if files_used >= max_files or scanned >= scan_cap:
            break
        for path in iter_managed_files(workspace, t, include_archive=include_archive):
            if files_used >= max_files or scanned >= scan_cap:
                break
            scanned += 1
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
    # 记账用**工作区相对路径**而不是 `path.name`：`iter_managed_files` 走 `rglob("*.md")` 会纳入
    # 子目录里的受管件，只记名 ⇒ 冲突项的 file_path 被拼成 `<type>/<basename>`（不存在的错误路径），
    # 两个同名不同目录的件也会互相顶掉（414）
    seen.setdefault(ident, []).append(rel)
    index_rel = schema.get("index")
    if index_rel:
        # containment + 读保护：schema 的 `index` 若为绝对路径/含 `..` 会读仓外；坏编码/TOCTOU 会让
        # 整个 `validate_docs` 崩栈（其它读取都包了 try，唯此处漏，ocr-063）。
        try:
            type_dir = _type_dir(workspace, typ)
            root = type_dir.resolve()
            rp = (type_dir / str(index_rel)).resolve()
            if rp != root and root not in rp.parents:
                idx_text = ""
            else:
                idx_text = rp.read_text(encoding="utf-8") if rp.is_file() else ""
        except (OSError, UnicodeDecodeError, ValueError):
            idx_text = ""
        for code, msg, _scope in _pure_check_index_ref(idx_text, ident, codes, index_rel, path.name):
            out.append(Violation(code, msg, file_path=rel))
    # 编号退役账本（baseline 之前的物理删除也在账上）：复用号 + 引用退役号
    from k3dge.engine import pure_refs as _pr

    for code, msg in _pr.check_adr_number_reuse(workspace, rel):
        out.append(Violation(code, msg, file_path=rel, detail={"path": rel}))
    for code, msg in _pr.check_adr_ref_retired(workspace, rel, text):
        out.append(Violation(code, msg, file_path=rel, detail={"path": rel}))
    if typ == "incidents":
        for code, msg in _pr.check_incident_id_redundant(rel, text):
            out.append(Violation(code, msg, file_path=rel, detail={"path": rel}))
    if typ == "tasks":
        # 仓库级也验票一致性（此前**只有 pre-commit 对 staged 文件验** ⇒ 历史漂移无人管，
        # 自举测试 test_repo_tasks_conform 也因此空转）。四条：status↔文件名、milestone↔文件名、
        # 正文复写元数据、done 票须有结案记录。
        for code, msg in _pr.check_task_consistency(rel, text):
            out.append(Violation(code, msg, file_path=rel, detail={"path": rel}))
    return out

def _boundary_task_violations(workspace: Path) -> List[Violation]:
    """边界之后新增却仍挂在已封里程碑上的票（advisory，ADR-0004 §2.1.9）。

    一次性算（每个边界一次 git 调用），不放进类型循环——否则每张票都要跑一遍 git。
    """
    from k3dge.engine import milestone_files as _mf

    try:
        rows = _mf.tasks_after_boundary(workspace)
    except Exception:  # 非 git 仓 / git 不可用 ⇒ 无事实可报，不假装有
        return []
    return [
        Violation("TASK_MILESTONE_AFTER_BOUNDARY", msg, file_path=rel,
                  detail={"path": rel, "milestone": ms})
        for rel, ms, msg in rows
    ]


def validate_docs(workspace: Path, types: Optional[Iterable[str]] = None) -> List[Violation]:
    """Structure-only gate. Types without ``.schema.json`` are skipped."""
    violations: List[Violation] = []
    wanted = list(types) if types is not None else iter_doc_types(workspace)
    # 退役面：不参与默认视图（iter_managed_files 排除 obsolete/），但**去向必须可验** ⇒ 独立扫。
    # 注意放在类型循环**之外**：不依赖 adr 有没有 .schema.json，闸不该因为缺 schema 被跳过。
    if types is None or "adr" in wanted:
        from k3dge.engine import pure_refs as _pr

        obs = _type_dir(workspace, "adr") / "obsolete"
        if obs.is_dir():
            for op in sorted(obs.glob("*.md")):
                orel = str(op.relative_to(workspace)).replace("\\", "/")
                try:
                    otext = op.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                for code, msg in _pr.check_retired_adr_dest(orel, otext):
                    violations.append(Violation(code, msg, file_path=orel, detail={"path": orel}))

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
                    rel = names[0]
                    violations.append(
                        Violation(
                            _code(schema, "unique"),
                            f"id collision {ident}: {', '.join(names)}",
                            file_path=rel,
                        )
                    )
    # 边界之后新增的票仍挂在已封里程碑上（advisory）：一次算，不放类型循环里
    if types is None or "tasks" in wanted:
        violations.extend(_boundary_task_violations(workspace))
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
