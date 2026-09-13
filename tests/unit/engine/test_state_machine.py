"""状态机透镜：task 状态转移表 → 可达/死状态/未声明目标。"""
from __future__ import annotations

from k3dge.engine import state_machine as sm


def test_all_states_reachable_and_no_dead() -> None:
    s = sm.summary()
    assert s["unreachable"] == []
    assert s["dead_states"] == []          # done 是唯一无出边者，且为终态
    assert set(s["reachable"]) == set(sm.TASK_STATES)
    assert s["undeclared_targets"] == []


def test_dead_state_and_undeclared_detected_on_custom_table() -> None:
    bad = {"a": {"b"}, "b": set(), "c": {"zzz"}}
    assert sm.dead_states(bad) == ["b"]
    assert sm.reachable(bad, start="a") == {"a", "b"}
    assert sm.unreachable(bad, start="a") == ["c"]
    assert sm.undeclared_targets(bad) == ["zzz"]
