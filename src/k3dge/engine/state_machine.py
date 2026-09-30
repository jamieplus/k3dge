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


def _dead_states(states: Set[TaskState], terminals: frozenset,
                 transitions: Sequence[Transition]) -> Set[TaskState]:
    """非终态且无出边 = 死状态。**判据单源**：CI 完备性检查与观测件 `summary()` 共用这一处（464）。"""
    outgoing = {t.source for t in transitions}
    return set(states) - set(terminals) - outgoing


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
    # 先校**声明集自身**：source/initial/terminals 不在 states 里时，下面的死锁/可达/确定性
    # 判据全都建立在错误前提上（CI 只查 target ⇒ 自造表漏判，325）
    for s in sorted(set(terminals) - set(states), key=lambda x: getattr(x, "value", str(x))):
        v.append(f"终态 {getattr(s, 'value', s)!r} 未声明在 states 里")
    if initial not in states:
        v.append(f"初始态 {getattr(initial, 'value', initial)!r} 未声明在 states 里")
    for t in transitions:
        if t.source not in states:                                   # ③b 源态已定义
            v.append(f"未定义源态 {t.source!r}")
        if t.target not in states:                                   # ③ 目标态已定义
            v.append(f"未定义目标态 {t.target!r}")
        if t.source in terminals:                                    # ① 终态不得有出边
            v.append(f"终态 {t.source.value} 有出边 -> {t.target.value}")
    dead = _dead_states(states, terminals, transitions)
    for s in sorted(dead, key=lambda x: x.value):                     # ② 非终态须有出边（防死锁）
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
    return {
        "states": [s.value for s in TaskState],
        "initial": INITIAL.value,
        "reachable": sorted(s.value for s in reach),
        "dead_states": sorted(s.value for s in _dead_states(set(TaskState), TERMINAL_STATES, TRANSITIONS)),
        "violations": completeness_violations(),
    }
