"""提交信息里的历史仓名提示（advisory）：`k3ge` 非引述上下文才提示。

为什么要有：2026-09-26 一天内我把它写进 4 条提交信息（`k3ge 作为消费方` 等），而工作树里的同类
残留早已清干净 —— 只靠"记得"守不住。改名/勘误提交必须能引述旧名，故**只提示不阻断**。
"""
from __future__ import annotations

from k3dge.cli.main import old_name_warnings


def test_slip_is_flagged():
    msg = "feat: 接线\n\nk3dit 改完后，k3ge 作为消费方随之调整："
    assert old_name_warnings(msg) == ["k3dit 改完后，k3ge 作为消费方随之调整："]


def test_quotes_and_errata_are_allowed():
    for line in ("chore: 清掉旧名 k3ge 与跨仓引用",
                 "feat(commit-msg): 提示提交信息里的 `k3ge`（反引号跨度＝在描述这个名字）",
                 "docs: 复现例：（`k3ge 作为消费方` 等）曾被写进 4 条信息",
                 "docs: 勘误 k3ge → k3dge（M8 审计报告 ×2）",
                 "docs: 修掉一处旧称 k3ge 的注释",
                 "fix: 临时目录前缀 k3ge-apply-dry- → k3dge-apply-dry-"):
        assert old_name_warnings(line) == [], line


def test_clean_message_has_no_warning():
    assert old_name_warnings("feat(x): 新增 k3dge 侧消费接线") == []
