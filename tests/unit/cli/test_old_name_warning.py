"""提交信息里的**错写**提示（advisory）：`k3ge` 裸写即提示。

`k3ge` 不是历史名（不存在这个仓），纯属错写；唯一合法出现是**在引用这个错写本身**（反引号跨度）——
检测器/测试/文档必须能写它。危害实测：2026-09-26 一天内被写进 4 条提交信息。
"""

from k3dge.cli.main import old_name_warnings


def test_bare_typo_is_flagged():
    assert old_name_warnings("feat: 接线\n\nk3ge 作为消费方随之调整") == ["k3ge 作为消费方随之调整"]
    # 勘误句里**裸写**也提示（没有"历史名"这回事；要引用就加反引号）
    assert old_name_warnings("docs: 勘误 k3ge -> k3dge") == ["docs: 勘误 k3ge -> k3dge"]


def test_backticked_reference_is_allowed():
    for line in ("feat(commit-msg): 提示提交信息里的 `k3ge`（反引号跨度＝在引用这个错写）",
                 "docs: 复现例：（`k3ge 作为消费方` 等）曾被写进 4 条信息"):
        assert old_name_warnings(line) == [], line


def test_clean_message_has_no_warning():
    assert old_name_warnings("feat(x): 新增 k3dge 侧消费接线") == []
    # 返回契约的边界输入（t-009）：空消息、只有干净标题——别哪天 None/整条消息回吐
    assert old_name_warnings("") == []
    assert old_name_warnings("feat(x): 标题") == []


def test_multiple_offenders_keep_document_order_and_are_stripped():
    """返回契约＝**每条被冒犯行、strip 后、文档序、不去重**（t-009）：
    旧测全钉单元素列表——改成"整条消息回吐/不去重/不 strip/换序"都看不见。"""
    msg = ("docs: 修名\n\n"
           "k3ge 作为消费方\n\n"
           "    - k3ge 缩进正文行\n\n"
           "    - k3ge 缩进正文行\n\n"      # ocr2-408：逐字重复——去重实现会在此现形
           "k3ge 又一处裸写")
    assert old_name_warnings(msg) == ["k3ge 作为消费方",
                                      "- k3ge 缩进正文行",
                                      "- k3ge 缩进正文行",   # 不去重：两次都出现
                                      "k3ge 又一处裸写"]


def test_mixed_line_bare_typo_is_still_flagged():
    """**混合行**是旧"整行豁免"的漏网点（t-008）：一行里既有反引号引用又有裸写时，
    旧实现见引用即放行 ⇒ 裸错写静默逃逸——advisory 检测器恰恰死在这个形状。
    契约（本轮定死）：反引号跨度只是**局部**豁免，抹掉后仍有裸写就提示。
    """
    mixed = "docs: 把 `k3ge` 的裸写（如 k3ge 作为消费方）改掉"
    assert old_name_warnings(mixed) == [mixed], old_name_warnings(mixed)
    # 对照：全引用的行仍豁免（必要引用不被扰）
    assert old_name_warnings("docs: 引用 `k3ge` 与 `k3ge x` 两处") == []
