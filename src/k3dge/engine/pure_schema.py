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


def _literal_or_re(item: str, match_re, nomatch_literal) -> bool:
    """声明表的取值一律**字面量**优先；要正则必须显式 `re:` 前缀。

    旧实现把每项都当正则：`"2.0"` 放行 `2x0`、`"Superseded"` 的 `.` 通配 ⇒ 假绿，
    且含元字符的真字面量反而判不中（假红）。两种错都来自"猜作者的意图"（ocr-300/301）。
    """
    if isinstance(item, str) and item.startswith("re:"):
        try:
            return match_re(item[3:])
        except re.error:
            return nomatch_literal()
    return nomatch_literal()


def _status_ok(value: str, allowed: Iterable[str]) -> bool:
    v = value.strip()
    for item in allowed:
        if _literal_or_re(str(item), lambda pat: bool(re.fullmatch(pat, v)), lambda: str(item) == v):
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
    # 可选分组没参与匹配时 `m.group(1)` 是 None，而 `lastindex` 只指"最后参与匹配的组"
    # ⇒ 判据要落在 **group(1) 本身**，否则 ident 被赋成 None 再流进 h1 模板（454）
    if m.lastindex:
        g1 = m.group(1)
        ident = g1 if isinstance(g1, str) else ident
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
    try:
        matched = re.search(filled, text, re.MULTILINE | re.IGNORECASE)
    except re.error as exc:
        # `h1` 是工作区可编辑配置；写坏正则要报 schema 违规，不能崩整轮 check（ocr-103）。
        return [(
            code_for(codes, "h1", "DOC_SCHEMA_INVALID"),
            f"h1 正则非法（{exc}）：{h1_pat!r}",
            "schema",
        )]
    if not matched:
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
            ok = _literal_or_re(str(heading),
                                lambda pat: bool(re.search(pat, text, re.MULTILINE)),
                                lambda: False)
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
        elif isinstance(rule, str):
            if val.strip() != rule:
                out.append((
                    code_for(codes, "frontmatter", "DOC_SCHEMA_INVALID"),
                    f"{key}={val!r} != 声明的唯一值 {rule!r}: {Path(filename).name}", "file"))
        elif isinstance(rule, dict) and ("enum" in rule or "pattern" in rule):
            ok = _status_ok(val, [str(x) for x in (rule.get("enum") or [])]) if rule.get("enum") \
                else bool(re.fullmatch(str(rule.get("pattern")), val))
            if not ok:
                out.append((
                    code_for(codes, "frontmatter", "DOC_SCHEMA_INVALID"),
                    f"{key}={val!r} 不满足声明 {rule}: {Path(filename).name}", "file"))
        else:
            # 形状不认识 ⇒ **报出来**：静默跳过等于该键永远绿（455）
            out.append((
                code_for(codes, "frontmatter", "DOC_SCHEMA_INVALID"),
                f"{schema_rel} 的 frontmatter.{key} 规则形状不支持（{type(rule).__name__}）",
                "schema"))
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
    # 索引**有表** ⇒ 必须真有一行（旧条件 `and token not in index_text` 让行判据恒失效：格内出现 token
    # 即放行，票没进表也 GREEN，ocr-104）；无表可查 ⇒ 退回子串判定（另一条路径）。
    if re.search(r"^\|", index_text, re.MULTILINE):
        ok = bool(re.search(rf"^\|\s*{re.escape(token)}\s*\|", index_text, re.MULTILINE))
    else:
        ok = token in index_text
    if not ok:
        return [(
            code_for(codes, "index", "DOC_SCHEMA_INVALID"),
            f"{index_rel} has no row for `{token}`: {Path(filename).name}",
            "file",
        )]
    return []


