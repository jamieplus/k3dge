"""Zero-dependency cross-file doc checks (stdlib only — NO k3dge imports).

New gates the engine never had (see task 2026-09-16-M10-refactor-schema_check_layer):
B1 dangling references, B2 filename↔content consistency, B3 markdown integrity,
B4 orphan files. Wired into `scripts/pre-commit`; the engine does not call these
(pre-commit sees every staged file, so commit-time coverage is complete without
double-reporting).

Return convention: `[(code, message)]`. B4 codes are warnings (`ORPHAN_*`) —
callers print them without failing until the false-positive rate is observed.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple

# Allowed: other `k3dge.engine.pure_*` modules only (both `__init__.py` in the
# chain are docstring-only — verified, no heavy deps). Never import functional
# engine modules from here; enforced by `test_pure_imports_stdlib_only`.

from k3dge.engine.pure_schema import parse_frontmatter_pairs

Ref = Tuple[str, str]  # (code, message)

_ADR_RE = re.compile(r"ADR-(\d{4})")
_FOOTNOTE_REF_RE = re.compile(r"\[\^([^\]]+)\]")
_FOOTNOTE_DEF_RE = re.compile(r"^\[\^([^\]]+)\]:", re.MULTILINE)
_FENCE_RE = re.compile(r"^(`{3,}|~{3,})", re.MULTILINE)
_REPORT_RE = re.compile(r"-\s+\*\*Report\*\*:\s*`?([^`\n]+?)`?\s*$", re.MULTILINE)
_STATUS_RE = re.compile(r"-\s+\*\*Status\*\*:\s*([\w-]+)", re.IGNORECASE)
_ADR_FILE_RE = re.compile(r"^(\d{4})-")
_ADR_H1_RE = re.compile(r"^#\s+ADR-(\d{4})\b", re.MULTILINE)
_MATRIX_REF_RE = re.compile(r"`(tests/[^\s`]+)`")
_CONFLICT_START = "<<<<<<<"
_CONFLICT_END = ">>>>>>>"
_CODE_SPAN_RE = re.compile(r"`[^`\n]*`")


def strip_fences(text: str) -> str:
    """Remove fenced code blocks (example refs inside them are not real refs)."""
    out: List[str] = []
    in_fence: Optional[str] = None
    for line in text.splitlines():
        m = re.match(r"^(`{3,}|~{3,})", line)
        if m:
            fence = m.group(1)[0] * 3
            if in_fence is None:
                in_fence = fence
            elif line.startswith(in_fence):
                in_fence = None
            continue
        if in_fence is None:
            out.append(line)
    return "\n".join(out)


def strip_code_spans(text: str) -> str:
    """Remove inline `code` spans.

    Footnote-only: a doc that *describes* the pattern (`` `[^X]` `` in a table
    cell) is not a live reference. Deliberately NOT applied to the ADR check —
    real pointers are often written in backticks (`ADR-0025`), and stripping
    them there would weaken B1.
    """
    return _CODE_SPAN_RE.sub("", text)


def check_dangling_adr(workspace: Path, rel: str, text: str) -> List[Ref]:
    """Every `ADR-XXXX` must resolve to `docs/adr/XXXX-*.md` (or `obsolete/`)."""
    out: List[Ref] = []
    adr_dir = workspace / "docs" / "adr"
    for num in sorted(set(_ADR_RE.findall(strip_fences(text)))):
        if list(adr_dir.glob(f"{num}-*.md")):
            continue
        if (adr_dir / "obsolete").is_dir() and list((adr_dir / "obsolete").glob(f"{num}-*.md")):
            continue
        out.append(("DANGLING_ADR_REF", f"{rel}: ADR-{num} has no file under docs/adr/"))
    return out


def _report_pointer(text: str) -> str:
    fm = dict(parse_frontmatter_pairs(text))
    rep = (fm.get("report") or "").strip()
    if not rep:
        m = _REPORT_RE.search(text)
        rep = m.group(1).strip() if m else ""
    return rep


def check_report_pointer(workspace: Path, rel: str, text: str) -> List[Ref]:
    """A task's `report:` pointer must resolve (tasks only; others skipped)."""
    if not rel.startswith("docs/tasks/"):
        return []
    rep = _report_pointer(text)
    if not rep:
        return []
    if not (workspace / rep).is_file():
        return [("DANGLING_REPORT_REF", f"{rel}: report pointer missing: {rep}")]
    return []


def check_footnotes(rel: str, text: str) -> List[Ref]:
    """Every `[^X]` reference must have a `[^X]:` definition."""
    defs = set(_FOOTNOTE_DEF_RE.findall(text))
    # definition lines also contain `[^X]` textually — exclude them before scanning refs
    nodef_lines = [ln for ln in text.splitlines() if not _FOOTNOTE_DEF_RE.match(ln)]
    live_refs = set(_FOOTNOTE_REF_RE.findall(strip_code_spans(strip_fences("\n".join(nodef_lines)))))
    missing = sorted(live_refs - defs)
    return [("DANGLING_FOOTNOTE", f"{rel}: footnote [^{m}] referenced but never defined") for m in missing]


