"""ADR amend/footnote 形态闸（2026-09-24）：k3dit 0001/0007 漂移的判据。"""
from __future__ import annotations

from pathlib import Path

from k3dge.engine.adr_gate import amend_format

GOOD = """---
Status: Accepted
Amended-by:
  - 🅰2 | Core Maintainer | 2026-09-22 | 第二处
  - 🅰1 | Core Maintainer | 2026-09-20 | 第一处
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
    d = tmp_path / "docs" / "adr"
    d.mkdir(parents=True)
    (d / "0001-t.md").write_text(body, encoding="utf-8")
    return tmp_path


def test_good_adr_passes(tmp_path):
    assert amend_format(_ws(tmp_path, GOOD)) is None


def test_missing_superscript_prefix_is_flagged(tmp_path):
    bad = GOOD.replace("  - 🅰2 |", "  - 2 |")
    assert "🅰N |" in (amend_format(_ws(tmp_path, bad)) or "")


def test_non_monotonic_numbers_flagged(tmp_path):
    bad = GOOD.replace("  - 🅰2 | Core Maintainer | 2026-09-22 | 第二处\n  - 🅰1 | Core Maintainer | 2026-09-20 | 第一处",
                       "  - 🅰1 | Core Maintainer | 2026-09-20 | 第一处\n  - 🅰2 | Core Maintainer | 2026-09-22 | 第二处\n  - 🅰1b | x")
    out = amend_format(_ws(tmp_path, bad)) or ""
    assert "前缀" in out or "非单调" in out


def test_defined_but_unreferenced_footnote_flagged(tmp_path):
    bad = GOOD.replace("正文[^🅰1.1]", "正文")
    assert "没被引用" in (amend_format(_ws(tmp_path, bad)) or "")


def test_footnotes_must_be_in_tail(tmp_path):
    bad = GOOD.replace("## 2. 决策 (Decision)\n\n又一处[^🅰2.1]\n",
                       "## 2. 决策 (Decision)\n\n又一处[^🅰2.1]\n\n[^🅰9.9]: 修改：穿插\n")
    bad = bad.replace("[^🅰2.1]: 修改：乙", "[^🅰2.1]: 修改：乙")   # 保持定义存在
    out = amend_format(_ws(tmp_path, bad)) or ""
    assert "文末" in out or "没有定义" in out
