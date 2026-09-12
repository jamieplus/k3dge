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