def _fm_value(text: str, key: str) -> str:
    for k, v in parse_frontmatter_pairs(text):
        if k.lower() == key.lower():
            return v
    return ""


def check_task_consistency(rel: str, text: str) -> List[Ref]:
    """`status: done` ⇔ `.done.md` 后缀；文件名 milestone ⇔ frontmatter；frontmatter ⇔ body。"""
    if not rel.startswith("docs/tasks/"):
        return []
    out: List[Ref] = []
    base = Path(rel).name
    st = _fm_value(text, "status").lower()
    if not st:
        m = _STATUS_RE.search(text)
        st = m.group(1).lower() if m else ""
    is_done_name = base.endswith(".done.md")
    if st == "done" and not is_done_name:
        out.append(("TASK_STATUS_MISMATCH", f"{rel}: status is done but filename lacks .done.md"))
    elif st and st != "done" and is_done_name:
        out.append(("TASK_STATUS_MISMATCH", f"{rel}: filename is .done.md but status is '{st}'"))
    ms = _fm_value(text, "milestone")
    if ms and ms not in base:
        out.append(("TASK_MILESTONE_MISMATCH", f"{rel}: frontmatter milestone '{ms}' not in filename"))
    out.extend(check_task_meta_agreement(rel, text))
    return out


# frontmatter 键 → body 粗体标签（两源的字段名不同）
_BODY_FIELD_MAP = {
    "status": "Status",
    "milestone": "Milestone",
    "priority": "Priority",
    "date": "Date",
    "report": "Report",
}


def check_task_meta_agreement(rel: str, text: str) -> List[Ref]:
    """frontmatter ↔ body 双源对照（tasks only）。

    frontmatter 是权威源（`task_index._scan_task_dir` 优先读它），body 的
    `- **Key**:` 是刻意保留的**人类可读副本**。副本可漂移且此前无闸发现 ⇒
    人读 body 见 `idea`、工具读 frontmatter 见 `done`，同一任务两种事实。

    单侧缺失不报（写入端不保证全字段，`milestone`/`report` 可缺）；
    无 frontmatter 的遗留任务跳过（body 即唯一源，无从对照）。
    """
    if not rel.startswith("docs/tasks/"):
        return []
    from k3dge.engine.pure_schema import parse_frontmatter_pairs, parse_headers

    fm = {k.lower(): v for k, v in parse_frontmatter_pairs(text)}
    if not fm:
        return []
    hdr = parse_headers(text)
    out: List[Ref] = []
    for fm_key, body_key in _BODY_FIELD_MAP.items():
        fv = fm.get(fm_key, "").strip()
        bv = (hdr.get(body_key) or "").strip().strip("`").strip()
        if not fv or not bv:
            continue
        if fv != bv:
            out.append((
                "TASK_META_DIVERGENCE",
                f"{rel}: {body_key} 双源不一致：frontmatter={fv!r} body={bv!r}",
            ))
    return out


_SUPERSEDES_RE = re.compile(r"^Supersedes:\s*ADR-(\d{4})\s*$", re.MULTILINE)


def check_supersede_unreconciled(workspace: Path, rel: str, text: str) -> List[Ref]:
    """ADR 声明 `Supersedes: ADR-Y` ⇒ Y 必须已标 Superseded 且移入 `obsolete/`。

    只读检查，跑在 commit 时。红了就是“修复路径告之”：`k3dge sync`
    （归档在 sync 里，不在 seal——见 memo「ADR 归档移出封板」）。
    """
    if not rel.startswith("docs/adr/") or "/obsolete/" in rel.replace("\\", "/"):
        return []
    m = _SUPERSEDES_RE.search(text)
    if not m:
        return []
    target = m.group(1)
    adr_dir = workspace / "docs" / "adr"
    if list(adr_dir.glob(f"{target}-*.md")):
        return [("ADR_SUPERSEDE_UNRECONCILED",
                 f"{rel}: 声明 Supersedes ADR-{target}，但该 ADR 仍在 docs/adr/（未归档）"
                 f"——run `k3dge sync`")]
    archived = list((adr_dir / "obsolete").glob(f"{target}-*.md"))
    if not archived:
        return [("ADR_SUPERSEDE_UNRECONCILED",
                 f"{rel}: 声明 Supersedes ADR-{target}，但 obsolete/ 下无该文件"
                 f"——run `k3dge sync`")]
    try:
        old = archived[0].read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    if "Status: Superseded" not in old:
        return [("ADR_SUPERSEDE_UNRECONCILED",
                 f"{rel}: obsolete/{archived[0].name} 未标 Status: Superseded"
                 f"——run `k3dge sync`")]
    return []


