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
    # ocr2-529：逐条复现**全部**声明行（旧测只抽 3/6，IDEA/FINISH、DEFERRED/* 无行为断言——
    # 某行 target 被换成另一个合法态时表仍确定/无死锁/可达，全绿）。
    for t in sm.TRANSITIONS:
        assert sm.resolve(t.source, t.move) is t.target, t
    # 补：每个**未声明**的 (state, move) 必须返回 None（表↔resolve 双向一致）
    declared = {(t.source, t.move) for t in sm.TRANSITIONS}
    for state in sm.TaskState:
        for move in sm.TaskMove:
            if (state, move) not in declared:
                assert sm.resolve(state, move) is None, (state, move)


def test_terminal_with_outgoing_is_flagged() -> None:
    # 消息**必须专属这条规则**（t-282）："终态"同时出现在死锁/活锁两支的"非终态 …"
    # 文案里——子串 `"终态"` 在别的规则上也成立，规则①回归时此测可能照绿。
    # 现在钉规则①自己的措辞 `终态 <s> 有出边 -> <t>`，并排除其它两支的句式。
    bad = (T(S.DONE, M.START, S.IDEA),) + _GOOD
    v = sm.check_completeness(bad, set(S), sm.TERMINAL_STATES, sm.INITIAL)
    own = [x for x in v if "有出边 ->" in x and x.startswith("终态")]
    assert own, v
    assert any("done" in x for x in own), own
    assert not [x for x in v if "无出边" in x or "活锁" in x], v


def test_non_terminal_dead_end_is_flagged() -> None:
    # 夹具把 _GOOD 整个丢掉，活锁/不可达噪声会同屏（t-283）——关键词只锁**死锁规则自己**
    # 的句式，并点名列出的状态：被标的是 DEFERRED/IN_PROGRESS，不含 DONE（终态不该报）。
    bad = (T(S.IDEA, M.FINISH, S.DONE),)  # DEFERRED/IN_PROGRESS 无出边
    v = sm.check_completeness(bad, set(S), sm.TERMINAL_STATES, sm.INITIAL)
    dead = [x for x in v if "无出边" in x]
    assert dead, v
    assert any("deferred" in x for x in dead) and any("in-progress" in x for x in dead), dead
    assert not [x for x in dead if "done" in x], dead


def test_nondeterministic_pair_is_flagged() -> None:
    # **叠在 _GOOD 上**（t-284）：独立两行的夹具会顺带触发死锁/活锁/不可达一串噪声，
    # "红了几条"里分不清哪条是二义性引的。叠加后违例恰好只有二义性这一条。
    bad = _GOOD + (T(S.IDEA, M.FINISH, S.DEFERRED),)     # ('idea','finish') 已有目标 done → 双目标
    v = sm.check_completeness(bad, set(S), sm.TERMINAL_STATES, sm.INITIAL)
    assert len(v) == 1, v
    assert any("非确定" in x for x in v), v


def test_unreachable_state_is_flagged() -> None:
    # ocr2-791：与邻测（t-282/283/284）同标准——只断"有条含 不可达"时，
    # 报去别的态（如 initial/全态）的回归照样绿。本夹具其余规则全干净，
    # 故钉死恰一条、点名 deferred、无其它噪声。
    bad = (
        T(S.IDEA, M.START, S.IN_PROGRESS),
        T(S.IN_PROGRESS, M.FINISH, S.DONE),
        T(S.DEFERRED, M.FINISH, S.DONE),  # DEFERRED 从 IDEA 不可达
    )
    v = sm.check_completeness(bad, set(S), sm.TERMINAL_STATES, sm.INITIAL)
    unreach = [x for x in v if "不可达" in x]
    assert unreach, v
    assert any("deferred" in x for x in unreach), unreach
    assert len(v) == 1, v


def test_new_state_without_registration_fails() -> None:
    """新增态若不登记（既不加转移也不标终态）⇒ 完备性红（防漂移核心）。"""

    # 死锁判据必须用**同一套枚举**验：旧写法另造一个 MoreStates，成员与 TaskState 是
    # 不同对象 ⇒ 每一行都变成"未定义源态/目标态"，`无出边` 其实一条都没产生，
    # 断言是被**错的理由**满足的（t-281）。
    # ocr2-530：夹具必须与 docstring 一致——DEFERRED **既不做出边也不做入边**（旧夹具
    # 只删 source=DEFERRED，仍留 IDEA-DEFER->DEFERRED，与 `test_non_terminal_dead_end`
    # 同形）。真正"表里没有它任何一行"时，死锁判据要能报出来。
    unregistered = tuple(t for t in _GOOD
                         if t.source is not S.DEFERRED and t.target is not S.DEFERRED)
    assert len(unregistered) == len(_GOOD) - 3, unregistered   # 前置：确实删了所有触及行
    v = sm.check_completeness(unregistered, set(S), sm.TERMINAL_STATES, S.IDEA)
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


def test_garbage_labels_do_not_crash_the_checker() -> None:
    # 函数契约是"返回违例列表"：自造坏表（含非 Enum 的 target / 纯字符串 states）
    # 不得抛 AttributeError（ocr2-666）。消息经 getattr 取 label。
    bad = (T(S.DONE, M.START, "idea"),)  # type: ignore[arg-type]
    v = sm.check_completeness(bad, set(S), sm.TERMINAL_STATES, S.IDEA)
    assert any("未定义目标态" in x for x in v), v
    assert any("有出边" in x for x in v), v

    v2 = sm.check_completeness(
        (T("done", "start", "idea"),), {"done", "idea"}, frozenset({"done"}), "done")  # type: ignore[arg-type]
    assert isinstance(v2, list) and v2, v2
