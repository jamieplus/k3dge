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
)

#: 不扫的目录：派生面/历史面/退役面（各有其权威源，改它们没意义或有害）
_SKIP_PARTS = frozenset({"archive", "generated", "obsolete"})

_BODY_META_RE = re.compile(r"^-\s+\*\*(Status|Milestone|Priority|Date|Report)\*\*:.*$\n?", re.MULTILINE)


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
    return [c for c in codes if c in FIXABLE_RULES]


def _fix(rel: str, text: str, codes: List[str]) -> Tuple[str, List[str]]:
    """按闭集规则改写文本；返回 (新文本, 实际应用的规则)。规则间无冲突（字节级/删行）。"""
    out = text
    applied: List[str] = []
    if "MD_CRLF" in codes:
        out = out.replace("\r\n", "\n").replace("\r", "\n")
        applied.append("MD_CRLF")
    if "MD_TRAILING_WS" in codes:
        out = re.sub(r"[ \t]+$", "", out, flags=re.MULTILINE)
        applied.append("MD_TRAILING_WS")
    if "TASK_BODY_META_REDUNDANT" in codes:
        out = _BODY_META_RE.sub("", out)
        applied.append("TASK_BODY_META_REDUNDANT")
    if "MD_NO_FINAL_NEWLINE" in codes:
        out = out.rstrip("\n") + "\n"
        applied.append("MD_NO_FINAL_NEWLINE")
    return out, applied


def scan(workspace: Path) -> List[Dict[str, str]]:
    """当前可确定修的偏差清单（`[{"path", "rule"}]`）；空 ⇒ 规约已满足（`docs_normalized` 过）。"""
    out: List[Dict[str, str]] = []
    for p in managed_docs(workspace):
        rel = p.relative_to(workspace).as_posix()
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue          # 编码问题属判断类，不在本集
        for code in _codes(rel, text):
            out.append({"path": rel, "rule": code})
    return out


def apply(workspace: Path, *, dry_run: bool = False) -> Dict[str, object]:
    """按闭集规则修；`dry_run=True` 只报不改。返回报告（幂等：再跑一次应为空）。"""
    fixed: List[Dict[str, str]] = []
    remaining = 0
    for p in managed_docs(workspace):
        rel = p.relative_to(workspace).as_posix()
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        codes = _codes(rel, text)
        if not codes:
            continue
        new, applied = _fix(rel, text, codes)
        if new == text or not applied:
            remaining += len(codes)      # 检测到但无可改（理论不可达，保守计）
            continue
        if not dry_run:
            try:
                with open(p, "w", encoding="utf-8", newline="") as fh:
                    fh.write(new)
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
