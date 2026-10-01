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
