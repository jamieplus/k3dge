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


def test_wrapped_footnote_and_gapped_minor_are_fixed():
    """换行截断脚注；小标号必须从 1 连续，不能用条款号。"""
    from k3dge.engine.doc_fix import _fix
    from k3dge.engine.pure_schema import check_amend

    bad = GOOD.replace(
        "又一处[^🅰2.1]\n",
        "先[^🅰2.4]后[^🅰2.1]\n",
    ).replace(
        "[^🅰2.1]: 修改：乙",
        "[^🅰2.4]: 修改：乙的第一处\n续行掉进正文\n[^🅰2.1]: 修改：乙的第二处",
    )
    codes = {c for c, _, _ in check_amend({"enabled": True}, {}, "0001-t.md", bad)}
    assert "ADR_FOOTNOTE_LINE" in codes
    assert "ADR_FOOTNOTE_SEQ" in codes
    fixed, applied = _fix("docs/adr/0001-t.md", bad, ["ADR_FOOTNOTE_LINE", "ADR_FOOTNOTE_SEQ"])
    assert applied == ["ADR_FOOTNOTE_LINE", "ADR_FOOTNOTE_SEQ"]
    assert "续行掉进正文" in fixed.splitlines()[-2] or any(
        ln.startswith("[^🅰2.1]:") and "续行掉进正文" in ln for ln in fixed.splitlines())
    again = {c for c, _, _ in check_amend({"enabled": True}, {}, "0001-t.md", fixed)}
    assert "ADR_FOOTNOTE_LINE" not in again
    assert "ADR_FOOTNOTE_SEQ" not in again
    # 出现序：原 2.4 在前 ⇒ 变成 2.1，原 2.1 变成 2.2
    assert "[^🅰2.1]" in fixed.split("## 2")[1].split("## 3")[0]
    assert fixed.count("[^🅰2.4]") == 0


def _accepted(rows: str, marks: str) -> str:
    defs = "\n".join(f"[^{m}]: 修改：一处" for m in marks.split())
    refs = " ".join(f"[^{m}]" for m in marks.split())
    return (
        "---\nStatus: Accepted\nAmended-by:\n" + rows + "\nDate: 2026-09-26\n---\n\n"
        "# ADR-0001: t\n\n## 1. 上下文 (Context)\n\n" + refs + "\n\n"
        "## 2. 决策 (Decision)\n\n## 3. 产生后果 (Consequences)\n\n" + defs + "\n"
    )


def test_same_section_split_across_amends_is_blocked():
    """一个节写成多条修订：同一天两条，或先后三条，都是拆主题。"""
    from k3dge.engine.pure_schema import check_amend

    three = _accepted(
        "  - 🅰1 | Core Maintainer | 2026-09-26 | §2.9.6 增形状\n"
        "  - 🅰2 | Core Maintainer | 2026-09-26 | §2.9.6 补落地\n"
        "  - 🅰3 | Core Maintainer | 2026-09-27 | §2.9.6 补验收\n",
        "🅰1.1 🅰2.1 🅰3.1",
    )
    assert any(c == "ADR_AMEND_SPLIT" and "§2.9.6" in msg
               for c, msg, _ in check_amend({"enabled": True}, {}, "0001-t.md", three))
    same_day = _accepted(
        "  - 🅰1 | Core Maintainer | 2026-09-26 | §2.5 补哈希\n"
        "  - 🅰2 | Core Maintainer | 2026-09-26 | §2.5 补空补丁\n",
        "🅰1.1 🅰2.1",
    )
    assert any(c == "ADR_AMEND_SPLIT" for c, _, _ in check_amend({"enabled": True}, {}, "0001-t.md", same_day))


def test_later_invariant_on_the_same_section_is_not_a_split():
    """隔天、且只有两条：后一次可以是另一个不变量，不并进前一个号。"""
    from k3dge.engine.pure_schema import check_amend

    later = _accepted(
        "  - 🅰1 | Core Maintainer | 2026-09-14 | §2.3 作用域\n"
        "  - 🅰2 | Core Maintainer | 2026-09-26 | §2.3 传输链\n",
        "🅰1.1 🅰2.1",
    )
    assert not any(c == "ADR_AMEND_SPLIT" for c, _, _ in check_amend({"enabled": True}, {}, "0001-t.md", later))


def test_proposed_adr_must_not_carry_amend_trail():
    from k3dge.engine.pure_schema import check_amend

    bad = GOOD.replace("Status: Accepted", "Status: Proposed")
    got = check_amend({"enabled": True}, {}, "0001-t.md", bad)
    assert any(c == "ADR_AMEND_DRAFT" for c, _, _ in got)
    clean = GOOD.replace("Status: Accepted", "Status: Proposed").replace(
        "Amended-by:\n  - 🅰1 | Core Maintainer | 2026-09-20 | 第一处\n  - 🅰2 | Core Maintainer | 2026-09-22 | 第二处\n",
        "Amended-by: -\n",
    )
    # 去掉修订标记，Proposed 才过
    import re
    clean = re.sub(r"\[\^🅰\d+\.\d+\]", "", clean)
    clean = re.sub(r"(?m)^\[\^🅰\d+\.\d+\]:.*\n", "", clean)
    assert check_amend({"enabled": True}, {}, "0001-t.md", clean) == []


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
