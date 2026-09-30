"""value-2：12 列报告单一解析器。"""
from k3dge.engine import report_table as rt

_TBL = """# 报告
| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A-1 | 2026-01-01 | 中 | P2 | 缺陷 | d1 | f.py:1 | 待修 | 转 tasks |  |  |  |
| A-2 | 2026-01-01 | 低 | P3 | 规范 | d2 | f.py:2 | 已修 | 已修 | v | 通过 |  |
| A-3 | 2026-01-01 | 低 | P3 | 规范 | 截断行 | f.py:3 | 有意留
| A-4 | 2026-01-01 | 低 | P3 | 规范 | d4 | f.py:4 | 有意留 | 有意留 |  | 通过 |  |
"""


def test_has_table_and_rows_skip_malformed():
    assert rt.has_table(_TBL)
    header, rows = rt.parse_rows(_TBL)
    assert header is not None and len(header) == 12
    # A-3 截断行（列数不符）被跳过
    assert [r.get("ID") for _, r in rows] == ["A-1", "A-2", "A-4"]


def test_count_statuses_single_source():
    c = rt.count_statuses(_TBL)
    assert c["待修"] == 1 and c["已修"] == 1 and c["有意留"] == 1 and c["total"] == 3
    assert c["_ids_待修"] == ["A-1"]


def test_no_table():
    assert not rt.has_table("no table here")
    assert rt.count_statuses("nothing")["total"] == 0


def test_open_aliases_and_unknown_fail_closed():
    """`待验证`/`待裁` 计入 `待修`；未知状态计 total 并单列（ocr-009）。"""
    tbl = (
        "| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
        "| A-5 | 2026-01-01 | 低 | P3 | 规范 | d5 | f.py:5 | 待验证 |  |  |  |  |\n"
        "| A-6 | 2026-01-01 | 低 | P3 | 规范 | d6 | f.py:6 | 待裁 |  |  |  |  |\n"
        "| A-7 | 2026-01-01 | 低 | P3 | 规范 | d7 | f.py:7 | 怪状态 |  |  |  |  |\n"
        "| A-8 | 2026-01-01 | 低 | P3 | 规范 | d8 | f.py:8 | 已修 | 已修 | v | 通过 |  |\n"
    )
    c = rt.count_statuses(tbl)
    assert c["待修"] == 2 and c["total"] == 4 and c["已修"] == 1
    assert c["_ids_未知状态"] == ["A-7"]
    assert set(c["_ids_待修"]) == {"A-5", "A-6"}


def test_has_table_shares_find_table_normalization() -> None:
    """制表符/全角空格/NBSP 填充的 12 列表头：`find_table` 认得出，`has_table` 也必须认（ocr-303）。"""
    cells = [c.strip() for c in rt.TABLE_HEADER.split("|")]
    for fill in ("\t", "\u3000", "\u00a0"):
        text = "# r\n\n|" + "|".join(f"{fill}{c}{fill}" for c in cells) + "|\n| --- |\n"
        assert rt.find_table(text)[0] >= 0, fill
        assert rt.has_table(text), fill
    shuffled = "| " + " | ".join(reversed(cells)) + " |"
    assert not rt.has_table("# r\n" + shuffled), "列序仍须严格（12 列契约）"
    assert rt.has_table(_TBL)

def test_external_scan_report_is_not_the_audit_report() -> None:
    """外部全文件扫描（`-scan.md`）不得被当成本轮 k3dit 审计报告消费。

    以前 `_find_report(kind="audit")` 只按"M11 + 12 列 + 最新 mtime"认，扫描件一旦比真审新，
    `seal_flow._report_seat` 会把封版提交的 `Audit-seat` 写成扫描器名，`audit_closed` 也会拿
    扫描计数当闭环证据（ADR-0004 §2.1.10 / ADR-0006）。
    """
    import tempfile
    from pathlib import Path as _P

    from k3dge.engine.audit_report import _find_report, _report_kind

    assert _report_kind("2026-09-30-M11-ocr-tests-scan.md", "") == "scan"
    assert _report_kind("2026-09-29-M11-quality-audit.md", "") == "audit"
    assert _report_kind("2026-09-29-M11-k3dit-bundle-audit.md", "") == "audit"

    ws = _P(tempfile.mkdtemp())
    (ws / "docs" / "reviews").mkdir(parents=True)
    tbl = _TBL
    (ws / "docs" / "reviews" / "2026-09-29-M11-k3dit-bundle-audit.md").write_text(
        "# 审计\n- **审计人**: k3dit\n- **透镜来源**: k3dit\n- **基线**: " + "0" * 40 + "\n" + tbl,
        encoding="utf-8")
    newer = ws / "docs" / "reviews" / "2026-09-30-M11-ocr-scan.md"
    newer.write_text("# 扫描\n- **审计人**: open-code-review\n" + tbl, encoding="utf-8")
    import os, time
    os.utime(newer, (time.time() + 60, time.time() + 60))          # 让扫描件"更新"
    found = _find_report(ws, "M11", "audit")
    assert found is not None and found[0].name.endswith("k3dit-bundle-audit.md"), found[0].name
    assert _find_report(ws, "M11", "scan")[0].name.endswith("-ocr-scan.md")
