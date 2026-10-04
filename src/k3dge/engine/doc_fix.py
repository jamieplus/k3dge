"""文档规约化的**确定性修复**（闭集规则；幂等；可预演）。

范围＝`gate_facts` 里 `fix=="deterministic"` 且**文件级**的那几条：

    MD_TRAILING_WS          删行尾空白
    MD_CRLF                 CRLF → LF
    MD_NO_FINAL_NEWLINE     末尾补换行
    TASK_BODY_META_REDUNDANT 删正文里复写 frontmatter 的元数据行

其余 deterministic 码由**既有命令**修（不进本模块，避免第二实现）：
`DOC_INDEX_STALE` / `CONTRACT_DRIFT` / `CONTRACT_HASH_MISSING` / `ADR_SUPERSEDE_UNRECONCILED`
→ `k3dge sync`；`VERSION_MISMATCH` → `k3dge version bump`。

不做什么（重要）：
- **不碰散文**（章节重排、措辞、`Context 无 timeline` 这类要读懂语义的）——那是外部透镜在
  里程碑轮的事（ADR-0022 §2.2 🅰1.3）。
- **不猜编码**（`MD_ENCODING` 属判断类：源编码判断不了，猜错会损坏文件）。
- **不自动填充占位**（自动写"待办"等于伪合规）。

为何挂 `docs_normalized` 闸而不在 seal 的动作环里自动改文档：改在审计闭环**之后**会
使刚闭环的审计证据（审的是旧文档）失效 ⇒ 规约化必须发生在封板之前，由 `[NEXT]` 引导的
主动动作完成（`k3dge doc fix`），seal 只验"做没做"。
"""
from __future__ import annotations

import contextlib
import re
from pathlib import Path
from typing import Dict, List, Tuple

from k3dge.engine import pure_refs

#: 本模块能修的文件级规则（闭集；与 `gate_facts.fix=="deterministic"` 交叉核对，见测试）
FIXABLE_RULES: Tuple[str, ...] = (
    "MD_TRAILING_WS",
    "MD_CRLF",
    "MD_NO_FINAL_NEWLINE",
    "TASK_BODY_META_REDUNDANT",
    # ADR amend/footnote 形态（2026-09-24）：这些都是**固定规则**，不需要 agent 参与
    "ADR_AMEND_ORDER",            # 条目前缀补齐 + 按 append 序（升序）重排
    "ADR_FOOTNOTE_TAIL",          # 脚注定义移到文末
    "ADR_FOOTNOTE_LINE",          # 脚注定义的续行并回同一行（换行会截断脚注）
    "ADR_FOOTNOTE_SEQ",           # 小标号按正文出现序重排为 1..k
    "ADR_AMEND_MARKER_TEXT",      # 正文里的"（🅰N，…）"→ 对应脚注引用
    "INCIDENT_ID_REDUNDANT",      # 删 frontmatter 里与文件名重复的 `id:` 行（fix_hint 早就这么写，缺实现）
)

#: 由**既有命令**修的 deterministic 码（不进本模块，避免第二实现）——登记表＝机检的消费者面。
#: 新码若声明 `fix=deterministic`，必须要么进 FIXABLE_RULES（本模块能改），要么进 BY_COMMAND。
BY_COMMAND: Dict[str, str] = {
    "DOC_INDEX_STALE": "k3dge sync",
    "CONTRACT_DRIFT": "k3dge sync",
    "CONTRACT_HASH_MISSING": "k3dge sync",
    "ADR_SUPERSEDE_UNRECONCILED": "k3dge sync",
    "VERSION_MISMATCH": "k3dge version bump",
    "EXTRACTOR_PLUGIN_STALE": "k3dge extractor sync",
    "SYMBOL_INDEX_STALE": "k3dge index",
    "DOCS_GENERATED_STALE": "k3dge sync",
    "MCP_JSON_PEER_MISSING": "k3dge mcp sync",
}

#: 不扫的目录：派生面/历史面/退役面（各有其权威源，改它们没意义或有害）
_SKIP_PARTS = frozenset({"archive", "generated", "obsolete"})

_BODY_META_LINE_RE = re.compile(r"^-\s+\*\*(Status|Milestone|Priority|Date|Report)\*\*:")


def _strip_body_meta(text: str) -> str:
    """删正文元数据副本行——**跳过围栏代码块**（``` / ~~~ 内的示例是正文，不是副本；ocr-064）。"""
    out: List[str] = []
    fence = False
    for ln in text.splitlines(keepends=True):
        stripped = ln.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            fence = not fence
            out.append(ln)
            continue
        if not fence and _BODY_META_LINE_RE.match(ln):
            continue
        out.append(ln)
    return "".join(out)


