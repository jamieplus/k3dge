"""审计钉语法 v2 —— findings 的树侧介质（棘轮循环；契约 §8）。

角色：树上放**指针＋状态＋判读四格**（一行），账本/报告由 k3dit 收成投影（ADR-0025 §2.7）；
本模块只解析、校验结构、计数——**永不改写**任何文件（去钉在 worktree、apply 属编排侧）。
判读四格 sev/prio/type 的闭集权威在 k3dit `rounds`（本模块不复校词表，避免反向依赖）。

kind:     pending | leftover | disputed | fixnote（修席顺手发现，须审席复核）
open :=   pending + disputed + fixnote            # 结项判据 = open 计零
scope:    @line(缺省) | @file(文件头块内) | @repo(只准住 AUDIT.md)
attr:     [sev=..] [prio=..] [type=..]（v2 固定序，其后为 desc）
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

KINDS = ("pending", "leftover", "disputed", "fixnote", "fixed")
OPEN_KINDS = frozenset({"pending", "disputed", "fixnote"})   # fixed=复核背书待 Hall 拔，非 open
SCOPES = ("line", "file", "repo")
SIDECAR = "AUDIT.md"

# 注释宿主前缀不参与匹配语义（提取只认核心串），但校验头部块归属要用它认注释行。
# 宿主分型：md/html 只认 <!-- -->（反引号里的示例绝不自触发）；代码文件允许行尾注释
#（案发现场就在行尾——指针必须钉得起）。
# v2（ADR-0025 §2.7）：kind 后、desc 前，可选属性段 sev= prio= type=（固定序、闭集；闭集
# 权威在 k3dit rounds，此处只解析结构、不复校词表，避免 k3dge 反向依赖 k3dit）。
_ATTRS = r"(?:[ \t]+sev=(?P<sev>\S+))?(?:[ \t]+prio=(?P<prio>\S+))?(?:[ \t]+type=(?P<type>\S+))?"
MARKER_RE = re.compile(
    r"(?:#|//|<!--)[ \t]*k3dit:(?P<kind>pending|leftover|disputed|fixnote|fixed)[ \t]+"
    r"(?P<id>[A-Za-z0-9][A-Za-z0-9._#-]*)(?:[ \t]*@(?P<scope>line|file|repo)(?![A-Za-z0-9_-]))?"
    + _ATTRS +
    r"[ \t]*(?P<note>[^\n]*?)[ \t]*(?:-->)?[ \t]*$",
    re.M,
)
_COMMENT_LINE_RE = re.compile(r"^\s*(?:#|//|<!--)")
MARKER_RE_MD = re.compile(
    r"<!--[ \t]*k3dit:(?P<kind>pending|leftover|disputed|fixnote|fixed)[ \t]+"
    r"(?P<id>[A-Za-z0-9][A-Za-z0-9._#-]*)(?:[ \t]*@(?P<scope>line|file|repo)(?![A-Za-z0-9_-]))?"
    + _ATTRS +
    r"(?P<note>[^\n]*?)[ \t]*-->[ \t]*$",
    re.M,
)
_SCAN_SUFFIXES = frozenset(
    {".py", ".md", ".js", ".ts", ".tsx", ".go", ".rs", ".java", ".rb", ".toml", ".yaml", ".yml", ".php", ".kt", ".swift", ".c", ".h", ".cc", ".sh"}
)
_SKIP_DIR_PARTS = ("archive", ".git", ".venv", "node_modules", "__pycache__")
# note 上限按 kind：pending 只活在线上、ff 前去钉剥净不上主干，可放宽到 500（够 value/design 理据）；
# 其余 kind（leftover 上主干当长期文献）维持 ≤80（防正文漂）。超 ⇒ 拆成多条钉。
_MAX_NOTE = 80
_MAX_NOTE_PENDING = 500


@dataclass
class Marker:
    file: str
    line: int
    kind: str
    id: str
    scope: str
    note: str
    sev: str = ""    # v2 判读四格（结构解析；闭集校验在 k3dit harvest）
    prio: str = ""
    type: str = ""

    def key(self) -> Tuple[str, str]:
        return (self.id, self.kind)


def _iter_scan_files(workspace: Path, roots: Sequence[str]) -> Iterable[Tuple[str, Path]]:
    for root_rel in roots:
        root = workspace / root_rel
        if not root.exists():
            continue
        for p in sorted(root.rglob("*")):
            if not p.is_file() or p.suffix.lower() not in _SCAN_SUFFIXES:
                continue
            rel = p.relative_to(workspace).as_posix()
            if rel in (SIDECAR,):
                continue
            parts = set(p.relative_to(workspace).parts)
            if parts & set(_SKIP_DIR_PARTS) or rel.startswith(("docs/reviews/", "docs/generated/")):
                continue
            yield rel, p


def head_block_end(lines: Sequence[str]) -> int:
    """首个连续注释块（含空行）的结束行号（0-based 开区间）。允许 shebang/encoding。"""
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped or _COMMENT_LINE_RE.match(lines[i]):
            i += 1
            continue
        break
    return i


# str.splitlines() 的行界（除 \n 外还含 \x0b\x0c\x1c-\x1e\x85\u2028\u2029）——
# parse_text 的行号必须用同一套，否则 worktree.strip_pins 按 splitlines 索引会错位（code-11）。
_LINE_BREAK_RE = re.compile(r"\r\n|[\r\n\v\f\x1c-\x1e\x85\u2028\u2029]")


def _line_starts(text: str) -> list:
    """行首偏移表（与 str.splitlines() 同口径）。一次算好可复用（428）。"""
    starts = [0]
    for bm in _LINE_BREAK_RE.finditer(text):
        starts.append(bm.end())
    return starts


def _line_index_from(starts: list, pos: int) -> int:
    import bisect

    return bisect.bisect_right(starts, pos)


def _line_index(text: str, pos: int) -> int:
    """char offset -> 1-based line number（单点调用；多处请复用 `_line_starts`）。"""
    return _line_index_from(_line_starts(text), pos)


def parse_text(rel: str, text: str, *, max_note: int = _MAX_NOTE,
               max_note_pending: int = _MAX_NOTE_PENDING) -> Tuple[List[Marker], List[str]]:
    lines = text.splitlines()
    hb = head_block_end(lines)
    markers: List[Marker] = []
    problems: List[str] = []
    rx = MARKER_RE_MD if rel.endswith((".md", ".html")) else MARKER_RE
    starts = _line_starts(text)
    for m in rx.finditer(text):
        line_no = _line_index_from(starts, m.start())
        kind = m.group("kind")
        note = m.group("note") or ""
        cap = max_note_pending if kind == "pending" else max_note
        if len(note) > cap:
            problems.append(f"{rel}:{line_no} note 超 {cap} 字符（pending≤{max_note_pending}，"
                            f"其余≤{max_note}；正文超应拆多条钉）")
            note = note[:cap] + "…"
        markers.append(
            Marker(
                file=rel,
                line=line_no,
                kind=kind,
                id=m.group("id"),
                scope=m.group("scope") or "line",
                note=note.strip(),
                sev=(m.group("sev") or "").strip(),
                prio=(m.group("prio") or "").strip(),
                type=(m.group("type") or "").strip(),
            )
        )
    # scope↔位置一致性（规则 3）
    for mk in markers:
        if mk.scope == "file" and mk.line > hb:
            problems.append(f"{mk.file}:{mk.line} @{mk.id} 声明 @file 但不在头部注释块内")

    return markers, problems


def parse_sidecar(text: str) -> Tuple[List[Marker], List[str]]:
    """AUDIT.md：`## k3dit:<kind> <id>@repo <note>` ＋ 可选 `- files:`/`- why:` 行。"""
    markers: List[Marker] = []
    problems: List[str] = []
    cur: Marker | None = None
    for i, raw in enumerate(text.splitlines(), 1):
        if raw.startswith("## "):
            # 锚定标题正文开头：`## 关于 k3dit:pending 的说明` 这类叙述性标题不该被当审计条目（ocr-259）。
            m = re.match(
                r"k3dit:(?P<kind>pending|leftover|disputed|fixnote|fixed)\s+(?P<id>[A-Za-z0-9][A-Za-z0-9._#-]*)\s*"
                r"(?:@(?P<scope>line|file|repo)(?![A-Za-z0-9_-]))?(?P<note>.*?)\s*$",
                raw[3:],
            )
            if not m:
                cur = None        # 非条目标题 ⇒ 结束上一条，后续 `- files:` 不再挂到旧条目（ocr-260）
                continue
            if (m.group("scope") or "line") != "repo":
                problems.append(f"{SIDECAR}:{i} 条目缺 @repo 作用域")
            cur = Marker(SIDECAR, i, m.group("kind"), m.group("id"), "repo", (m.group("note") or "").strip())
            markers.append(cur)
        elif raw.startswith("- files:") and cur is not None:
            cur.note = (cur.note + " | " + raw.split(":", 1)[1].strip()).strip("| ")
    return markers, problems


def extract(workspace: Path, roots: Sequence[str] = ("src", "docs")) -> Tuple[List[Marker], List[str]]:
    from k3dge.engine import gates

    max_note = int(gates.get(workspace, "markers", "max_note"))
    max_note_pending = int(gates.get(workspace, "markers", "max_note_pending"))
    markers: List[Marker] = []
    problems: List[str] = []
    for rel, path in _iter_scan_files(workspace, roots):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as exc:
            # 别再静默少一个文件：审计计数偏低/开放项被漏可能误判可结项（ocr-082）。
            problems.append(f"{rel}: 读取失败（{exc}）——其中钉未计入")
            continue
        ms, ps = parse_text(rel, text, max_note=max_note, max_note_pending=max_note_pending)
        markers.extend(ms)
        problems.extend(ps)
    side = workspace / SIDECAR
    if side.is_file():
        try:
            ms, ps = parse_sidecar(side.read_text(encoding="utf-8"))
            markers.extend(ms)
            problems.extend(ps)
        except (UnicodeDecodeError, OSError) as exc:
            # 根侧车承载 repo-scope 钉；读不出 ⇒ repo 条目整体消失 ⇒ fail-closed（ocr-083）。
            problems.append(f"{SIDECAR}: 读取失败（{exc}）——repo-scope 钉整体缺失")
    problems.extend(validate(workspace, markers))
    return markers, problems


def validate(workspace: Path, markers: Sequence[Marker]) -> List[str]:  # noqa: ARG001（保留接口位）
    problems: List[str] = []
    seen: dict = {}
    for mk in markers:
        if mk.scope == "repo" and mk.file != SIDECAR:
            problems.append(f"{mk.file}:{mk.line} @{mk.id} @repo 只准住 {SIDECAR}")
        bucket = seen.setdefault(mk.id, set())
        bucket.add(mk.file)
    for mid, files in seen.items():
        kinds = {m.kind for m in markers if m.id == mid}
        if len(kinds) > 1:
            problems.append(f"@{mid} 同 ID 挂多种 kind：{sorted(kinds)}")
            continue
        if "leftover" in kinds:
            continue  # 规则 2 例外：leftover 随文件走
        if len(files) > 1:
            problems.append(f"@{mid} 一发现多主锚（{sorted(files)}）——同 ID 只准一个宿主")
    return problems


def counts(markers: Iterable[Marker]) -> dict:
    c = {k: 0 for k in KINDS}
    for m in markers:
        c[m.kind] += 1
    c["open"] = sum(c[k] for k in OPEN_KINDS)
    return c


def open_samples(markers: Sequence[Marker]) -> List[str]:
    return [f"{m.file}#{m.id}" for m in markers if m.kind in OPEN_KINDS]


def closure_ok(markers: Sequence[Marker]) -> Tuple[bool, dict]:
    """结项判据（规则 5 入内）：fixnote/disputed 不许活过结项；pending 清零才可关单。"""
    c = counts(markers)
    blockers = {k: c[k] for k in ("pending", "disputed", "fixnote") if c[k]}
    return (not blockers), {"counts": c, "blockers": blockers}
