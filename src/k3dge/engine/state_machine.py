"""状态机透镜（graph-lens §1.3/§6）：**声明的** task 状态转移表 → 可达性/死状态/非法跃迁事实。

本模块是 task 状态机的**声明源**（与 `docs/tasks/AUTHORING.md` 的 Status 枚举、`mark_task_done`
的合法流转一致）。**事实，不判定**：只出可达/死状态事实，不进 `check`。
"""
from __future__ import annotations

from typing import Dict, List, Set

#: task 状态枚举（= AUTHORING Status 枚举）。
TASK_STATES: tuple = ("idea", "deferred", "in-progress", "done")
#: 合法转移（声明源）：`from -> {to}`。`done` 为终态。
TASK_TRANSITIONS: Dict[str, Set[str]] = {
    "idea": {"deferred", "in-progress", "done"},
    "deferred": {"in-progress", "done"},
    "in-progress": {"done"},
    "done": set(),
}
INITIAL = "idea"


def reachable(transitions: Dict[str, Set[str]] = TASK_TRANSITIONS, start: str = INITIAL) -> Set[str]:
    """从 `start` BFS 可达的状态集。"""
    seen = {start}
    stack = [start]
    while stack:
        for nxt in transitions.get(stack.pop(), set()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def dead_states(transitions: Dict[str, Set[str]] = TASK_TRANSITIONS) -> List[str]:
    """非终态却无出边＝死状态（悬挂）。"""
    return sorted(s for s, out in transitions.items() if not out and s != "done")


def unreachable(transitions: Dict[str, Set[str]] = TASK_TRANSITIONS, start: str = INITIAL) -> List[str]:
    return sorted(set(transitions) - reachable(transitions, start))


def undeclared_targets(transitions: Dict[str, Set[str]] = TASK_TRANSITIONS) -> List[str]:
    """出边指向的目标未在转移表中作为源声明＝未声明目标。"""
    targets = {t for outs in transitions.values() for t in outs}
    return sorted(targets - set(transitions))


def summary() -> Dict[str, object]:
    """观测件：state 数 / 可达 / 死状态 / 未声明目标（不判定）。"""
    return {
        "states": list(TASK_STATES),
        "reachable": sorted(reachable()),
        "dead_states": dead_states(),
        "unreachable": unreachable(),
        "undeclared_targets": undeclared_targets(),
    }