def managed_docs(workspace: Path) -> List[Path]:
    """受管主观文档（`docs/**/*.md` 去掉 aux / archive / generated / obsolete）。"""
    d = Path(workspace) / "docs"
    if not d.is_dir():
        return []
    out: List[Path] = []
    for p in sorted(d.rglob("*.md")):
        if p.name in pure_refs.AUX_NAMES:
            continue
        if _SKIP_PARTS & set(p.relative_to(d).parts):
            continue
        out.append(p)
    return out


def _codes(rel: str, text: str) -> List[str]:
    codes = [c for c, _ in pure_refs.check_markdown_text(text, rel)]
    codes += [c for c, _ in pure_refs.check_task_body_meta_redundant(rel, text)]
    if rel.startswith("docs/incidents/"):
        # 此前漏接 ⇒ `INCIDENT_ID_REDUNDANT` 分支是死代码（检测在 doc_gate/doc_catalog，修复器在这，ocr-066）。
        codes += [c for c, _ in pure_refs.check_incident_id_redundant(rel, text)]
    if rel.startswith("docs/adr/"):
        from k3dge.engine.pure_schema import check_amend

        codes += [c for c, _, _ in check_amend({"enabled": True}, {}, Path(rel).name, text)]
    return [c for c in codes if c in FIXABLE_RULES]


def _fix(rel: str, text: str, codes: List[str]) -> Tuple[str, List[str]]:
    """按闭集规则改写文本；返回 (新文本, 实际应用的规则)。规则间无冲突（字节级/删行）。

    `applied` 只收**真改了文本**的规则：按"检测到"列会把"没动过"也报成已修，
    门禁复查仍红时报告与事实分叉（ocr2-055）。
    """
    # marker_text 会在正文里**新增/改写脚注引用** ⇒ 改变出现序，而 footnote_seq 的小标号是按
    # 正文首现序算的：seq 先跑、marker_text 后跑 ⇒ 修完又不服从 seq（不幂等，需再跑一遍）。
    # 所以顺序必须是 marker_text 在前、seq 在后（ocr-232）。
    _order = [
        ("MD_CRLF", lambda s: s.replace("\r\n", "\n").replace("\r", "\n")),
        ("MD_TRAILING_WS", lambda s: re.sub(r"[ \t]+$", "", s, flags=re.MULTILINE)),
        ("TASK_BODY_META_REDUNDANT", _strip_body_meta),
        ("INCIDENT_ID_REDUNDANT", _fix_incident_id),
        ("ADR_AMEND_ORDER", _fix_amend_order),
        ("ADR_FOOTNOTE_TAIL", _fix_footnote_tail),
        ("ADR_FOOTNOTE_LINE", _fix_footnote_line),
        ("ADR_AMEND_MARKER_TEXT", _fix_marker_text),
        ("ADR_FOOTNOTE_SEQ", _fix_footnote_seq),
        ("MD_NO_FINAL_NEWLINE", lambda s: s.rstrip("\n") + "\n"),
    ]
    out, applied = text, []
    for _code, _fn in _order:
        if _code in codes:
            _new = _fn(out)
            if _new != out:
                applied.append(_code)
            out = _new
    return out, applied


def _fix_incident_id(text: str) -> str:
    """删 frontmatter 里的 `id:` 行（身份唯一源＝文件名；该键无消费者）。只在首个 frontmatter 块内改。"""
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return text
    fm = [ln for ln in m.group(1).splitlines() if not re.match(r"^\s*id\s*:", ln, re.IGNORECASE)]
    return "---\n" + "\n".join(fm) + "\n---\n" + text[m.end():]


def _fix_amend_order(text: str) -> str:
    """补 `🅰N |` 前缀 + 按 append 序（升序）重排 `Amended-by` 列表（确定性）。"""
    # 检测端 `((?:\s+-.*(?:\n|$))+)` 认"行尾即 EOF 无换行"的块：修复端必须同口径，
    # 否则"检出→修不动→写盘（仅末换行变了）→报已修"，同一码要跑两遍（ocr2-240）。
    # 重复编号排序修不动：`_fix` 只收真改了文本的规则，不会谎报 applied。
    m = re.search(r"^Amended-by:\s*\n((?:\s+-.*(?:\n|$))+)", text, re.M)
    if not m:
        return text
    entries = [ln.rstrip("\n") for ln in m.group(1).splitlines() if ln.strip()]
    fixed = []
    for ln in entries:
        mm = re.match(r"^(\s*-\s*)(\d+)(\s*\|.*)$", ln)
        fixed.append(f"{mm.group(1)}🅰{mm.group(2)}{mm.group(3)}" if mm else ln)
    def _seq_key(ln: str) -> int:
        # 判据用 `"🅰" in ln`、取值用 `.group(1)` ⇒ 含 🅰 但后面不是数字的行（正文被并入）
        # 会让 re.search 返回 None → AttributeError 冒出 apply()（ocr-233）。
        m = re.search(r"🅰(\d+)", ln)
        return int(m.group(1)) if m else 0

    fixed.sort(key=_seq_key)
    return text[:m.start(1)] + "\n".join(fixed) + "\n" + text[m.end(1):]