def check_amend(block: Any, codes: Dict[str, Any], filename: str, text: str) -> List[Check]:
    """ADR `Amended-by` 与 footnote 标记的形态（2026-09-24）。

    为什么进 schema 引擎而不是只挂 seal：`k3dge check` 才是**平时**的闸；只挂 seal 的话，
    漂移要活到封板才红（实测：注掉一个 `[^🅰2.1]` 引用后 `k3dge check` 仍 GREEN）。
    权威形态＝k3dge 自家 ADR（`- 🅰N | 席位 | 日期 | 简述`，降序；定义集中在文末）。

    判据：① 条目前缀 `- 🅰N |`；② 号唯一且单调；③ 引用/定义双向闭合（引用只从非定义行取）；
    ④ 定义行全在最后一个 `## ` 之后；⑤ 每条定义独占一行（续行会把脚注截断）；
    ⑥ 同一修订号的小标号按正文出现序从 1 连续；⑦ `Draft`/`Proposed` 不带修订留痕；
    ⑧ 多条修订都只写同一个节（同一天两条，或先后三条及以上）＝拆主题。
    """
    if not block:
        return []
    c_order = code_for((codes or {}), "amend_order", "ADR_AMEND_ORDER")
    c_tail = code_for((codes or {}), "footnote_tail", "ADR_FOOTNOTE_TAIL")
    c_marker = code_for((codes or {}), "amend_marker_text", "ADR_AMEND_MARKER_TEXT")
    c_ref = code_for((codes or {}), "amend_ref", "ADR_AMEND_REF")
    c_orphan = code_for((codes or {}), "footnote_orphan", "ADR_FOOTNOTE_ORPHAN")
    c_line = code_for((codes or {}), "footnote_line", "ADR_FOOTNOTE_LINE")
    c_seq = code_for((codes or {}), "footnote_seq", "ADR_FOOTNOTE_SEQ")
    c_draft = code_for((codes or {}), "amend_draft", "ADR_AMEND_DRAFT")
    c_split = code_for((codes or {}), "amend_split", "ADR_AMEND_SPLIT")
    out: List[Check] = []
    lines = text.splitlines()
    nums: List[int] = []
    body_text = "\n".join(l for l in lines if not l.startswith("[^🅰"))
    m = re.search(r"^Amended-by:\s*\n((?:\s+-.*(?:\n|$))+)", text, re.M)
    if m:
        for ln in m.group(1).splitlines():
            if not ln.strip():
                continue
            mm = re.match(r"^\s*-\s*🅰(\d+)\s*\|", ln)
            if not mm:
                out.append((c_order, f"Amended-by 条目缺 '🅰N |' 前缀：{ln.strip()[:48]}", "file"))
            else:
                nums.append(int(mm.group(1)))
        if len(set(nums)) != len(nums):
            out.append((c_order, f"Amended-by 号重复：{sorted(nums)}", "file"))
        elif nums != sorted(nums):
            # 顺序＝**append 序**（升序）：追加一条就是往下列，不倒插、不重排（2026-09-24 定）
            out.append((c_order, f"Amended-by 号非升序（应为 append 序）：{nums}", "file"))
        # 每条修订必须在正文被引用（脚注标记或 `> **🅰N 起**` 段级块）
        for n in sorted(set(nums)):
            if not re.search(rf"\[\^🅰{n}\.\d+\]", body_text) and \
               not re.search(rf"\*\*🅰{n}\b", body_text):
                out.append((c_ref, f"Amended-by 的 🅰{n} 在正文没有引用（脚注标或段级块）", "file"))
        # 正文不得用带文字的括号标记（`（🅰2，2026-09-21）`）——那是脚注引用的旧写法
        for m2 in re.finditer(r"（🅰\d+[，,][^）]*）", body_text):
            out.append((c_marker, f"正文里的括号标记应改为脚注引用：{m2.group(0)[:32]}", "file"))
    refs = set(re.findall(r"\[\^(🅰\d+\.\d+)\]", body_text))
    defs = set(re.findall(r"^\[\^(🅰\d+\.\d+)\]:", text, re.M))
    if defs - refs:
        out.append((c_orphan, f"脚注定义了却没被引用：{sorted(defs - refs)}", "file"))
    if refs - defs:
        out.append((c_orphan, f"脚注引用没有定义：{sorted(refs - defs)}", "file"))
    last_sec = max((i for i, l in enumerate(lines) if l.startswith("## ")), default=-1)
    deflines = [i for i, l in enumerate(lines) if l.startswith("[^🅰")]
    if deflines and not all(i > last_sec for i in deflines):
        out.append((c_tail, "脚注定义未集中在文末（穿插正文）", "file"))
    i = 0
    while i < len(lines):
        if re.match(r"^\[\^🅰\d+\.\d+\]:", lines[i]):
            start, end = _footnote_run(lines, i)
            if end > start:
                out.append((c_line, f"脚注定义必须独占一行（换行会截断脚注）：{lines[i][:48]}", "file"))
            i = end
            continue
        i += 1
    for n, minors in _footnote_minor_order(lines).items():
        if minors != list(range(1, len(minors) + 1)):
            out.append((c_seq, f"🅰{n} 的脚注小标号须按正文出现序从 1 连续，现为 {minors}", "file"))
    status = re.search(r"^Status:\s*(\S+)", text, re.M)
    if status and status.group(1) in ("Draft", "Proposed") and (nums or refs or defs):
        out.append((c_draft, "Draft/Proposed 不记 Amended-by 与修订脚注；Accepted 之后才修订", "file"))
    for sec, group in _amend_sole_sections(text).items():
        dates = {d for _, d in group}
        if len(group) >= 3 or (len(group) >= 2 and len(dates) == 1):
            ids = "、".join(f"🅰{n}" for n, _ in group)
            out.append((c_split,
                        f"Amended-by 的 {ids} 都只写 §{sec}，同一主题拆成了多个号；"
                        f"并成一个号，落点用连续小标号",
                        "file"))
    return out


