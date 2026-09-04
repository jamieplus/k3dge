"""审计标记语法 v1 —— findings 的树侧介质（棘轮循环；契约 §8）。

角色：树上只放**指针＋状态**（一行），正文住在 k3dit 账本；本模块只解析、校验、计数——
**永不改写**任何文件（apply 是编排动作，属 milestone/audit_flow 侧，且永远由补丁驱动）。

kind:     pending | leftover | disputed | fixnote（修席顺手发现，须审席复核）
open :=   pending + disputed + fixnote            # 结项判据 = open 计零
scope:    @line(缺省) | @file(文件头块内) | @repo(只准住 AUDIT.md)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

KINDS = ("pending", "leftover", "disputed", "fixnote")
OPEN_KINDS = frozenset({"pending", "disputed", "fixnote"})
SCOPES = ("line", "file", "repo")
SIDECAR = "AUDIT.md"

# 注释宿主前缀不参与匹配语义（提取只认核心串），但校验头部块归属要用它认注释行。
# 宿主分型：md/html 只认 <!-- -->（反引号里的示例绝不自触发）；代码文件允许行尾注释
#（案发现场就在行尾——指针必须钉得起）。
MARKER_RE = re.compile(
    r"(?:#|//|<!--)[ \t]*k3dit:(?P<kind>pending|leftover|disputed|fixnote)\s+"
    r"(?P<id>[A-Za-z0-9][A-Za-z0-9._#-]*)\s*"
    r"(?:@(?P<scope>line|file|repo))?\s*"
    r"(?P<note>.*?)\s*(?:-->)?\s*$",
    re.M,
)
_COMMENT_LINE_RE = re.compile(r"^\s*(?:#|//|<!--)")
MARKER_RE_MD = re.compile(
    r"<!--[ \t]*k3dit:(?P<kind>pending|leftover|disputed|fixnote)\s+"
    r"(?P<id>[A-Za-z0-9][A-Za-z0-9._#-]*)\s*(?:@(?P<scope>line|file|repo))?(?P<note>[^\n]*?)\s*-->\s*$",
    re.M,
)
_SCAN_SUFFIXES = frozenset(
    {".py", ".md", ".js", ".ts", ".tsx", ".go", ".rs", ".java", ".rb", ".toml", ".yaml", ".yml", ".php", ".kt", ".swift", ".c", ".h", ".cc", ".sh"}
)
_SKIP_DIR_PARTS = ("archive", ".git", ".venv", "node_modules", "__pycache__")
_MAX_NOTE = 80


@dataclass
class Marker:
    file: str
    line: int
    kind: str
    id: str
    scope: str
    note: str

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


def parse_text(rel: str, text: str) -> Tuple[List[Marker], List[str]]:
    lines = text.splitlines()
    hb = head_block_end(lines)
    markers: List[Marker] = []
    problems: List[str] = []
    rx = MARKER_RE_MD if rel.endswith((".md", ".html")) else MARKER_RE
    for m in rx.finditer(text):
        line_no = text.count("\n", 0, m.start()) + 1
        note = m.group("note") or ""
        if len(note) > _MAX_NOTE:
            problems.append(f"{rel}:{line_no} note 超 {_MAX_NOTE} 字符（正文应入账本）")
            note = note[:_MAX_NOTE] + "…"
        markers.append(
            Marker(
                file=rel,
                line=line_no,
                kind=m.group("kind"),
                id=m.group("id"),
                scope=m.group("scope") or "line",
                note=note.strip(),
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
            body = "## " + raw[3:]
            m = re.search(
                r"k3dit:(?P<kind>pending|leftover|disputed|fixnote)\s+(?P<id>[A-Za-z0-9][A-Za-z0-9._#-]*)\s*"
                r"(?:@(?P<scope>line|file|repo))?(?P<note>.*?)\s*$",
                raw[3:],
            )
            if not m:
                continue
            if (m.group("scope") or "line") != "repo":
                problems.append(f"{SIDECAR}:{i} 条目缺 @repo 作用域")
            cur = Marker(SIDECAR, i, m.group("kind"), m.group("id"), "repo", (m.group("note") or "").strip())
            markers.append(cur)
        elif raw.startswith("- files:") and cur is not None:
            cur.note = (cur.note + " | " + raw.split(":", 1)[1].strip()).strip("| ")
    return markers, problems


def extract(workspace: Path, roots: Sequence[str] = ("src", "docs")) -> Tuple[List[Marker], List[str]]:
    markers: List[Marker] = []
    problems: List[str] = []
    for rel, path in _iter_scan_files(workspace, roots):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        ms, ps = parse_text(rel, text)
        markers.extend(ms)
        problems.extend(ps)
    side = workspace / SIDECAR
    if side.is_file():
        try:
            ms, ps = parse_sidecar(side.read_text(encoding="utf-8"))
            markers.extend(ms)
            problems.extend(ps)
        except (UnicodeDecodeError, OSError):  # pragma: no cover
            pass
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
