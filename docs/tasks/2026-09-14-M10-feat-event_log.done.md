---
status: done
milestone: M10
priority: P3
date: 2026-09-14
blocking: 2026-09-14-M10-feat-unify_next_step_channel
---

# Event Log：`.k3dge/events.jsonl` 操作事实日志

- **Status**: done
- **Milestone**: M10
- **Priority**: P3
- **blocking**: 2026-09-14-M10-feat-unify_next_step_channel
- **可检索摘要**: 新增 `engine/events.py`，append-only JSONL 记录所有状态变迁（gate/audit/seal/task/next），为 debug 和未来 dashboard 提供操作历史。不替换现有通道，只旁路 append。
- **Date**: 2026-09-14

## 意图

"刚才发生了什么"目前要翻 `audit_jobs.json` / `audit_checklist.json` / `logs/k3dge.log` / stdout 四处。一个 append-only JSONL 统一为单一事实源。

**不支撑操作完成钩子**——钩子只需 `next.json`（指令层），不需要事件历史。本票是可观测性基础设施，为未来 dashboard / CI 集成铺路。

## 方案

### `engine/events.py`

```python
def emit(workspace: Path, evt: str, **data) -> None:
    path = workspace / ".k3dge" / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"ts": _now(), "evt": evt, **data}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    _rotate(path, max_lines=1000)
```

### emit 点（首批）

| evt | 调用位置 | 现有通道 |
|---|---|---|
| `gate_pass` / `gate_fail` | `evaluator.evaluate()` 尾部 | stdout |
| `audit_submit` | `audit_flow.submit_audit()` | audit_jobs.json |
| `audit_collect` | `audit_flow.collect_audit()` | audit_jobs.json |
| `task_done` | `task_write.mark_task_done()` | CHANGELOG |
| `next` | `nextstep._persist()` | next.json |
| `downgrade` | `pipeline_runner.run_action()` | logs/k3dge.log |
| `sealed` | `seal_flow.run_seal_flow()` | stdout |

### 与 next-step task 的关系

`nextstep._persist()` 内部复用 `events.emit(workspace, "next", ...)` — 一行代码，不引入额外依赖方向（events 不 import nextstep）。

### 与现有通道的关系

**不替换**。audit_jobs.json / logs 继续各写各的。events.jsonl 是旁路 append，不影响现有消费者。未来可以考虑让 logs 从 events.jsonl 派生，但本票不做。

## 边界与拆分（feat 类必填；规则 08）

- 事实归属：`engine/events.py` 拥有 `emit()` + `_rotate()`；其他模块只调 `emit()`
- 边界检查：fire-and-forget，emit 失败不阻断命令主路径（catch + warn）
- 桩子先行：先实现 `emit()` + `_rotate()` + 测试 → 一个命令加 emit → 推广

## Notes

- 改动量：`events.py` ~30 行 + 7 处 emit 调用点 + 测试
- rotate 策略：超 1000 行时保留后 800 行（截断头部）
- 单进程模型，无并发写问题
