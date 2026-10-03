"""过程审计面（process_audit）：报告署名/来源/锚点字段的**解析**。

闸位说明（ADR-0004 §2.1.3/§2.1.10 🅰1）：报告是**可选产物**——存在则须合格（`_SIGN_KEYS`
非空），不存在不卡流程。故本文件只测 `_field`/`_SIGN_KEYS` 这层；"缺报告 / 未入库 ⇒ 拒"的
旧判据（`evidence_chain_error`）已随报告降级一并删除，不再有对应测试。
"""

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


def test_field_empty_value_does_not_capture_the_next_line() -> None:
    r"""ocr-097 的 fail-open 形状**必须留在测里**（t-191）：`- **审计人**:` 空值 +
    下一行 `- **基线**: abc…`——旧 `[ \t]*\s*(.+)` 的 `\s` 含 `\n`，跨行捕获下一行 ⇒
    假"值非空"，报告没署名也算签了。现判据（行内空白 + 值同行 + re.M）没测兜住它，
    将来谁改回 `\s*(.+)` 或丢了 re.M，本文件全绿而闸被绕过。
    """
    text = "- **审计人**: \n- **基线**: abc123\n"
    assert process_audit._field(text, "审计人") == ""
    assert process_audit._field(text, "基线") == "abc123"


def test_signed_report_passes_the_single_criterion(tmp_path: Path) -> None:
    """两测走 `sign_missing()`（t-192）：生产唯一判定（milestone_audit 用它），
    `[k for k in _SIGN_KEYS if not _field(...)]` 是**退休的 accept 形状**——
    下面的模板占位测恰好证明它放行未填模板。保留 `_field` 真值位只用来展示分歧。
    """
    text = _report(tmp_path, sign=True).read_text(encoding="utf-8")
    assert process_audit.sign_missing(text) == []


def test_sign_missing_blank_value_does_not_capture_next_anchor(tmp_path: Path) -> None:
    r"""ocr2-506：fail-open 形状必须走**生产唯一判定** `sign_missing()`，而不只在 `_field` 上。
    `_report(sign=False)` 整块不写锚点，跨行捕获不可能发生——把 `sign_missing` 里
    `_field` 换成 `[:：]\s*(.+)`（丢 `re.M`/同行约束）时该夹具照样绿。
    """
    text = ("- **审计人**: \n- **透镜来源**: k3dit 工单\n- **基线**: " + "0" * 40 + "\n")
    assert process_audit.sign_missing(text) == ["审计人"]
    # 半签报告：只有一部分锚点被填，缺的那部分逐项报
    partial = ("- **审计人**: k3dit\n- **透镜来源**: \n- **基线**: " + "0" * 40 + "\n")
    assert process_audit.sign_missing(partial) == ["透镜来源"]


def test_unsigned_report_lists_missing_keys(tmp_path: Path) -> None:
    text = _report(tmp_path, sign=False).read_text(encoding="utf-8")
    assert process_audit.sign_missing(text) == list(process_audit._SIGN_KEYS)


def test_sign_missing_rejects_template_placeholder(tmp_path: Path) -> None:
    """AUTHORING 模板原句（未填）过 `非空` 判据 ⇒ 锚点是空的（ocr-288）。"""
    reviews = tmp_path / "docs" / "reviews"
    reviews.mkdir(parents=True)
    (reviews / "r.md").write_text(
        "- **审计人**: k3dit\n- **透镜来源**: k3dit 工单\n- **基线**: commit/tests 状态快照\n",
        encoding="utf-8")
    text = (reviews / "r.md").read_text(encoding="utf-8")
    # 分歧登记：`_field` 真值判据（退休 accept 形状）放行这条未填模板……
    assert [k for k in process_audit._SIGN_KEYS if not process_audit._field(text, k)] == []
    # ……而唯一判定 `sign_missing()` 拒它。这就是 t-192 把上面两测翻到 sign_missing 的原因。
    assert process_audit.sign_missing(text) == ["基线"]


def test_every_placeholder_mark_is_rejected() -> None:
    """逐个标记测（t-193）：旧测只钉 `状态快照` 一个值，其余标记（含 ocr-288 点名补进来的
    `...`/TODO/N/A）漂移进元组也不会有测红——把 `_SIGN_PLACEHOLDER_MARKS` **本身**当参数源。

    ocr2-507：旧形状拿标记当输入又当预言（`val` 就是标记，`any(m in val)` 按构造恒真），
    删掉某个标记时循环静默少跑一项、`len>=6` 仍真——现在把**期望集合显式钉死**，并对
    **每个 key** 各验一遍（不只是 `基线`）。
    """
    marks = process_audit._SIGN_PLACEHOLDER_MARKS
    assert marks == ("状态快照", "待填", "TBD", "<", "{{", "TODO", "N/A"), \
        "标记集合变了：本测的预言必须同步改（t-193）"
    assert all(isinstance(m, str) and m for m in marks), marks

    def _report_with(key: str, value: str) -> str:
        vals = {"审计人": "k3dit", "透镜来源": "k3dit 工单", "基线": "0" * 40}
        vals[key] = value
        return "".join(f"- **{k}**: {v}\n" for k, v in vals.items())

    for key in process_audit._SIGN_KEYS:
        for mark in marks:
            text = _report_with(key, mark)
            assert key in process_audit.sign_missing(text), f"{key}={mark!r} 被放行＝占位当真实值"
    # 正对照：每个 key 填真值时不得报（证明上面的报缺确实来自占位值）
    for key in process_audit._SIGN_KEYS:
        assert process_audit.sign_missing(_report_with(key, "真实值-" + key)) == [], key


def test_sign_missing_accepts_filled_anchor(tmp_path: Path) -> None:
    import re

    text = _report(tmp_path, sign=True).read_text(encoding="utf-8")
    assert process_audit.sign_missing(text) == []
    # ocr2-766: 上面与 test_signed_report_passes_the_single_criterion 同形——
    # 只断 [] 时"填充锚点是真锚"从没被钉。调用方剥壳后基线须是真 sha 形。
    raw = process_audit._field(text, "基线")
    sha = raw.strip().strip("`").strip()
    assert re.fullmatch(r"[0-9a-fA-F]{40}", sha), f"填充锚点不是 sha 形：{raw!r}"