def _fix_footnote_tail(text: str) -> str:
    """把 `[^🅰…]:` 定义块（含缩进续行）整体移到文末（确定性；保持定义间原有顺序）。

    围栏代码块内的同形行不得动：那是示例字面量，不是脚注定义（ocr2-056）。
    注意：本函数只跟踪 ``` 围栏切换，未对 ~~~  fences 做等价处理——若引入了 ~~~ 围栏块，
    同形行判据需扩展（与 `_strip_body_meta` 的两栅栏口径暂不完全一致）。
    """
    lines = text.splitlines()
    blocks: List[List[str]] = []
    keep: List[str] = []
    i, _fence = 0, False
    while i < len(lines):
        if lines[i].strip().startswith("```"):
            _fence = not _fence
            keep.append(lines[i])
            i += 1
            continue
        if lines[i].startswith("[^🅰") and not _fence:
            blk = [lines[i]]
            i += 1
            while i < len(lines) and (not lines[i].strip() or lines[i].startswith((" ", "\t"))):
                blk.append(lines[i])
                i += 1
            while blk and not blk[-1].strip():
                blk.pop()
            blocks.append(blk)
            continue
        keep.append(lines[i])
        i += 1
    while keep and not keep[-1].strip():
        keep.pop()
    for blk in blocks:
        keep += [""] + blk
    return "\n".join(keep).rstrip("\n") + "\n"


def _footnote_continuation(line: str) -> bool:
    """**委托 `pure_schema`**：检测端与修复端不得各持一份判据（415）。"""
    from k3dge.engine.pure_schema import _footnote_continuation as _detected

    return _detected(line)


def _fix_footnote_line(text: str) -> str:
    """把脚注定义的续行并回定义行。Markdown 在未缩进的换行处结束脚注，后文掉进正文。"""
    lines = text.splitlines()
    out: List[str] = []
    i = 0
    while i < len(lines):
        if re.match(r"^\[\^🅰\d+\.\d+\]:", lines[i]):
            parts = [lines[i].rstrip()]
            i += 1
            while i < len(lines) and _footnote_continuation(lines[i]):
                parts.append(lines[i].strip())
                i += 1
            out.append(" ".join(parts))
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def _fix_footnote_seq(text: str) -> str:
    """同一修订号的小标号按正文第一次出现序改成 1..k。定义随引用一起改，单遍替换不连环。"""
    lines = text.splitlines()
    order: Dict[int, List[int]] = {}
    for line in lines:
        if line.startswith("[^🅰"):
            continue
        for m in re.finditer(r"\[\^🅰(\d+)\.(\d+)\]", line):
            n, minor = int(m.group(1)), int(m.group(2))
            got = order.setdefault(n, [])
            if minor not in got:
                got.append(minor)
    # 定义行不参与"正文首现序"是对的，但**孤儿定义**（只定义未引用）也得占号：否则重排后的引用
    # 可能正好撞上它 ⇒ 同一 `[^🅰N.m]` 两条定义——是"修坏"不是"修不动"（ocr-234）。
    defined: Dict[int, List[int]] = {}
    for line in lines:
        dm = re.match(r"^\[\^🅰(\d+)\.(\d+)\]:", line) if line.startswith("[^🅰") else None
        if dm:
            got = defined.setdefault(int(dm.group(1)), [])
            if int(dm.group(2)) not in got:
                got.append(int(dm.group(2)))
    for n, defs in defined.items():
        got = order.setdefault(n, [])
        for d in defs:
            if d not in got:
                got.append(d)
    mapping = {(n, old): i for n, minors in order.items() for i, old in enumerate(minors, 1)}
    if not mapping or all(new == old for (_n, old), new in mapping.items()):
        return text

    def repl(m: "re.Match[str]") -> str:
        n, old = int(m.group(1)), int(m.group(2))
        return f"[^🅰{n}.{mapping.get((n, old), old)}]{m.group(3) or ''}"

    return re.sub(r"\[\^🅰(\d+)\.(\d+)\](:?)", repl, text)


