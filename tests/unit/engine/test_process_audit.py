"""过程审计面（process_audit）：报告署名/来源/锚点字段的**解析**。

闸位说明（ADR-0004 §2.1.3/§2.1.10 🅰1）：报告是**可选产物**——存在则须合格（`_SIGN_KEYS`
非空），不存在不卡流程。故本文件只测 `_field`/`_SIGN_KEYS` 这层；"缺报告 / 未入库 ⇒ 拒"的
旧判据（`evidence_chain_error`）已随报告降级一并删除，不再有对应测试。
"""
from __future__ import annotations

from pathlib import Path

from k3dge.engine import process_audit

_HEADER = "ID|日期|严重度|优先级|类型|问题描述|位置|状态|处置|验证|复审|验收"


def _report(ws: Path, *, sign: bool, name: str = "2026-09-13-M9-audit.md") -> Path:
    reviews = ws / "docs" / "reviews"
    reviews.mkdir(parents=True, exist_ok=True)
    lines = ["# Audit M9", f"| {_HEADER} |", "| --- |"]
    if sign:
        lines += ["- **审计人**: k3dit", "- **透镜来源**: k3dit 工单",
                  "- **基线**: " + "0" * 40]   # 本层只验"可解析"，不需真 sha
    p = reviews / name
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_sign_keys_are_the_three_anchors() -> None:
    assert process_audit._SIGN_KEYS == ("审计人", "透镜来源", "基线")


def test_field_parses_bold_key_value() -> None:
    text = "- **审计人**: k3dit\n- **基线**: `abc1234`（说明）\n"
    assert process_audit._field(text, "审计人") == "k3dit"
    assert process_audit._field(text, "基线") == "`abc1234`（说明）"   # 调用方自己剥壳
    assert process_audit._field(text, "透镜来源") == ""


def test_field_accepts_fullwidth_colon() -> None:
    assert process_audit._field("- **审计人**：k3dit\n", "审计人") == "k3dit"


def test_signed_report_yields_all_three_keys(tmp_path: Path) -> None:
    text = _report(tmp_path, sign=True).read_text(encoding="utf-8")
    assert [k for k in process_audit._SIGN_KEYS if not process_audit._field(text, k)] == []


def test_unsigned_report_lists_missing_keys(tmp_path: Path) -> None:
    text = _report(tmp_path, sign=False).read_text(encoding="utf-8")
    missing = [k for k in process_audit._SIGN_KEYS if not process_audit._field(text, k)]
    assert missing == ["审计人", "透镜来源", "基线"]
