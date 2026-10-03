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
    # 一格一断（t-253）：合取断言红时只报整个表达式，CI 里定位不了一条计数回归
    assert c["待修"] == 1, c
    assert c["已修"] == 1, c
    assert c["有意留"] == 1, c
    assert c["total"] == 3, c
    assert c["_ids_待修"] == ["A-1"]
    # 畸形行不再是"当它不存在"（t-252）：A-3 列数不符被解析跳过，但必须有信号可查
    assert c["malformed"] == 1, c
    assert c["_ids_畸形"] == ["A-3"], c


def test_zero_hit_ids_keys_exist() -> None:
    """456 不变量的**零命中面**（t-251）：每个 `_ids_*` 键无命中也必须在——
    调用方（task_write/milestone_audit）直接按键取值。旧文件所有 `_ids_` 断言
    都指向真有命中的桶，"只有命中才建键"的简化会全绿通过、在调用点炸 KeyError。
    """
    tbl = ("| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |\n"
          "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
          "| Z-1 | 2026-01-01 | 中 | P2 | 缺陷 | d | f.py:1 | 待修 |  |  |  |  |\n")
    c = rt.count_statuses(tbl)
    for key in ("_ids_待修", "_ids_已修", "_ids_有意留", "_ids_待验证", "_ids_待裁",
                "_ids_未知状态", "_ids_畸形"):
        assert key in c, key
    assert c["_ids_已修"] == [] and c["_ids_有意留"] == [] and c["_ids_未知状态"] == []
    assert c["_ids_待修"] == ["Z-1"]


def test_audit_closed_refuses_truncated_pending_row(tmp_path) -> None:
    """fail-open 的端到端面（t-252）：唯一一行 `待修` 被截成 9 列 ⇒ 解析 0 行、
    `待修==0` 假成立——旧 `audit_closed` 会宣布闭环。现在畸形信号挡住它。
    """
    from k3dge.engine.audit_trigger import audit_closed

    (tmp_path / ".agent").mkdir()
    (tmp_path / ".agent" / "manifest.json").write_text("{}", encoding="utf-8")
    revs = tmp_path / "docs" / "reviews"
    revs.mkdir(parents=True)
    truncated = (
        "| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
        "| B-1 | 2026-01-01 | 高 | P1 | 缺陷 | 写漏几列 | f.py:1 | 待修\n"
    )
    (revs / "2026-09-01-M7-audit.md").write_text(truncated, encoding="utf-8")
    # ocr2-778：`False` 也可能是"根本没找到报告/没认成审计表"——先钉夹具
    # 真带畸形信号，`False` 才只能来自 malformed 守卫，而非 discovery 空转。
    c = rt.count_statuses(truncated)
    assert c["malformed"] == 1, c
    assert c["_ids_畸形"] == ["B-1"], c
    assert c["total"] == 0, c
    assert audit_closed(tmp_path, "M7") is False, "截断的待修行被当成了闭环"


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
    assert c["待修"] == 2, c
    assert c["total"] == 4, c
    assert c["已修"] == 1, c
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

def test_count_statuses_exposes_contract_check() -> None:
    """命中的表是否真 12 列审计表要暴露给消费方（ocr2-304）；辅助表在前时不得冒充。"""
    aux = "| ID | 状态 |\n| --- | --- |\n| X-1 | 待修 |\n\n" + _TBL
    assert rt.count_statuses(aux)["contract_ok"] is False
    assert rt.count_statuses(_TBL)["contract_ok"] is True
    assert rt.count_statuses("nothing")["contract_ok"] is False


def test_external_scan_report_is_not_the_audit_report(tmp_path) -> None:
    """外部全文件扫描（`-scan.md`）不得被当成本轮 k3dit 审计报告消费。

    以前 `_find_report(kind="audit")` 只按"M11 + 12 列 + 最新 mtime"认，扫描件一旦比真审新，
    `seal_flow._report_seat` 会把封版提交的 `Audit-seat` 写成扫描器名，`audit_closed` 也会拿
    扫描计数当闭环证据（ADR-0004 §2.1.10 / ADR-0006）。
    """
    from k3dge.engine.audit_report import _find_report, _report_kind

    assert _report_kind("2026-09-30-M11-ocr-tests-scan.md", "") == "scan"
    assert _report_kind("2026-09-29-M11-quality-audit.md", "") == "audit"
    assert _report_kind("2026-09-29-M11-k3dit-bundle-audit.md", "") == "audit"

    # ocr2-779：用 pytest 的 tmp_path（按测回收），不手搓 mkdtemp + atexit
    # （解释器退出才清；崩溃/xdist worker 挂时永久残留 /tmp）。
    ws = tmp_path
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
    # ocr2-780：`None` 与"名不对"分开断——合写时 found 为 None 会死在
    # TypeError（'NoneType' 不可下标），CI 输出丢了"哪个报告没找到"的真因。
    assert found is not None, "audit 报告没找到（discovery/kind 分类回归？）"
    assert found[0].name.endswith("k3dit-bundle-audit.md"), found[0].name
    scan_found = _find_report(ws, "M11", "scan")
    assert scan_found is not None, "scan 桶空（-scan.md 分类/过滤回归？）"
    assert scan_found[0].name.endswith("-ocr-scan.md"), scan_found[0].name