def _fix_marker_text(text: str) -> str:
    """`（🅰N，…）` → 该 N 的**唯一**脚注引用；N 有多个定义或无定义时不动（留闸报）。"""
    defs: Dict[str, List[str]] = {}
    for m in re.finditer(r"^\[\^(🅰\d+)\.(\d+)\]:", text, re.M):
        defs.setdefault(m.group(1), []).append(m.group(2))

    def sub(m):
        n = m.group(1)
        ids = defs.get(n) or []
        return f"[^{n}.{ids[0]}]" if len(ids) == 1 else m.group(0)

    return re.sub(r"（(🅰\d+)[，,][^）]*）", sub, text)


def scan(workspace: Path) -> List[Dict[str, str]]:
    """当前可确定修的偏差清单（`[{"path", "rule"}]`）；空 ⇒ 规约已满足（`docs_normalized` 过）。"""
    out: List[Dict[str, str]] = []
    for p in managed_docs(workspace):
        rel = p.relative_to(workspace).as_posix()
        try:
            with open(p, encoding="utf-8", newline="") as fh:   # newline="" 保留 CRLF 以便检测/修 MD_CRLF
                text = fh.read()
        except (OSError, UnicodeDecodeError):
            continue          # 编码问题属判断类，不在本集
        codes = _codes(rel, text.replace("\r\n", "\n").replace("\r", "\n"))
        if "\r" in text and "MD_CRLF" in FIXABLE_RULES:        # MD_CRLF 只在字节层可见（ocr-065）
            codes = list(dict.fromkeys(codes + ["MD_CRLF"]))
        for code in codes:
            out.append({"path": rel, "rule": code})
    return out


def apply(workspace: Path, *, dry_run: bool = False) -> Dict[str, object]:
    """按闭集规则修；`dry_run=True` 只报不改。返回报告（幂等：再跑一次应为空）。"""
    fixed: List[Dict[str, str]] = []
    remaining = 0
    for p in managed_docs(workspace):
        rel = p.relative_to(workspace).as_posix()
        try:
            with open(p, encoding="utf-8", newline="") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError):
            continue
        codes = _codes(rel, text.replace("\r\n", "\n").replace("\r", "\n"))
        if "\r" in text and "MD_CRLF" in FIXABLE_RULES:
            codes = list(dict.fromkeys(codes + ["MD_CRLF"]))
        if not codes:
            continue
        new, applied = _fix(rel, text, codes)
        if new == text or not applied:
            remaining += len(codes)      # 检测到但无可改（理论不可达，保守计）
            continue
        # 本遍修不完的码不得计零：重算改后文本的残留（如 EOF 的 amend 块、多定义 marker），
        # 否则"一遍里半修半留"的文件被报成 remaining=0，而 scan/seal 照样红（ocr2-241）。
        leftover = _codes(rel, new.replace("\r\n", "\n").replace("\r", "\n"))
        if "\r" in new and "MD_CRLF" in FIXABLE_RULES:
            leftover = list(dict.fromkeys(leftover + ["MD_CRLF"]))
        remaining += len(leftover)
        if not dry_run:
            try:
                # 确定性临时名 + 无 fsync + 继承 tmp 权限 + 只清 OSError：并发 doc fix 共用
                # 同一 `.k3dge-tmp` 会互相覆盖半写内容，崩溃/断电丢半截文件，还顺手改权限（ocr2-242）。
                import os as _os
                import tempfile as _tf

                _fd, _tmp = _tf.mkstemp(dir=str(p.parent), prefix=".k3dge-", suffix=".tmp")
                try:
                    with _os.fdopen(_fd, "w", encoding="utf-8", newline="") as fh:
                        fh.write(new)
                        fh.flush()
                        _os.fsync(fh.fileno())
                    try:
                        _os.chmod(_tmp, p.stat().st_mode & 0o777)
                    except OSError:
                        pass
                    _os.replace(_tmp, p)
                except BaseException:
                    with contextlib.suppress(OSError):
                        _os.unlink(_tmp)
                    raise
            except OSError:
                remaining += len(codes)
                continue
        for rule in applied:
            fixed.append({"path": rel, "rule": rule})
    return {
        "dry_run": dry_run,
        "fixed": fixed,
        "changed_files": sorted({f["path"] for f in fixed}),
        "remaining": remaining,
    }
