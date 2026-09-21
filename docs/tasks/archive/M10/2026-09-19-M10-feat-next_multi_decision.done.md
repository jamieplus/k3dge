---
status: done
milestone: M10
priority: P2
date: 2026-09-19
---

# 多处理点交付：sidecar 单槽 → 列表 + STATE_OPTIONS priority（[NEXT] 复数处理点）

- **可检索摘要**: 一次命令可以命中**多个**处理点（实测：`k3dge check` 同轮打了 `seal_ready` 与 `doc_audit` 两块 `[NEXT]`），但三个面不齐：stdout 支持复数（循环 `nextstep.emit`，每块自带 state/fact/options）；**sidecar `.k3dge/next.json` 是单槽**（`persist()` 覆盖写，只剩最后一条）；处理点**优先级无字段**——AGENTS.md §12 用散文写「`pending_findings` 最高优先」，`STATE_OPTIONS` 里没有任何 priority。后果：读 sidecar 的消费者（外来 harness / MCP）看不见排在前面的处理点，且"先处理哪个"只有散文。修法：sidecar 单槽 → `{"next": [...], "primary": <state>}`（保留向后兼容的单条读法）+ `STATE_OPTIONS` 增数值 `priority`（闭集）。

## Intent

k3dge 是**仪表**（ADR-0026 §2.1：agent 的工作流不可编排）。仪表要如实反映"当前有几个处理点、哪个更该先看"，不能因为投递通道的容量而丢信息。

## 证据（实测）

```
同轮两块 [NEXT]（k3dge check 输出）：
  [NEXT] state=seal_ready milestone=M10
    fact: 里程碑 M10 审计已闭环（待修=0）；封板与否由你决定（封＝归档+版本+指针）
    option: k3dge milestone seal M10（align→归档+版本+指针）
    …
  [NEXT] state=doc_audit milestone=M10
    fact: docs/ 有改动：check 是静态硬闸（T-01）…

sidecar 实际内容（单槽）：
  $ cat .k3dge/next.json
  {"state": "doc_audit", …}        ← 只剩最后一条，seal_ready 蒸发
  （nextstep.persist：path.write_text(json.dumps(ns.render_mcp()…)) —— 覆盖写）

优先级：整个 STATE_OPTIONS 无 priority 键；"最高优先"只写在
  AGENTS.md §12 的「代码/文档里有 k3dit:pending 钉」行（散文）
```

## 方案

```
① sidecar 形状（向后兼容）
   .k3dge/next.json = {"next": [<card>…], "primary": "<state>"}
   - 每个 <card> 即现在 render_mcp() 的形状（state/milestone/fact/options/question/pointers）
   - 同轮重复 state 去重（同 state 只留一条，后来的合并 reasons）
   - persist(ns) 改成 upsert 语义（同一轮内累积；`nextstep.reset(workspace)` 在命令入口清空）
   - **兼容读法**：load_persisted() 见到单条（旧形状）也返回；新增 load_all()
② priority（闭集，进声明表）
   STATE_OPTIONS[state]["priority"]: int（小的先看；同值按声明顺序稳定）
   实测待定值：pending_findings=1（最高，现在只写在散文里）> audit_open/audit_needed=2
                > reject 类=3 > audit_suggested/seal_ready/rejected=4 > 播报态=9
   - 消费者：`[NEXT]` 渲染时按 priority 排序（stdout 顺序稳定且有意义）；
     sidecar 的 `primary` = 最小 priority 那条
③ 渲染
   render_cli() 不变（单块形状不变，避免破坏现有解析）；排序在 emit 层做
   （多块场景由 cli 汇总后统一 emit，而不是各调各的 emit——现在是每处各自 emit）
```

## 边界与拆分（规则 08）

- 事实归属：**处理点集合**归各命令（谁命中谁 emit）；**排序**归 `nextstep`（priority 表）；**投递**归 `persist`（单写者）。命令不得自己算优先级。
- 边界检查：不改 MCP 工具返回值里已有的 `next` 单条字段（那是给"这一动作的下一步"的，语义不同）；sidecar 是**跨命令的当前处理点集合**，两者不混。
- 桩子先行：先落 `priority` 字段 + `load_all`/`reset` + 排序，sidecar 暂保持单槽（只写 primary）⇒ 行为等价、可测；再切 sidecar 到列表形状（读侧兼容旧形状）。
- **不编排**：只排序与陈列，不给 agent 下步骤（ADR-0026 §2.6：k3dge 不得编排自主工作流）。priority 是"先看哪个"的建议，不是执行顺序指令。

