"""12 列审计报告的**查找/归类/计数**（report finding；表格解析在 `report_table`）。

Extracted from `engine/milestone.py` (A-1 第四块).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional, Tuple

from k3dge.engine import report_table
from k3dge.engine.milestone_files import (
    _filename_milestone,
    _has_milestone_token,
    _is_review_aux,
)

_AUDIT_HEADER = report_table.TABLE_HEADER
_QUALITY_MARKER_RE = re.compile(r"k3dge:kind:\s*quality", re.IGNORECASE)


#: 外部扫描件的类名（`-scan.md` 后缀或正文标记），与"里程碑审计报告"分开认。
_SCAN_MARKER_RE = re.compile(r"k3dge:kind:\s*scan", re.IGNORECASE)


def _report_kind(name: str, text: str) -> str:
    """分类 12 列报告：`quality`（legacy 标记/文件名）、`scan`（外部全文件扫描）、否则 `audit`。

    文件名的判据一律**收到后缀**：`-quality`/`-scan` 作全文子串会把普通审计报告
    （如 `2026-09-29-M11-quality-audit.md`）错分进别的桶 ⇒ 审计面找不到报告（假阴，403）。

    `scan` 这一类是必需的：`_find_report(..., kind="audit")` 以前只看"文件名带 M11 + 有 12 列表 +
    取最新 mtime"，于是一份**外部扫描**会冒充本轮 k3dit 审计报告被 6 个消费者读走——包括
    `seal_flow._report_seat`（封版提交 trailer 的 `Audit-seat` 会写成扫描器名）与
    `audit_closed`/`audit_checklist`（把扫描计数当"本轮审计闭环"）。外部扫描 ≠ 里程碑审计
    （ADR-0004 §2.1.10、ADR-0006 sidecar）。
    """
    low = name.lower()
    if _QUALITY_MARKER_RE.search(text) or low.endswith("-quality.md"):
        return "quality"
    if _SCAN_MARKER_RE.search(text) or low.endswith("-scan.md"):
        return "scan"
    return "audit"


def _find_report(workspace: Path, milestone_id: str,
                 kind: str = "audit") -> Optional[Tuple[Path, str]]:
    """Return `(path, text)` of the most recent 12-col report of `kind`; **None** when none.

    调用方一律靠 `is None` / `[1]` 解包判闸门（`audit_trigger.audit_closed`、
    `seal_flow._report_seat`、`milestone_audit`），故契约必须写出来（404）。
    """
    reviews = workspace / "docs" / "reviews"
    if not reviews.is_dir():
        return None
    candidates = []
    for f in reviews.iterdir():
        if not (f.is_file() and f.suffix == ".md" and not _is_review_aux(f.name)):
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            # 整份吞掉会让结论变成"没有审计报告"，而真因是"有一份读不出"——方向性误导（405）
            print(f"[audit_report] WARN: 候选报告读不出 {f.name}（{type(exc).__name__}: {exc}）"
                  "⇒ 已跳过该件", file=sys.stderr)
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
        try:
            mtime = f.stat().st_mtime          # iterdir 是快照：seal 归档可能在这中间把文件移走（407）
        except OSError as exc:
            print(f"[audit_report] WARN: {f.name} 扫描期间不可 stat（{exc}）⇒ 跳过该件",
                  file=sys.stderr)
            continue
        candidates.append((mtime, f, text))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1], candidates[0][2]


def _find_audit_report(workspace: Path, milestone_id: str):
    """Most recent audit (k3dit) report. Back-compat wrapper for kind='audit'."""
    return _find_report(workspace, milestone_id, "audit")


def _parse_audit_stats(text: str) -> dict:
    """Count 待修 / 有意留 / 已修 rows in a 12-col audit table.

    单一解析器：委托 `report_table.count_statuses`（value-2），封板闸与 `k3dge check` 同口径。
    """
    return report_table.count_statuses(text)
