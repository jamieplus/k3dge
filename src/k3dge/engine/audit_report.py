"""12 列审计报告的**查找/归类/计数**（report finding；表格解析在 `report_table`）。

Extracted from `engine/milestone.py` (A-1 第四块).
"""
from __future__ import annotations

import re
from pathlib import Path

from k3dge.engine import report_table
from k3dge.engine.milestone_files import (
    _filename_milestone,
    _has_milestone_token,
    _is_review_aux,
)

_AUDIT_HEADER = report_table.TABLE_HEADER
_QUALITY_MARKER_RE = re.compile(r"k3dge:kind:\s*quality", re.IGNORECASE)


def _report_kind(name: str, text: str) -> str:
    """Classify a 12-col report as 'quality' (legacy kind marker / filename) or 'audit'."""
    if _QUALITY_MARKER_RE.search(text) or "-quality" in name.lower():
        return "quality"
    return "audit"


def _find_report(workspace: Path, milestone_id: str, kind: str = "audit"):
    """Return (path, text) of the most recent 12-col report of the given kind."""
    reviews = workspace / "docs" / "reviews"
    if not reviews.is_dir():
        return None
    candidates = []
    for f in reviews.iterdir():
        if not (f.is_file() and f.suffix == ".md" and not _is_review_aux(f.name)):
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        # 必须含**真表格**（`|` 起头的 12 列表头行），不能只是正文里抄了表头串——
        # 否则说明稿会被当成本里程碑审计报告、count_statuses 解析 0 行 ⇒ 假闭环（ocr-051）。
        from k3dge.engine import report_table

        if report_table.find_table(text, required=("ID", "状态"))[0] < 0:
            continue
        if _report_kind(f.name, text) != kind:
            continue
        if milestone_id:
            fn_ms = _filename_milestone(f.name)
            if fn_ms:
                if fn_ms.lower() != milestone_id.lower():   # 正则 IGNORECASE ⇒ 比较也得大小写不敏感（ocr-267）
                    continue
            elif not _has_milestone_token(text, milestone_id):
                # 报告既无里程碑文件名、正文也无该里程碑 token（如跨里程碑的通用稿）：
                # 不得充当任一里程碑的审计闭环（否则 seal_ready 假阳）。
                continue
        candidates.append((f.stat().st_mtime, f, text))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1], candidates[0][2]


def _find_audit_report(workspace: Path, milestone_id: str):
    """Most recent audit (k3dit) report. Back-compat wrapper for kind='audit'."""
    return _find_report(workspace, milestone_id, "audit")


def _parse_audit_stats(text: str) -> dict:
    """Count 待修 / 有意留 / 已修 rows in a 12-col audit table.

    单一解析器：委托 `report_table.count_statuses`（value-2），与 `_count_status`、
    封板闸同口径。
    """
    return report_table.count_statuses(text)