## 验收

- 一次命中两个处理点时，sidecar 含两条且 `primary` 指向 priority 最小者（实测同轮 `seal_ready` + `doc_audit`）；
- 旧形状 sidecar（单条）仍能被 `load_persisted` 读出（向后兼容断言）；
- 每个 state 都有 priority（闭集守卫：缺 priority 即红；播报态也须显式给值）；
- 排序稳定（同 priority 按 STATE_OPTIONS 声明序，跑两遍一致）；
- 全量 pytest 绿；`k3dge sync` 回写契约哈希；`k3dge check` 绿。

## Notes

- 来源：本轮设计讨论中我提的三问之一，用户裁定「开票」（2026-09-19）。
- 与 doc 新策略的依赖：一次提交可能同时命中「新建未排查」（`DOC_NEW_UNSCREENED`）与「可自动修偏差」（`doc_normalize`），两类处理点必须并存且有序——本票是那个场景的地基。
- 有意留（本票不做）：`[NEXT]` 从"每命令各自 emit"改成"命令返回 hints、由统一出口 emit"——那属 `orch_node_table` 的单执行器收编。

## 落地（2026-09-19）

| 项 | 落点 | 实测 |
| --- | --- | --- |
| ① 侧车新形状 | `{"next": [card...], "primary": <state>}`；`persist`＝**替换**（单判定流程用），`emit`＝本轮 **upsert**（同 state 去重），`begin_run`＝清空 | `check` 后 `primary=seal_ready`、`next=[(seal_ready,4),(doc_audit,5)]`——**改前只剩 doc_audit** |
| ② priority（闭集） | `STATE_OPTIONS[*].priority`：1 需人立即介入（pending_findings/escalated）／2 环未闭环（audit_open/audit_needed）／3 被拒／4 决策点／5 在办与后续步／9 播报 | 每态都有；守卫测试锁闭集 |
| ③ 排序与投影 | `emit_all(steps)` 按 `(priority, 声明序)` 稳定排序后打印；`priority` 进 MCP 投影（读侧要能自己排）；`[NEXT]` 不打印它（顺序已表达） | `check` 的 stdout 顺序＝priority 序 |
| ④ 一轮边界 | `cli.main()` 调 `begin_run`（**单一入口**；MCP 不调 —— 它的工具各自直接构造 NextStep，不累积） | `task list`（无提示）后侧车清空；`check` 后只有它自己的处理点 |
| ⑤ 向后兼容 | `load_all()` 读新形状；旧单条形状 ⇒ 单元素列表；`load_persisted()` 返回 `primary`（MCP 的单值读法不变） | 测试 `test_load_persisted_accepts_legacy_single_shape` |

### 途中被自己抓到两处

1. **排序失效**：卡片里没带 `priority` ⇒ `_upsert` 排序全落默认值 5，`primary` 错成 `seal_ready`（应为 `pending_findings`）。修：`render_mcp()` 带上 `priority`（读侧也需要它）。
2. **测试断言旧形状**：`test_next_sidecar` 与 `seal_flow::_sidecar` 按旧单槽断言 ⇒ 更新为读主卡片。

### 有意留（票内已记）

- `[NEXT]` 从"各命令自己 emit"改成"命令返回 hints、由统一出口 emit"——属 `orch_node_table` 的单执行器收编。
- MCP 侧不调 `begin_run`：其 14 个工具各自构造并回传 NextStep（不经过侧车累积），故无跨调用污染；若将来有工具改走 `emit`，需在那里补 `begin_run`。

## 验收（实测）

```
608 passed；k3dge check 绿
tests/unit/engine/test_next_sidecar.py（11 条）：新形状 / persist 替换 / emit upsert+排序 /
  同 state 去重 / begin_run 清空 / emit_all 排序+写全量 / stdout 顺序 / 旧形状兼容 / 打印开关
tests/unit/engine/test_nextstep.py::TestProjectionInvariants：每态有 priority 且在闭集内 /
  priority 进 MCP 投影且不进 [NEXT]
端到端：k3dge check ⇒ 两块按 priority 排 + 侧车两条 + primary=seal_ready；
        k3dge task list（无提示）⇒ 侧车被清空（按轮重置生效）
```
