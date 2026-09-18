---
status: idea
milestone: M10
priority: P3
date: 2026-09-17
---

# 判定点单源化：prompt 文案源出 STATE_OPTIONS

- **Status**: idea
- **Milestone**: M10
- **Priority**: P3
- **可检索摘要**: 同一判定点的文案在两处各写一遍且已漂移——`STATE_OPTIONS["seal_ready"].ask`（`审计已闭环（待修=0），封板？`）vs `seal_flow.py` 的 `prompt.ask("里程碑 {id} 审计已闭环，封板？")`。`audit_open` 同形（`agent 修？` vs `审计/质量共发现 {n} 项待修。是否由 agent 修复？`）。修法待定形：一个判定声明 + 两投影（`[NEXT]` / `prompt`）。
- **Date**: 2026-09-17

## 意图

消除判定点文案的双源。源：`docs/memo/archive/2026-09-16-orchestration-form-exploration.md` 下一步第 5 项（memo 标「先定形再评」）。

## 证据（实测）

```
封板判定
  [NEXT] : STATE_OPTIONS["seal_ready"].ask = "审计已闭环（待修=0），封板？"
  prompt : seal_flow.py:136               = "里程碑 {id} 审计已闭环，封板？"

修不修判定
  [NEXT] : STATE_OPTIONS["audit_open"].ask = "agent 修？"
  prompt : milestone_audit.py:266          = "审计/质量共发现 {n} 项待修。是否由 agent 修复？"

⇒ 同一判定点两处文案，措辞不一致（且 prompt 侧缺「待修=0」、[NEXT] 侧缺里程碑 id）
```

## 待定形（本票的阻塞点）

候选形状：

| 方案 | 内容 | 代价 |
|---|---|---|
| **(a) prompt 源出 STATE_OPTIONS** | `prompt.ask(f"里程碑 {id} {STATE_OPTIONS['seal_ready']['ask']}", ...)` | `audit_open` 有动态计数（`{n}` 项待修），需占位符机制 |
| **(b) 加 `prompt` 参数字段** | STATE_OPTIONS 增 `prompt: {default_yes, countdown}`；文案单源 | 新增字段；`[NEXT]` 与 prompt 共用一句疑问句（与 S7 的陈述式方向相抵） |
| **(c) 明分两投影** | 声明 `fact`（陈述）+ `decision`（疑问主体）；两通道各自渲染 | 结构变更最大；MCP JSON 形状变（`.next.ask`/`if_y`） |

**(a)/(c) 的取舍取决于要不要同时落 S7 的「[NEXT] 陈述式」**——若落，则 (c) 是自然形态；若不落，(a) 更小。

## 边界与拆分（feat 类必填；规则 08）

- 事实归属：判定文案归 `nextstep.STATE_OPTIONS`（唯一源）；`prompt` 只负责渲染与收回答
- 边界检查：`prompt.ask` 的 `default_yes` / `countdown` 是**通道行为**，不是文案——是否也单源化待定
- 桩子先行：先定形（上表三选一）→ 再改

## Notes

- **阻塞**：定形未决，不能开工（memo 原判「先定形再评」）
- memo 归档的前置条件之一（另一为 ADR 投影契约票）
- 已完成的相邻项：装饰词删除（用户裁定 B，2026-09-17）——那是本项的一小部分，不含单源化
