"""状态机：表驱动 + CI 完备性检查（ADR-0001 §2 第 9 条：建模用 3.10 stdlib，执行靠 CI）。"""

from k3dge.engine import state_machine as sm

T = sm.Transition
S = sm.TaskState
M = sm.TaskMove
_GOOD = sm.TRANSITIONS


def test_task_fsm_is_complete() -> None:
    """内置 task 状态机声明表完备（终态/死锁/确定性/可达/目标合法）。"""
    assert sm.completeness_violations() == []


def test_resolve_is_table_driven() -> None:
    assert sm.resolve(S.IDEA, M.START) == S.IN_PROGRESS
    assert sm.resolve(S.IN_PROGRESS, M.FINISH) == S.DONE
    assert sm.resolve(S.DONE, M.START) is None  # 终态没有出边 ⇒ resolve 返回 None（DONE 行不在表里）
    assert sm.resolve(S.IDEA, M.DEFER) == S.DEFERRED


def test_terminal_with_outgoing_is_flagged() -> None:
    bad = (T(S.DONE, M.START, S.IDEA),) + _GOOD
    v = sm.check_completeness(bad, set(S), sm.TERMINAL_STATES, sm.INITIAL)
    assert any("终态" in x for x in v), v


def test_non_terminal_dead_end_is_flagged() -> None:
    bad = (T(S.IDEA, M.FINISH, S.DONE),)  # DEFERRED/IN_PROGRESS 无出边
    v = sm.check_completeness(bad, set(S), sm.TERMINAL_STATES, sm.INITIAL)
    assert any("无出边" in x for x in v), v


def test_nondeterministic_pair_is_flagged() -> None:
    bad = (
        T(S.IDEA, M.START, S.IN_PROGRESS),
        T(S.IDEA, M.START, S.DEFERRED),  # 同 (source, move) 双目标
    )
    v = sm.check_completeness(bad, set(S), sm.TERMINAL_STATES, sm.INITIAL)
    assert any("非确定" in x for x in v), v


def test_unreachable_state_is_flagged() -> None:
    bad = (
        T(S.IDEA, M.START, S.IN_PROGRESS),
        T(S.IN_PROGRESS, M.FINISH, S.DONE),
        T(S.DEFERRED, M.FINISH, S.DONE),  # DEFERRED 从 IDEA 不可达
    )
    v = sm.check_completeness(bad, set(S), sm.TERMINAL_STATES, sm.INITIAL)
    assert any("不可达" in x for x in v), v


def test_new_state_without_registration_fails() -> None:
    """新增态若不登记（既不加转移也不标终态）⇒ 完备性红（防漂移核心）。"""
    import enum

    # 死锁判据必须用**同一套枚举**验：旧写法另造一个 MoreStates，成员与 TaskState 是
    # 不同对象 ⇒ 每一行都变成"未定义源态/目标态"，`无出边` 其实一条都没产生，
    # 断言是被**错的理由**满足的（t-281）。
    deadlocked = tuple(t for t in _GOOD if t.source is not S.DEFERRED)
    v = sm.check_completeness(deadlocked, set(S), sm.TERMINAL_STATES, S.IDEA)
    assert any(x.startswith("非终态 deferred 无出边") for x in v), v
    assert not [x for x in v if "未定义" in x], v        # 声明集本身没问题


def test_completeness_checks_the_declaration_set_itself() -> None:
    """source/initial/terminals 不在 states 里也必须红（旧只校 target，CI 漏判，ocr-325）。"""
    v_src = sm.check_completeness(_GOOD, set(S) - {S.IN_PROGRESS}, sm.TERMINAL_STATES, S.IDEA)
    assert any("未定义源态" in x for x in v_src), v_src

    v_term = sm.check_completeness(_GOOD, set(S) - {S.DONE}, sm.TERMINAL_STATES, S.IDEA)
    assert any("未声明在 states" in x for x in v_term), v_term

    v_init = sm.check_completeness(_GOOD, set(S), sm.TERMINAL_STATES, "nope")   # type: ignore[arg-type]
    assert any("初始态" in x for x in v_init), v_init
