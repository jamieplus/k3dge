"""Zero-dependency cross-file doc checks (stdlib only — NO k3dge imports).

New gates the engine never had (see task 2026-09-16-M10-refactor-schema_check_layer):
B1 dangling references, B2 filename↔content consistency, B3 markdown integrity,
B4 orphan files. Wired into `scripts/pre-commit`; the engine does not call these
(pre-commit sees every staged file, so commit-time coverage is complete without
double-reporting).

Return convention: `[(code, message_or_path)]` —— 已声明进 `gate_facts` 的 code 一律返回**事实**
（多数情况就是路径），文案由声明表渲染；B4 codes 是 warnings (`ORPHAN_*`) —
callers print them without failing until the false-positive rate is observed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

# Allowed: other `k3dge.engine.pure_*` modules only (both `__init__.py` in the
# chain are docstring-only — verified, no heavy deps). Never import functional
# engine modules from here; enforced by `test_pure_imports_stdlib_only`.

from k3dge.engine.pure_schema import AUX_NAMES, parse_frontmatter_pairs

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
#: 行内代码：CommonMark 允许任意长度的反引号串作定界符（内容不得含同长串）。
#: 旧只认单反引号 ⇒ 文档里用 `` `x` `` 形式举反引号例子时，示例内容仍被当正文（385 家族/桩判定误读）。
_CODE_SPAN_RE = re.compile(r"(`+)(?:(?!\1)[^\n])*?\1")


def inside_workspace(workspace: Path, ref: str) -> bool:
    """指针/回执去向必须落在本仓内：绝对路径会**替换**基路径、`..` 会越界（ocr-295/297）。"""
    s = str(ref or "").strip()
    if not s:
        return False
    cand = Path(s)
    if cand.is_absolute() or ".." in cand.parts:
        return False
    try:
        root = Path(workspace).resolve()
        return (root / cand).resolve().is_relative_to(root)
    except OSError:  # pragma: no cover - 异常按"不在仓内"处理
        return False


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


#: 跨仓自限定引用（`k3dge ADR-0001` / `where ADR-0001`）：**指向 k3dge 仓的决策**，不在本仓解析面。
#: 下游仓自带 `docs/adr/` 从 0001 起编号，若这里也要求"解析得到"，则 k3dge **自己下发的文档**
#: 永远过不了自己的 hook（实测 2026-09-21：init 后首次提交被 `DANGLING_ADR_REF` 拦）。
#: 代价：k3dge 自举仓里带 `k3dge ` 前缀的引用不再被本闸校验（有意留，见 LEFTOVERS）。
# `where` 是普通英文连接词：`, where ADR-0001 mandates …` 会被整段豁免 ⇒ B1 对该号完全不校验（452）。
# 跨仓自限定只认工具名前缀这一种形状（LEFTOVERS 记其代价）。
_QUALIFIED_ADR_RE = re.compile(r"k3dge\s+ADR-\d{4}", re.IGNORECASE)


def _adr_numbers_to_resolve(text: str) -> List[str]:
    """待解析的 ADR 号：先去代码围栏、再去跨仓自限定引用。"""
    return sorted(set(_ADR_RE.findall(_QUALIFIED_ADR_RE.sub("", strip_fences(text)))))


def check_dangling_adr(workspace: Path, rel: str, text: str) -> List[Ref]:
    """Every unqualified `ADR-XXXX` must resolve to `docs/adr/XXXX-*.md` (or `obsolete/`)."""
    out: List[Ref] = []
    adr_dir = workspace / "docs" / "adr"
    for num in _adr_numbers_to_resolve(text):
        if list(adr_dir.glob(f"{num}-*.md")):
            continue
        if (adr_dir / "obsolete").is_dir() and list((adr_dir / "obsolete").glob(f"{num}-*.md")):
            continue
        out.append(("DANGLING_ADR_REF", f"{rel}: ADR-{num} has no file under docs/adr/"))
    return out


def _report_pointer(text: str) -> str:
    # 键一律 lower 后比：本模块其余读法（`_fm_value`/`check_retired_adr_dest`）都大小写不敏感，
    # 这里用原始键 ⇒ `Report: …` 静默不看（判据随作者大小写漂移，ocr-294）
    fm = {k.lower(): v for k, v in parse_frontmatter_pairs(text)}
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
    if not inside_workspace(workspace, rep):
        return [("DANGLING_REPORT_REF",
                 f"{rel}: report 指针越出本仓（须是仓内相对路径）：{rep}")]
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


def has_milestone_token(text: str, milestone_id: str) -> bool:
    r"""`milestone_id` 是否以**路径/词元**出现（不是更长 id 的子串）。

    `M1` 不得匹配 `M10`（文件名 `2026-08-23-M10-align.md` 或正文里的 `M10`）。
    边界集 `[-_./\s]`（**不含 `+`**：`M10+` 形态不合法，见 `milestone_pointer` 的 id 规则）。
    大小写不敏感（与 `milestone_files._FILENAME_MILESTONE_RE` 同口径）。

    归零依赖层：`milestone_files._has_milestone_token` 是其委托别名（单一实现在此），
    这样闸核（`check_task_consistency`）与生命周期模块判同一个东西，不必各写一遍正则。
    """
    if not milestone_id:
        return False
    # 大小写不敏感：`_filename_milestone`/`_FILENAME_MILESTONE_RE` 都带 IGNORECASE，
    # 这里严格比大小写 ⇒ `2026-09-16-m10-fix.md` 的"M10" 判不出 ⇒ 本里程碑报告漏归档（ocr-304）
    return re.search(rf"(?:^|[-_./\s]){re.escape(milestone_id)}(?:[-_./\s]|$)",
                     text, re.IGNORECASE) is not None


def check_task_consistency(rel: str, text: str) -> List[Ref]:
    """`status: done` ⇔ `.done.md` 后缀；文件名 milestone ⇔ frontmatter；正文不得复写元数据。"""
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
    if ms and not has_milestone_token(base, ms):
        # 词元判定（不是子串）：`M1` 不得被 `2026-09-01-M10-feat-x.md` 满足——子串检查会让
        # 挂错里程碑的票静默通过（A-01 同形：闸偏松 = 假合规）
        out.append(("TASK_MILESTONE_MISMATCH", f"{rel}: frontmatter milestone '{ms}' not in filename"))
    out.extend(check_task_body_meta_redundant(rel, text))
    out.extend(check_task_closure_record(rel, text))
    return out


# frontmatter 键 → 正文粗体标签（旧双源时代的字段名）
_BODY_FIELD_MAP = {
    "status": "Status",
    "milestone": "Milestone",
    "priority": "Priority",
    "date": "Date",
    "report": "Report",
}


def check_task_body_meta_redundant(rel: str, text: str) -> List[Ref]:
    """正文不得复写 frontmatter 已有的任务元数据（tasks only）。

    frontmatter 是**唯一源**（`docs/tasks/AUTHORING.md`）；所有消费者读它
    （`task_index._scan_task_dir` / `milestone status` / seal 闸 / schema 闸）。
    正文的 `- **Status**: …` 是旧双源时代的副本，只能漂移（人读 body 见 idea、
    工具读 frontmatter 见 done）。

    本检查是**确定性可修**的：删掉冗余正文行即可（无需判断）。
    无 frontmatter 的遗留票跳过（body 即唯一源）。
    """
    if not rel.startswith("docs/tasks/"):
        return []
    from k3dge.engine.pure_schema import parse_frontmatter_pairs, parse_headers

    fm = {k.lower(): v for k, v in parse_frontmatter_pairs(text)}
    if not fm:
        return []
    hdr = parse_headers(strip_fences(text))  # 围栏里的反面样本不是正文复写（ocr-296）
    dup = sorted({k for k in _BODY_FIELD_MAP.values() if k in hdr})
    if not dup:
        return []
    return [(
        "TASK_BODY_META_REDUNDANT",
        f"{rel}: 正文复写 frontmatter 元数据（唯一源＝frontmatter）：{', '.join(dup)}"
        "；删掉这些正文行即可（确定性可修）",
    )]


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
    # 行锚定 + 大小写不敏感：`Status: superseded` 也算（adr_gate._is_superseded 就是 .lower() 判的）；
    # 整篇子串匹配会被散文/围栏示例里的同串误放行（ocr-100）。
    if not re.search(r"^Status:\s*superseded\s*$", old, re.M | re.I):
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
    """字节级检查。返回 `(code, rel)` —— **只产事实**，文案由 `gate_facts` 声明表渲染。

    （旧版把 `rel` 拼进 message，消费方（pre-commit）再用 `msg.split(': ')` 切回来；
    那是对散文的解析。收成事实后 hook 直接 `where=rel`。）
    """
    out: List[Ref] = []
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        return [("MD_ENCODING", rel)]
    if b"\r\n" in raw or b"\r" in raw.replace(b"\r\n", b""):
        out.append(("MD_CRLF", rel))
    return out


def check_markdown_text(text: str, rel: str) -> List[Ref]:
    """Unclosed fences, conflict markers, trailing whitespace, missing final newline."""
    out: List[Ref] = []
    # 围栏闭合用与 `strip_fences` **同一套状态机**（按标记类型分别数奇偶会把 ``` 块里的单条 ~~~ 示例
    # 误判未闭合；缩进/引用前缀的定义两处也要一致，ocr-101）。
    in_fence: Optional[str] = None
    for ln in text.splitlines():
        m = re.match(r"^(`{3,}|~{3,})", ln)
        if m:
            fence = m.group(1)[0] * 3
            if in_fence is None:
                in_fence = fence
            elif ln.startswith(in_fence):
                in_fence = None
    if in_fence is not None:
        out.append(("MD_FENCE_UNCLOSED", f"{rel}: unclosed {in_fence} code fence"))
    # conflict markers: ======= only counts inside an open <<<<<<< block
    # (bare ======= lines are legal setext headings)；先在**去围栏**的文本上扫（示例不是真冲突，ocr-102）。
    in_conflict = False
    for ln in strip_fences(text).splitlines():
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
            out.append(("ORPHAN_SPEC", rel))
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
            out.append(("ORPHAN_TEST", rel))
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
            out.append(("ORPHAN_ADR", f"docs/adr/{p.name}"))
    return out


# --- 新建受管文档的首次排查闸（用户裁定 2026-09-19：阻断，只第一次） ---

#: 由确定性流程生成的受管文档前缀：各有权威生成源（sync / task create / 流程落盘），
#: 不存在"值不值得建"的主观判断 ⇒ 不排查。剩下的（adr / memo / guides / architecture /
#: protocols / incidents / branches）才是人/agent 主观撰写的。
DETERMINISTIC_DOC_PREFIXES: Tuple[str, ...] = (
    "docs/generated/",   # k3dge sync 生成
    "docs/specs/",       # 契约哈希 / spec 由 sync 回写
    "docs/tasks/",       # k3dge task create 生成
    "docs/reviews/",     # 审计报告 / 收摊清单由流程落盘
)

#: **init 下发件**（`k3dge init` 从 `templates/assets` 写入）：内容是 k3dge 作者写的、不是本仓作者的
#: "新建决策" ⇒ 不进排查面。否则下游仓**第一次提交必被 `DOC_NEW_UNSCREENED` 拦**（实测 2026-09-21：
#: 全新 init 仓 staged 全部文件 → guides/protocols 4 件齐报），那与"把排查送到动手那一刻"的立意相反。
INIT_DELIVERED_DOCS: Tuple[str, ...] = (
    "docs/architecture/overview.md",
    "docs/protocols/audit_default.md",
    "docs/protocols/verify_default.md",
    "docs/protocols/quality_default.md",
    "docs/guides/mcp-bridge.md",
    "docs/guides/downstream.md",
)

#: 排查回执（ephemeral，已在 .gitignore）：一个文件一张回执，只活到本次提交过闸。
SCREEN_ACK_REL = ".protocol-ack/doc-screen"


def is_screenable_new_doc(rel: str) -> bool:
    """该新增路径是否属"主观撰写的受管文档"（需要首次排查）。"""
    if not rel.startswith("docs/") or not rel.endswith(".md"):
        return False
    name = Path(rel).name
    if name in AUX_NAMES or name.startswith("."):
        return False
    if "archive" in Path(rel).parts:
        return False
    if rel in INIT_DELIVERED_DOCS:
        return False   # init 下发件：k3dge 作者写的，不是本仓的新建决策
    return not any(rel.startswith(pre) for pre in DETERMINISTIC_DOC_PREFIXES)


def screen_ack_path(workspace: Path, rel: str) -> Path:
    import hashlib

    # 折叠不是单射：`/` 与 `-` 折成同一字符 ⇒ `docs/guides/a-b.md` 与 `docs/guides/a/b.md`
    # 共享一份回执，一份排查做完另一份也"免了"（453）⇒ 名字尾部带原路径摘要
    slug = re.sub(r"[^A-Za-z0-9._-]", "-", rel)
    sig = hashlib.sha1(rel.encode("utf-8", "surrogatepass")).hexdigest()[:10]
    return Path(workspace) / SCREEN_ACK_REL / f"{slug}.{sig}.ack"


def find_unscreened_new_docs(workspace: Path, added_rels) -> List[Ref]:
    """新增受管文档中，尚无排查回执的 ⇒ `(code, path)`（每个文件只拦一次）。

    判"值不值得建"是**判断主体的事**（进程判不了语义覆盖/子项关系）；本闸只负责
    把这件事**送到动手那一刻**并拦住一次，制造排查动力。回执后不再提示。

    返回的第二项是**事实**（路径），不是文案——文案/选项/档位由 `gate_facts` 声明，
    消费者（`scripts/pre-commit`）查表渲染。
    """
    out: List[Ref] = []
    for rel in added_rels:
        if not is_screenable_new_doc(rel):
            continue
        try:
            if screen_ack_path(workspace, rel).is_file():
                continue
        except OSError:
            continue
        # 只产 code + 事实（路径）；文案/options/档位归 `gate_facts` 声明面（内容/流程解耦）
        out.append(("DOC_NEW_UNSCREENED", rel))
    return out


def screen_target_exists(workspace: Path, into: str) -> bool:
    """回执声称"并入 X"时，X 必须真的存在——否则回执记的是一个不存在的去向。

    C 线残渣修复（票 doc_strategy_five_points）：此前 `--into` 不校验，回执可以写
    `merged-into docs/adr/9999-nope.md` 而无人发现；下一轮读回执的人只会困惑。
    """
    target = str(into or "").strip()
    if not target:
        return False
    if not inside_workspace(Path(workspace), target):
        return False      # 越界去向（`.git/HEAD` 之类）也能"满足"回执 ⇒ 闸对该路径永久沉默（ocr-297）
    return (Path(workspace) / target).is_file()


def record_screen_ack(workspace: Path, rel: str, *, into: Optional[str] = None) -> Path:
    """写排查回执（结论二值：并入某目标 / 确认新建）。不做语义判断，只记事实。

    调用方（CLI）在写入前用 `screen_target_exists()` 校验 `--into`；本函数只记。
    """
    import datetime

    path = screen_ack_path(workspace, rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    path.write_text(
        f"path: {rel}\nacked_at: {stamp}\n"
        f"conclusion: {'merged-into ' + into if into else 'new-no-overlap'}\n",
        encoding="utf-8",
    )
    return path


# --- ADR 编号退役账本（docs/adr/obsolete/README.md 的「永久退役号」表）---

_RETIRED_LEDGER_REL = "docs/adr/obsolete/README.md"
_RETIRED_ROW_RE = re.compile(r"^\|\s*(\d{4})\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|", re.MULTILINE)
_ADR_NUM_RE = re.compile(r"^(\d{4})-")


def retired_adr_numbers(workspace: Path) -> dict:
    """退役号 → {was, how, dest}。账本＝`docs/adr/obsolete/README.md` 的表（唯一源）。

    「曾被复用的号（存量不追）」那张表也在同一文件里，但它的行是 `| 号 | 旧占用 | 现役 |`
    三列且**号现役** ⇒ 由 `_live_adr_numbers` 排除，不会被当成退役号。
    """
    path = Path(workspace) / _RETIRED_LEDGER_REL
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        # 退役账本是三个 ADR 闸的唯一源：读不动就静默空 ⇒ 复用号/孤儿号全部漏判（ocr-298）
        print(f"[pure_refs] WARN: 退役账本不可读（{type(exc).__name__}: {exc}）⇒ 本轮按空账处理",
              file=sys.stderr)
        return {}
    # 只读「永久退役号」那一段，避免把"曾被复用"表里的现役号也收进来
    seg = text.split("## 永久退役号", 1)
    if len(seg) < 2:
        if _RETIRED_ROW_RE.search(text):
            print("[pure_refs] WARN: 退役账本有表行但缺『## 永久退役号』标记 ⇒ 按空账处理（标题漂了）",
                  file=sys.stderr)
        return {}
    seg = seg[1].split("### 曾被复用的号", 1)[0]
    out: dict = {}
    for num, was, how, dest in _RETIRED_ROW_RE.findall(seg):
        out[num] = {"was": was, "how": how, "dest": dest}
    return out


def _live_adr_numbers(workspace: Path) -> set:
    d = Path(workspace) / "docs" / "adr"
    if not d.is_dir():
        return set()
    return {m.group(1) for p in d.glob("*.md") if (m := _ADR_NUM_RE.match(p.name))}


def _obsolete_adr_numbers(workspace: Path) -> set:
    d = Path(workspace) / "docs" / "adr" / "obsolete"
    if not d.is_dir():
        return set()
    return {m.group(1) for p in d.glob("*.md") if (m := _ADR_NUM_RE.match(p.name))}


def accounted_adr_numbers(workspace: Path) -> set:
    """本仓已经解释过的号：现役文件 ∪ obsolete 墓碑 ∪ 退役账本。"""
    return _live_adr_numbers(workspace) | _obsolete_adr_numbers(workspace) | set(retired_adr_numbers(workspace))


def check_adr_number_holes(workspace: Path) -> List[Ref]:
    """1..最大号之间不得有空洞。

    空洞＝既没有现役文件，也没有退役墓碑。k3dit 在只有 0001–0007 时直接新建 0028
    就是这种跳号（去占了别的仓的下一个号）。下一号只能是 max+1。
    """
    nums = accounted_adr_numbers(workspace)
    if not nums:
        return []
    ints = sorted(int(n) for n in nums)
    holes = [i for i in range(1, ints[-1] + 1) if f"{i:04d}" not in nums]
    if not holes:
        return []
    first = holes[0]
    adr = Path(workspace) / "docs" / "adr"
    above = sorted(
        (int(m.group(1)), p.name)
        for p in adr.glob("*.md")
        if (m := _ADR_NUM_RE.match(p.name)) and int(m.group(1)) > first
    )
    rel = f"docs/adr/{above[0][1]}" if above else "docs/adr"
    shown = ", ".join(f"{n:04d}" for n in holes[:8])
    if len(holes) > 8:
        shown += f" …共 {len(holes)} 个"
    return [("ADR_NUMBER_HOLE",
             f"{rel}: 号池有空洞 {shown}（最大号 {ints[-1]:04d}）。"
             f"每个号必须是现役文件、obsolete 墓碑或退役账本；下一号只能是 max+1，不能跳去别的仓的号")]


def check_adr_number_reuse(workspace: Path, rel: str) -> List[Ref]:
    """新 ADR 不得占用退役号（`Numbers are never reused` 的机检半边）。

    退役面有两处，都算：`obsolete/*.md` 真文件（baseline 之后）+ 账本表（baseline 之前
    物理删除的 13 个号）。现役号之间的重号由 schema 的 `unique` 规则（`DOC_SCHEMA_INVALID`）管，不在此。
    """
    name = Path(rel).name
    m = _ADR_NUM_RE.match(name)
    if not m or not rel.startswith("docs/adr/") or "obsolete" in Path(rel).parts:
        return []
    num = m.group(1)
    ledger = retired_adr_numbers(workspace)
    if num in ledger:
        info = ledger[num]
        return [("ADR_NUMBER_REUSE",
                 f"{rel}: 号 {num} 已永久退役（曾是 {info['was']}；{info['how']} → {info['dest']}）；"
                 f"取 max(adr ∪ obsolete ∪ 账本)+1")]
    obs = Path(workspace) / "docs" / "adr" / "obsolete"
    if obs.is_dir() and list(obs.glob(f"{num}-*.md")):
        return [("ADR_NUMBER_REUSE",
                 f"{rel}: 号 {num} 已在 docs/adr/obsolete/ 退役；不得再分配（Numbers are never reused）")]
    return []


def check_adr_ref_retired(workspace: Path, rel: str, text: str) -> List[Ref]:
    """引用退役号 ⇒ 报去向（比 DANGLING 更有用：号是"曾存在过"，不是"写错了"）。

    只对**非现役**的退役号报；现役号（含 baseline 前被复用的 6 个）走 `check_dangling_adr`
    的存在性判断——存量不追（用户裁定 2026-09-19）。

    **不扫 `docs/reviews/` 与 `archive/`**：那是 append-only 的审计/历史记录，引用的是
    "当时那条 ADR"，改写它等于篡改当时的事实（实测：全仓非归档文档只有 2 处命中，都在
    reviews 里，且都是历史报告正文）。
    """
    parts = set(Path(rel).parts)
    if "archive" in parts or rel.startswith("docs/reviews/"):
        return []
    live = _live_adr_numbers(workspace)
    ledger = retired_adr_numbers(workspace)
    out: List[Ref] = []
    for num in _adr_numbers_to_resolve(text):
        if num in live or num not in ledger:
            continue
        info = ledger[num]
        out.append(("ADR_REF_RETIRED",
                    f"{rel}: ADR-{num} 已退役（曾是 {info['was']}）；去向 {info['dest']}"
                    f"——引用改指去向，或去掉 `ADR-` 前缀写成历史事件"))
    return out


# --- 关票必须留"结案记录"（防"done 票无落地痕迹"这一类漂移）---

#: 结案类标题的闭集（唯一源）。闸只验"有没有写"，内容归人/agent——
#: **不做自动填充**：自动写占位等于制造伪合规（docs/tasks/archive/…feat-protocol-resolver
#: 的既有教训：不把不可机检项伪装成可机检）。
_CLOSURE_HEADINGS = ("## 结案", "## 落地", "## 关闭理由", "## 收尾", "## 回填", "## 进度")


def check_task_closure_record(rel: str, text: str) -> List[Ref]:
    """`*.done.md` 必须含结案类段且有**非空内容**。

    为何：票是自包含事实源；关票时不写落地/结案，后续就出现"票里说待办、实际已做"
    的漂移（实测 2026-09-19：三张票的 blocking 与验收段全漂了，全靠人工扫才发现）。
    闸管两件事：段在不在、段后有没有内容；至于内容对不对仍归人（k3dit/审计）。
    """
    if not rel.startswith("docs/tasks/") or not rel.endswith(".done.md"):
        return []
    if Path(rel).name in AUX_NAMES:   # 零依赖层：不 import milestone_files
        return []
    lines = text.splitlines()
    empty_at = None
    for i, ln in enumerate(lines):
        # 前缀匹配：允许标题带限定词（`## 落地（2026-09-19，①-⑥ 全部执行）` 也算数）
        hit = next((h for h in _CLOSURE_HEADINGS if ln.strip().startswith(h)), None)
        if not hit:
            continue
        # 段界＝下一个 `## ` 标题：旧实现取"标题之后全文"⇒首个结案段空、后面有别的段也算过（假阴性），
        # 模板留白的空 `## 进度` 又会被当结案段直接判错（假阳性，ocr-299）
        j = i + 1
        while j < len(lines) and not lines[j].startswith("## "):
            j += 1
        if "\n".join(lines[i + 1:j]).strip():
            return []
        empty_at = empty_at or ln.strip()
    if empty_at:
        return [("TASK_CLOSURE_MISSING",
                 f"{rel}: 结案段 `{empty_at}` 是空的——闸只验有没有写，内容归人")]
    return [("TASK_CLOSURE_MISSING",
             f"{rel}: done 票缺结案记录（需 {' / '.join(_CLOSURE_HEADINGS)} 之一且有内容）"
             f"——票是自包含事实源，不写落地痕迹后续就会漂")]


# --- 退役 ADR 必须写清去向（合并路径既无自动化也无闸，本函数补后者）---

#: 能被当作"去向"的 frontmatter 键（唯一源）。
_DEST_KEYS = ("merged-into", "merged_into", "superseded_by", "Superseded-by")
_DEST_STATUSES = ("Rejected",)   # 被否决＝"从未生效"，status 本身即去向事实（无需指针）


def check_retired_adr_dest(rel: str, text: str) -> List[Ref]:
    """`docs/adr/obsolete/*.md`（非 aux）必须留下"这条去哪了"的事实。

    为何要闸：`reconcile_supersedes` 只自动化 `Supersedes:` 与 `Status: Rejected` 两条路；
    **合并没有自动化**（历史上写在宿主 ADR 的 Note + commit message 里），而 13 个永久退役号里
    12 个是合并 ⇒ baseline 之后若忘了写去向，退役卡片会显示 `retired` 但去向为空，
    读者仍找不到"这条去哪了"——正是退役账本要修的失效模式。`merged-into` 此前**全仓只有读、没有写方、也没有闸**。

    合法形态（闭集）：`merged-into: <宿主与小节>` / `superseded_by: ADR-XXXX` /
    `Status: Rejected`（提议被否，从未生效——"去哪"就是"没去哪"）。
    **不判去向对不对**（那要读懂 ADR 内容），只验"写了没写"。
    """
    parts = Path(rel).parts
    if "obsolete" not in parts or not rel.startswith("docs/adr/") or not rel.endswith(".md"):
        return []
    if Path(rel).name in AUX_NAMES:      # 账本 README / 模板：承载的是表格与约定，不是单条退役
        return []
    fm = {k.strip().lower(): v.strip() for k, v in parse_frontmatter_pairs(text)}
    for key in _DEST_KEYS:
        if fm.get(key.lower()):
            return []
    if fm.get("status", "").strip() in _DEST_STATUSES:
        return []
    return [("ADR_RETIRED_NO_DEST",
             f"{rel}: 退役 ADR 未写去向（需 `merged-into:` / `superseded_by:` / `Status: Rejected` 之一）"
             f"——合并没有自动化，忘写就会变成'retired 但不知去哪'")]


# --- 归档去向标记（ADR-0023 §2.2；warn 档，观察用）---

_ARCHIVE_MARKERS = ("Superseded-by", "Legacy note")


def find_unguarded_archives(workspace: Path, changed_rels) -> List[Ref]:
    """本轮改动集里落进 `docs/**/archive/` 但缺去向标记的文档（ADR-0023 §2.2）。

    **只对本轮增量**（存量不批量灌噪声），warn 档（不阻断）——归档是有意为之的动作，
    缺标记说明"为什么归档"没写下来，判定归人。
    原住 `engine/doc_audit._new_archive_without_note`；该模块（doc-audit 报告+票路径）
    已按 ADR-0022 §2.2 🅰1 退休，此检查迁到零依赖层由 pre-commit 消费。
    """
    out: List[Ref] = []
    for rel in changed_rels:
        parts = Path(rel).parts
        if "archive" not in parts or not rel.endswith(".md"):
            continue
        try:
            text = (Path(workspace) / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if any(m in text for m in _ARCHIVE_MARKERS):
            continue
        out.append(("ARCHIVE_NO_DEST", rel))
    return out


# --- incidents 身份单一源（文件名；frontmatter 不放复写字段）---


def check_incident_id_redundant(rel: str, text: str) -> List[Ref]:
    """`docs/incidents/*.md` 的 frontmatter 不得有 `id:` —— 身份的唯一源是文件名。

    实测（2026-09-19）：11 份 incident 里 10 份的 `id:` 与文件名一致（纯副本），
    1 份**不一致**——`INC-20260826-REG-m3-task-truncate.md` 的 `id: INC-20260826-REG-01`。
    没有任何消费者读它（`doc_catalog._card_id` 用 `path.stem`；`.schema.json` 也没有 id 规则）
    ⇒ 漂了无人知。与 tasks 正文 `- **Status**:` 副本同类（那批已收：`TASK_BODY_META_REDUNDANT`）。
    """
    if not rel.startswith("docs/incidents/") or not rel.endswith(".md"):
        return []
    if Path(rel).name in AUX_NAMES:
        return []
    fm = {k.strip().lower() for k, _v in parse_frontmatter_pairs(text)}
    if "id" not in fm:
        return []
    return [("INCIDENT_ID_REDUNDANT",
             f"{rel}: frontmatter 的 `id` 是文件名的副本（身份唯一源＝文件名）；删掉它")]
