"""ConsistencyEngine 的检查组：每组自成一模块，只共享 `workspace_root`。

`evaluator.ConsistencyEngine` 仍是对外唯一入口（`evaluate()`），本包只承载各检查的**实现**。
各模块公开一个 `check_<x>(workspace) -> List[Violation]`（与 `pure_refs` 的 `check_*` 同形）；模块内的 `_logs_*` 等辅助保持私有。
"""
