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
    # 只剥**一对**首尾 `|`（分隔符），不把首/尾的空单元一起吃掉（紧凑行尾部空列会被误删/错位，ocr-105）。
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _is_separator(cells: List[str]) -> bool:
    return bool(cells) and "".join(cells).strip() != "" and set("".join(cells)) <= set("-: ")


def has_table(text: str) -> bool:
    """是否含 12 列表头——判据与 `find_table`/`_cells` **同源**。

    旧实现自己 `replace("|","").replace(" ","")`：只剥半角空格，制表符/全角空格/U+00A0
    填充时判 False，而 `find_table`（走 `strip()`）认得出 ⇒ 同一个"这张表是不是审计报告"
    两处互相矛盾（ocr-303）。
    """
    _idx, header = find_table(text)
    if header is None:
        return False
    want = [c.strip() for c in TABLE_HEADER.split("|")]
    return len(header) == len(want) and header == want


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
        # 空行跳过不截断：表内偶然空行/注释后仍有数据行时，"遇非 `|` 即停"会把后面的
        # `待修` 行整段丢掉（ocr2-073）。非空非 `|`（正文/注解）才是表结束。
        if not s:
            continue
        if not s.startswith("|"):
            break
        cells = _cells(s)
        if _is_separator(cells):
            continue
        if len(cells) != len(header):
            continue
        rows.append((i, dict(zip(header, cells))))
    return header, rows


def malformed_rows(text: str) -> list:
    """被 `parse_rows` 因列数不符**跳过**的数据样行 `[(line_idx, cells)]`（t-252）。

    "跳过畸形"是解析器的口径，但闭环判定不许因此把这些行当不存在：一行 `待修`
    写漏几列 ⇒ `待修==0` 假成立——与 ocr-009 同族，方向是 fail-open。
    """
    lines = (text or "").splitlines()
    hidx, header = find_table(text)
    if hidx < 0 or header is None:
        return []
    out: list = []
    for i in range(hidx + 1, len(lines)):
        s = lines[i].strip()
        # 与 `parse_rows` 同口径：空行跳过不截断（ocr2-073），否则畸形行在空行之后就隐身。
        if not s:
            continue
        if not s.startswith("|"):
            break
        cells = _cells(s)
        if _is_separator(cells):
            continue
        if len(cells) != len(header):
            out.append((i, cells))
    return out


def count_statuses(text: str) -> Dict[str, object]:
    """状态列计数（含 `_ids_<状态>`）。封板闸与 `_count_status` 共用此唯一口径。

    **total＝列数合格的数据行**（列数角色非 12 的畸形行不计，而是进 `malformed`/`_ids_畸形` 供 `audit_closed` 拒闭环）；未知/非法状态进 `_ids_未知状态`；
    开放态别名（`待验证`/`待裁`）并入 `待修` ⇒ fail-closed：有未关行就不可能 `待修==0`（ocr-009）。
    列数不符被跳过的行进 `malformed`/`_ids_畸形`（t-252）——`audit_closed` 据此拒闭环。
    """
    counts: Dict[str, object] = {s: 0 for s in STATUSES}
    counts["total"] = 0
    # 命中的是否真是 12 列审计表（顺序敏感）：`find_table` 宽松、只认 ID+状态，
    # 前面的辅助表可能被当审计表整段解析（ocr2-304 / ocr-106 有意留的暴露面）。
    # 消费方可据此区分"这张表的数字可信"与"只是碰巧有这两列"。
    _hidx, _header = find_table(text)
    counts["contract_ok"] = (_header == [c.strip() for c in TABLE_HEADER.split("|")])
    # `_ids_*` 键**无论命中与否都存在**：调用方按 `counts["_ids_待修"]` 取值时，
    # "这一态没出现过"与"键不存在"是两种形状，前者安全后者让新代码 KeyError（456）
    for s in list(STATUSES) + list(_OPEN_ALIASES) + ["待修", "未知状态", "畸形"]:
        counts.setdefault(f"_ids_{s}", [])
    _, rows = parse_rows(text)
    malf = malformed_rows(text)
    counts["malformed"] = len(malf)
    counts["_ids_畸形"] = [str(cells[0]).strip() or f"line{idx + 1}" for idx, cells in malf]
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
