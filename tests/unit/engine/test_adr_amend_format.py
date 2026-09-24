"""ADR amend/footnote 形态闸（2026-09-24）：k3dit 0001/0007 漂移的判据。"""
from __future__ import annotations

from pathlib import Path

from k3dge.engine.adr_gate import amend_format

GOOD = """---
Status: Accepted
Amended-by:
  - 🅰1 | Core Maintainer | 2026-09-20 | 第一处
  - 🅰2 | Core Maintainer | 2026-09-22 | 第二处
Landed-by: src/x.py
Date: 2026-08-25
---

# ADR-0001: t

## 1. 上下文 (Context)

正文[^🅰1.1]

## 2. 决策 (Decision)

又一处[^🅰2.1]

## 3. 产生后果 (Consequences)

[^🅰1.1]: 修改：甲
[^🅰2.1]: 修改：乙
"""


def _ws(tmp_path: Path, body: str) -> Path:
    """最小 ADR 仓：**带 .schema.json 且声明 amend**（判据数据驱动，与 `k3dge check` 同一份 schema）。"""
    import json as _json

    d = tmp_path / "docs" / "adr"
    d.mkdir(parents=True)
    (d / ".schema.json").write_text(
        _json.dumps({"filename": r"^(\d{4})-[\w-]+\.md$", "amend": {"enabled": True},
                     "codes": {"amend": "ADR_AMEND_FORMAT"}}, ensure_ascii=False), encoding="utf-8")
    (d / "0001-t.md").write_text(body, encoding="utf-8")
    return tmp_path


def test_good_adr_passes(tmp_path):
    assert amend_format(_ws(tmp_path, GOOD)) is None


def test_missing_superscript_prefix_is_flagged(tmp_path):
    bad = GOOD.replace("  - 🅰2 |", "  - 2 |")
    assert "🅰N |" in (amend_format(_ws(tmp_path, bad)) or "")


def test_non_append_order_is_flagged(tmp_path):
    """顺序＝append 序（升序）：倒序/乱序都红（2026-09-24 用户定的口径）。"""
    bad = GOOD.replace("  - 🅰1 | Core Maintainer | 2026-09-20 | 第一处\n  - 🅰2 | Core Maintainer | 2026-09-22 | 第二处",
                       "  - 🅰2 | Core Maintainer | 2026-09-22 | 第二处\n  - 🅰1 | Core Maintainer | 2026-09-20 | 第一处")
    assert "非升序" in (amend_format(_ws(tmp_path, bad)) or "")


def test_defined_but_unreferenced_footnote_flagged(tmp_path):
    bad = GOOD.replace("正文[^🅰1.1]", "正文")
    assert "没被引用" in (amend_format(_ws(tmp_path, bad)) or "")


def test_footnotes_must_be_in_tail(tmp_path):
    bad = GOOD.replace("## 2. 决策 (Decision)\n\n又一处[^🅰2.1]\n",
                       "## 2. 决策 (Decision)\n\n又一处[^🅰2.1]\n\n[^🅰9.9]: 修改：穿插\n")
    bad = bad.replace("[^🅰2.1]: 修改：乙", "[^🅰2.1]: 修改：乙")   # 保持定义存在
    out = amend_format(_ws(tmp_path, bad)) or ""
    assert "文末" in out or "没有定义" in out


def test_schema_block_gates_the_check():
    """数据驱动：ADR schema 声明 `amend` 才查（其它文档类型不受影响）；`k3dge check` 与 seal 同源。"""
    from k3dge.engine.pure_schema import check_amend

    bad = "Amended-by:\n  - 1 | X | 2026-01-01 | a\n"
    assert check_amend(None, {}, "0001-a.md", bad) == []                    # 未声明 ⇒ 不查
    got = check_amend({"enabled": True}, {"amend_order": "ADR_AMEND_ORDER"}, "0001-a.md", bad)
    assert got and got[0][0] == "ADR_AMEND_ORDER" and "前缀" in got[0][1]
    # 码可被 schema 覆盖（数据驱动）
    got2 = check_amend({"enabled": True}, {"amend_order": "X_CUSTOM"}, "0001-a.md", bad)
    assert got2 and got2[0][0] == "X_CUSTOM"
