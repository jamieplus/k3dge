"""12 列审计报告的**单一表格解析器**（table-only，无判断）。

收敛 `_parse_audit_stats` / `_find_report` / `_auto_backfill_reviews` /
`audit_flow._count_status` / `audit_flow.collect_audit` 里各自复写的
「扫表头→定位列→计数/翻状态」逻辑（value-2）；口径分歧（如 code-13 抓到的两计数）
由此消根。所有消费方只调用本模块。
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

#: 12 列契约的表头（唯一来源；消费方不再各自硬编码）。
TABLE_HEADER = "ID|日期|严重度|优先级|类型|问题描述|位置|状态|处置|验证|复审|验收"

#: 状态列取值（枚举）。
STATUSES = ("待修", "有意留", "已修")
#: **开放态别名**：`待验证`(`fixnote`) / `待裁`(`disputed`) 同为未关（契约 §8 / `audit_verify.ROW_STATE_ZH`）。
#: 它们计入 `待修` 的开放口径——否则报告里明明有未闭环行，闸仍显示"待修=0"而放行（ocr-009）。
_OPEN_ALIASES = ("待验证", "待裁")


def _cells(line: str) -> List[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _is_separator(cells: List[str]) -> bool:
    return bool(cells) and "".join(cells).strip() != "" and set("".join(cells)) <= set("-: ")


def has_table(text: str) -> bool:
    """是否含 12 列表头（忽略空白差异）。"""
    return TABLE_HEADER.replace("|", "") in (text or "").replace("|", "").replace(" ", "")


def find_table(text: str, required: Tuple[str, ...] = ("ID", "状态")):
    """定位表头行：返回 (header_line_idx, header_cols)；无 ⇒ (-1, None)。"""
    for i, raw in enumerate((text or "").splitlines()):
        s = raw.strip()
        if not s.startswith("|"):
            continue
        cells = _cells(s)
        if _is_separator(cells):
            continue
        if all(h in cells for h in required):
            return i, cells
    return -1, None


def parse_rows(
    text: str, required: Tuple[str, ...] = ("ID", "状态")
) -> Tuple[Optional[List[str]], List[Tuple[int, Dict[str, str]]]]:
    """解析数据行：返回 (header, [(line_idx, {列: 值})])。

    只收 `len(cols) == len(header)` 的行（截断/畸形行跳过，与口径分歧的根因一致），
    遇表结束（非 `|` 行）即停。
    """
    lines = (text or "").splitlines()
    hidx, header = find_table(text, required)
    if hidx < 0 or header is None:
        return None, []
    rows: List[Tuple[int, Dict[str, str]]] = []
    for i in range(hidx + 1, len(lines)):
        s = lines[i].strip()
        if not s.startswith("|"):
            break
        cells = _cells(s)
        if _is_separator(cells):
            continue
        if len(cells) != len(header):
            continue
        rows.append((i, dict(zip(header, cells))))
    return header, rows


def count_statuses(text: str) -> Dict[str, object]:
    """状态列计数（含 `_ids_<状态>`）。封板闸与 `_count_status` 共用此唯一口径。

    **total＝表内所有数据行**（不因状态未知而漏计）；未知/非法状态进 `_ids_未知状态`；
    开放态别名（`待验证`/`待裁`）并入 `待修` ⇒ fail-closed：有未关行就不可能 `待修==0`（ocr-009）。
    """
    counts: Dict[str, object] = {s: 0 for s in STATUSES}
    counts["total"] = 0
    counts["_ids_未知状态"] = []
    _, rows = parse_rows(text)
    for _, row in rows:
        st = str(row.get("状态", "")).strip()
        rid = row.get("ID", "")
        counts["total"] = int(counts["total"]) + 1
        if st == "待修" or st in _OPEN_ALIASES:
            counts["待修"] = int(counts["待修"]) + 1
            counts.setdefault("_ids_" + st, []).append(rid)
            if st != "待修":
                counts.setdefault("_ids_待修", []).append(rid)   # 未关项下游派单口径一致
        elif st in STATUSES:
            counts[st] = int(counts[st]) + 1
            counts.setdefault("_ids_" + st, []).append(rid)
        else:
            counts["_ids_未知状态"].append(rid)
    return counts
