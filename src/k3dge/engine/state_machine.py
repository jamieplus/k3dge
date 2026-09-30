"""状态机透镜 + **CI 级完备性检查**（graph-lens §1.3/§6；ADR-0001 §2 第 9 条）。

- **建模**用 3.10 stdlib 类型（`Enum`/`NamedTuple`）；**执行**靠本模块的完备性检查（pytest/`check` 跑），
  **不引类型检查器**、不引 Rust。
- 声明＝单一源：`TRANSITIONS` 表 + 显式 `TERMINAL_STATES`；消费者走 `resolve()`（**表驱动＝无手写分支可漏**）。
- **保证面＝commit/CI（非编译期）**；只护**声明表**，手写 `match/if` 的消费点不在保护面。
- 事实、不判定；`status` 观测 `summary()`。
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, List, NamedTuple, Optional, Sequence, Set


class TaskState(Enum):
    IDEA = "idea"
    DEFERRED = "deferred"
    IN_PROGRESS = "in-progress"
    DONE = "done"


class TaskMove(Enum):
    DEFER = "defer"
    START = "start"
    FINISH = "finish"


class Transition(NamedTuple):
    source: TaskState
    move: TaskMove
    target: TaskState


INITIAL: TaskState = TaskState.IDEA
TERMINAL_STATES: frozenset = frozenset({TaskState.DONE})

#: 合法转移（唯一源）；消费者不得另写 `match/if` 分支，一律 `resolve()`。
TRANSITIONS: tuple = (
    Transition(TaskState.IDEA, TaskMove.DEFER, TaskState.DEFERRED),
    Transition(TaskState.IDEA, TaskMove.START, TaskState.IN_PROGRESS),
    Transition(TaskState.IDEA, TaskMove.FINISH, TaskState.DONE),
    Transition(TaskState.DEFERRED, TaskMove.START, TaskState.IN_PROGRESS),
    Transition(TaskState.DEFERRED, TaskMove.FINISH, TaskState.DONE),
    Transition(TaskState.IN_PROGRESS, TaskMove.FINISH, TaskState.DONE),
)


def resolve(state: TaskState, move: TaskMove) -> Optional[TaskState]:
    """表驱动唯一入口：`(state, move) -> target | None`（非法＝None，确定性）。"""
    for t in TRANSITIONS:
        if t.source == state and t.move == move:
            return t.target
    return None


def _reachable(transitions: Sequence[Transition], initial: TaskState) -> Set[TaskState]:
    seen: Set[TaskState] = {initial}
    stack = [initial]
    while stack:
        cur = stack.pop()
        for t in transitions:
            if t.source == cur and t.target not in seen:
                seen.add(t.target)
                stack.append(t.target)
    return seen


def check_completeness(
    transitions: Sequence[Transition],
    states: Set[TaskState],
    terminals: frozenset,
    initial: TaskState,
) -> List[str]:
    """声明表完备性：终态/死锁/确定性/目标合法/可达。返回违规列表（空＝完备）。

    只查**声明表**，不查手写消费者（那须表驱动，见模块 docstring）。
    """
    v: List[str] = []
    for t in transitions:
        if t.target not in states:                                   # ③ 目标态已定义
            v.append(f"未定义目标态 {t.target!r}")
        if t.source in terminals:                                    # ① 终态不得有出边
            v.append(f"终态 {t.source.value} 有出边 -> {t.target.value}")
    outgoing = {t.source for t in transitions}
    for s in sorted(states - set(terminals), key=lambda x: x.value):  # ② 非终态须有出边（防死锁）
        if s not in outgoing:
            v.append(f"非终态 {s.value} 无出边（潜在死锁）")

    def _can_reach_terminal(start: TaskState) -> bool:               # ②b 非终态须**可达终态**（防活锁）
        seen: Set[TaskState] = {start}
        stack = [start]
        while stack:
            cur = stack.pop()
            if cur in terminals:
                return True
            for t in transitions:
                if t.source == cur and t.target not in seen:
                    seen.add(t.target)
                    stack.append(t.target)
        return False

    for s in sorted(states - set(terminals), key=lambda x: x.value):
        if not _can_reach_terminal(s):
            v.append(f"非终态 {s.value} 无法到达任何终态（活锁）")
    seen: Set[tuple] = set()                                         # ④ `(source, move)` 唯一（非确定/二义）
    for t in transitions:
        key = (t.source, t.move)
        if key in seen:
            v.append(f"非确定转移 {t.source.value}/{t.move.value}")
        seen.add(key)
    reach = _reachable(transitions, initial)                         # ⑥ 初始态可达全部
    for s in sorted(states - reach, key=lambda x: x.value):
        v.append(f"不可达状态 {s.value}")
    return v


def completeness_violations() -> List[str]:
    """对内置 task 状态机跑完备性检查（CI 断言 `== []`）。"""
    return check_completeness(TRANSITIONS, set(TaskState), TERMINAL_STATES, INITIAL)


def summary() -> Dict[str, object]:
    """观测件：状态/初态/可达/死状态/违规（不判定）。"""
    reach = _reachable(TRANSITIONS, INITIAL)
    outgoing = {t.source for t in TRANSITIONS}
    return {
        "states": [s.value for s in TaskState],
        "initial": INITIAL.value,
        "reachable": sorted(s.value for s in reach),
        "dead_states": sorted(s.value for s in (set(TaskState) - TERMINAL_STATES - outgoing)),
        "violations": completeness_violations(),
    }