def check_adr_consistency(rel: str, text: str) -> List[Ref]:
    """ADR filename number vs `# ADR-NNNN` heading (checked only when both present)."""
    if not rel.startswith("docs/adr/"):
        return []
    m_file = _ADR_FILE_RE.match(Path(rel).name)
    m_h1 = _ADR_H1_RE.search(text)
    if m_file and m_h1 and m_file.group(1) != m_h1.group(1):
        return [("ADR_NUMBER_MISMATCH",
                 f"{rel}: filename ADR-{m_file.group(1)} != heading ADR-{m_h1.group(1)}")]
    return []


def check_markdown_bytes(raw: bytes, rel: str) -> List[Ref]:
    """Encoding-level checks on raw bytes. Returns [] when undecodable (caller reports)."""
    out: List[Ref] = []
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return [("MD_ENCODING", f"{rel}: not valid UTF-8 ({exc})")]
    if b"\r\n" in raw or b"\r" in raw.replace(b"\r\n", b""):
        out.append(("MD_CRLF", f"{rel}: CRLF line endings (use LF)"))
    return out


def check_markdown_text(text: str, rel: str) -> List[Ref]:
    """Unclosed fences, conflict markers, trailing whitespace, missing final newline."""
    out: List[Ref] = []
    for fence in ("```", "~~~"):
        n = sum(1 for ln in text.splitlines() if ln.strip().startswith(fence))
        if n % 2:
            out.append(("MD_FENCE_UNCLOSED", f"{rel}: unclosed {fence} code fence"))
    # conflict markers: ======= only counts inside an open <<<<<<< block
    # (bare ======= lines are legal setext headings)
    in_conflict = False
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith(_CONFLICT_START):
            in_conflict = True
            out.append(("MD_CONFLICT_MARKER", f"{rel}: merge conflict marker: {ln.strip()[:40]}"))
        elif s.startswith(_CONFLICT_END):
            out.append(("MD_CONFLICT_MARKER", f"{rel}: merge conflict marker: {ln.strip()[:40]}"))
            in_conflict = False
        elif in_conflict and s.startswith("======="):
            out.append(("MD_CONFLICT_MARKER", f"{rel}: merge conflict marker: {ln.strip()[:40]}"))
    if re.search(r"[ \t]+$", text, re.MULTILINE):
        out.append(("MD_TRAILING_WS", f"{rel}: trailing whitespace"))
    if text and not text.endswith("\n"):
        out.append(("MD_NO_FINAL_NEWLINE", f"{rel}: missing final newline"))
    return out


def find_orphan_specs(workspace: Path, manifest_spec_paths: List[str]) -> List[Ref]:
    """`docs/specs/**/spec.md` files no manifest domain points at (warn-tier)."""
    known = {p.replace("\\", "/") for p in manifest_spec_paths}
    out: List[Ref] = []
    for p in sorted((workspace / "docs" / "specs").rglob("spec.md")):
        rel = str(p.relative_to(workspace)).replace("\\", "/")
        if "_template" in p.parts or "archive" in p.parts:
            continue
        if rel not in known:
            out.append(("ORPHAN_SPEC", f"{rel}: no manifest domain references this spec"))
    return out


def find_orphan_tests(workspace: Path) -> List[Ref]:
    """`tests/**/*.py` files no Verification Matrix references (warn-tier)."""
    refs: set = set()
    for spec in (workspace / "docs" / "specs").rglob("spec.md"):
        if "_template" in spec.parts or "archive" in spec.parts:
            continue
        try:
            text = spec.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for ref in _MATRIX_REF_RE.findall(text):
            refs.add(ref.split("::")[0])
    out: List[Ref] = []
    tests_root = workspace / "tests"
    if not tests_root.is_dir():
        return []
    for p in sorted(tests_root.rglob("*.py")):
        if "__pycache__" in p.parts or "__init__.py" == p.name:
            continue
        rel = str(p.relative_to(workspace)).replace("\\", "/")
        if rel not in refs:
            out.append(("ORPHAN_TEST", f"{rel}: no Verification Matrix references this test file"))
    return out


def find_orphan_adrs(workspace: Path) -> List[Ref]:
    """`docs/adr/NNNN-*.md` numbers missing from README Topics (warn-tier)."""
    readme = workspace / "docs" / "adr" / "README.md"
    out: List[Ref] = []
    try:
        text = readme.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    topics = " ".join(ln for ln in text.splitlines() if "**" in ln)
    listed = set(re.findall(r"(\d{4})", topics))
    adr_dir = workspace / "docs" / "adr"
    for p in sorted(adr_dir.glob("*.md")):
        m = _ADR_FILE_RE.match(p.name)
        if not m or p.name in ("README.md", "AUTHORING.md", "_template.md"):
            continue
        if m.group(1) not in listed:
            out.append(("ORPHAN_ADR", f"docs/adr/{p.name}: ADR-{m.group(1)} not listed in README Topics"))
    return out