_AMEND_ROW_RE = re.compile(r"^\s*-\s*🅰(\d+)\s*\|[^|]*\|([^|]*)\|(.*)$")
_SECTION_REF_RE = re.compile(r"§(\d+(?:\.\d+)*)")


def _most_specific_sections(sections: List[str]) -> List[str]:
    """丢掉被更长节号盖住的前缀：同时写了 §2.9 和 §2.9.6 时，主题是 §2.9.6。"""
    return [s for s in sections if not any(o != s and o.startswith(s + ".") for o in sections)]


def _amend_sole_sections(text: str) -> Dict[str, List[tuple]]:
    """每条修订若只谈论一个节，记到那个节名下。返回节号 → [(修订号, 日期)]。"""
    m = re.search(r"^Amended-by:\s*\n((?:\s+-.*(?:\n|$))+)", text, re.M)
    if not m:
        return {}
    by: Dict[str, List[tuple]] = {}
    for ln in m.group(1).splitlines():
        mm = _AMEND_ROW_RE.match(ln)
        if not mm:
            continue
        specific = _most_specific_sections(_SECTION_REF_RE.findall(mm.group(3)))
        if len(specific) != 1:
            continue
        by.setdefault(specific[0], []).append((int(mm.group(1)), mm.group(2).strip()))
    return by


def _footnote_continuation(line: str) -> bool:
    """定义行的下一行若仍是这段说明，Markdown 会把它当成正文，脚注在此截断。"""
    s = line.strip()
    return bool(s) and not s.startswith("[^") and not s.startswith("#") and s != "---"


def _footnote_run(lines: List[str], start: int) -> Tuple[int, int]:
    """从定义行起，连续说明行的半开区间（不含定义行本身的后一段）。"""
    j = start + 1
    while j < len(lines) and _footnote_continuation(lines[j]):
        j += 1
    return start + 1, j


def _footnote_minor_order(lines: List[str]) -> Dict[int, List[int]]:
    """每个修订号的小标号，按正文（非定义行）第一次出现的顺序。"""
    order: Dict[int, List[int]] = {}
    for line in lines:
        if line.startswith("[^🅰"):
            continue
        for m in re.finditer(r"\[\^🅰(\d+)\.(\d+)\]", line):
            n, minor = int(m.group(1)), int(m.group(2))
            got = order.setdefault(n, [])
            if minor not in got:
                got.append(minor)
    return order


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
    out += check_amend(schema.get("amend"), codes, filename, text)
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
