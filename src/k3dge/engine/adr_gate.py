"""封版 ADR 硬闸（ADR-0001 §2 第 8 条「硬闸契约」的一族）：

- `adrs_all_accepted`：范围内 ADR 不得停留在 `Draft`/`Proposed`（封版要求决策已定稿）。
- `adr_landed`：`Accepted` 的 ADR 必带**可解析的落地指针** `Landed-by: <路径> [§节]`，
  使 ADR 成为"已实现现实"的事实源。

只读**结构事实**（`Status:`/`Landed-by:` 与指针解析），不判决策内容对错（归 k3dit）。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

_FM_STATUS = re.compile(r"^Status:\s*(\S+)", re.M)
_FM_LANDED = re.compile(r"^Landed-by:\s*(.+)$", re.M)
_SKIP = {"README.md", "AUTHORING.md", "_template.md"}
_UNDECIDED = {"Draft", "Proposed"}


def _adr_files(workspace: Path) -> List[Path]:
    d = Path(workspace) / "docs" / "adr"
    if not d.is_dir():
        return []
    return [p for p in sorted(d.glob("*.md")) if p.name not in _SKIP]


def _status(text: str) -> str:
    m = _FM_STATUS.search(text)
    return (m.group(1) if m else "").strip()


def adrs_all_accepted(workspace: Path) -> Optional[str]:
    """未 Accepted 的 ADR 汇总；全 Accepted（或无 ADR）⇒ None。"""
    bad = []
    for p in _adr_files(workspace):
        try:
            st = _status(p.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            st = ""
        if st in _UNDECIDED or not st:
            bad.append(f"{p.name}({st or '无 Status'})")
    if bad:
        return f"[SEAL REJECTED] ADR 未 Accepted（封版要求全部 Accepted）：{bad}"
    return None


def _pointer_resolves(workspace: Path, ptr: str) -> bool:
    first = ptr.strip().split()[0].strip() if ptr.strip() else ""
    if not first:
        return False
    return (Path(workspace) / first).exists()


def adr_landed(workspace: Path) -> Optional[str]:
    """Accepted ADR 须带可解析 `Landed-by:`；否则汇总；全满足 ⇒ None。"""
    bad = []
    for p in _adr_files(workspace):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _status(text) != "Accepted":
            continue
        m = _FM_LANDED.search(text)
        if not m:
            bad.append(f"{p.name}(缺 Landed-by)")
            continue
        ptr = m.group(1).strip()
        if not _pointer_resolves(workspace, ptr):
            bad.append(f"{p.name}->{ptr}(指针不可解析)")
    if bad:
        return f"[SEAL REJECTED] Accepted ADR 缺可解析落地指针 `Landed-by:`：{bad}"
    return None
