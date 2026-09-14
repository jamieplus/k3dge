"""里程碑对齐（`milestone align`）：读 `[checks.align]` 契约跑 Full Matrix + 生成对齐报告。

Extracted from `engine/milestone.py` (A-1 第十块); `milestone` re-exports for back-compat.
"""
from __future__ import annotations

import datetime
from pathlib import Path
from typing import List, Tuple

from k3dge.engine import gates
from k3dge.engine.evaluator import ConsistencyEngine
from k3dge.engine.milestone_pointer import _validate_milestone_id
from k3dge.engine.task_index import _ALLOWED_STATUS, MilestoneTask, scan_milestone_tasks

_ALIGN_STUB_MARKER = "<!-- k3dge:align-stub -->"


def _align_pass_marker(milestone_id: str) -> str:
    return f"<!-- k3dge:align-pass:{milestone_id} -->"


# k3dit:leftover value-7 已登记进 refactor-cc_debt_remaining 待拆表（一 diff 一测试）；本窗无 tests 不可验行为
def run_milestone_alignment(workspace: Path, milestone_id: str) -> Tuple[bool, str, List[MilestoneTask]]:
    from k3dge.engine.milestone import scan_unfilled_guides

    id_err = _validate_milestone_id(milestone_id)
    if id_err:
        return False, id_err, []

    tasks = scan_milestone_tasks(workspace, milestone_id)
    if not tasks:
        return False, f"No tasks found for milestone '{milestone_id}' under docs/tasks/", []

    invalid = [t for t in tasks if t.status not in _ALLOWED_STATUS]
    if invalid:
        listing = "\n".join(f"  - {t.path.name} (status: {t.status})" for t in invalid)
        return False, f"Invalid Status (not idea|deferred|in-progress|done):\n{listing}", tasks

    # 前置闸/动作：读「硬闸契约」`[checks.align]`（ADR-0001 §2 第 8 条）。
    pending = [t for t in tasks if t.status != "done"]

    def _tasks_all_done():
        if pending:
            return f"Cannot align milestone '{milestone_id}'. {len(pending)} pending tasks:\n" + "\n".join(
                f"  - {t.path.name} (status: {t.status})" for t in pending
            )
        return None

    def _full_matrix():
        report = ConsistencyEngine(workspace).evaluate(run_tests=True, force_full=True)
        if not report.passed:
            return f"Regression tests failed during milestone alignment:\n{report.render()}"
        return None

    _reg = {"tasks_all_done": _tasks_all_done, "full_matrix": _full_matrix}
    for _gid in gates.preconditions(workspace, "align"):
        _fn = _reg.get(_gid)
        if _fn is None:
            return False, f"[ALIGN REJECTED] gate contract references unknown gate id: '{_gid}'", tasks
        _err = _fn()
        if _err:
            return False, _err, tasks
    for _aid in gates.actions(workspace, "align"):
        _fn = _reg.get(_aid)
        if _fn is None:
            return False, f"[ALIGN REJECTED] gate contract references unknown action id: '{_aid}'", tasks
        _err = _fn()
        if _err:
            return False, _err, tasks

    # 2. 生成极简对齐评审报告
    today = datetime.date.today().isoformat()
    review_file = workspace / "docs" / "reviews" / f"{today}-{milestone_id}-align.md"
    if not review_file.exists():
        review_file.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"# 里程碑对齐与验收报告: {milestone_id}",
            _ALIGN_STUB_MARKER,
            _align_pass_marker(milestone_id),
            "",
            f"- **Date**: {today}",
            "- **Regression**: PASS (k3dge milestone align Full Matrix)",
            f"- **Completed Tasks**: {len(tasks)}",
            "",
            "## 1. 目标达成清单",
            "",
        ]
        for t in tasks:
            lines.append(f"- [x] `{t.path.name}`")
        lines.extend([
            "",
            "## 2. 重构准入评估",
            "> 仅在存在阻塞后续扩展的设计缺陷时启动重构；常规情况下跳过大重构。",
            "",
            "- [ ] 是否存在阻塞后续阶段的架构/接口缺陷？(Yes/No)",
            "- [ ] 是否存在超出阈值的深层嵌套坏味道？(Yes/No)",
            "- 处置结论: 跳过重构直接封板 / 触发定向微调",
            "",
            "## 3. 验收结论",
            "目标达成，契约一致，准予封板压缩。",
            "",
        ])
        review_file.write_text("\n".join(lines), encoding="utf-8")

    # 3. 指南完成度扫描（预警非阻断）：docs/guides/ 残留的 TODO 桩在 seal 时会被硬拦
    unfilled = scan_unfilled_guides(workspace)
    note = ""
    if unfilled:
        note = (
            " WARNING: unfilled guide stubs (will block seal): "
            + ", ".join(unfilled)
        )

    msg = (
        f"[ALIGN] Full Matrix verification PASS for milestone '{milestone_id}'.\n"
        f"  Created review scaffold: docs/reviews/{today}-{milestone_id}-align.md\n"
        f"  Milestone is seal-eligible. Audit is mandatory before seal "
        f"(k3dge milestone seal -> enter-seal prompt -> k3dit.actions.audit)."
    )
    if note:
        msg += note
    return True, msg, tasks
