---
status: done
milestone: M9
priority: P2
date: 2026-09-12
---

# 任务 DAG 透镜：blocking 环检测 + CPM 关键路径

- **Status**: done
- **Milestone**: M9
- **Priority**: P2
- **可检索摘要**: 把 task `blocking` 字段（`peer_contract §9` 已声明、引擎无消费者）变成图：互阻环 → check WARN；里程碑最长路径 → status 观测行（观测不判定）。
- **Date**: 2026-09-12

## Intent
工单 DAG 成为可机检图性质：blocking 环（死锁队列）WARN；CPM 关键路径作 status 观测行。

## 上下文/切入点
- 来源：memo `docs/memo/archive/2026-09-05-graph-lens-for-audit-and-qa.md` §1.4/§6（图 memo 落地顺序起步项）。
- 现状：`peer_contract §9` 声明 `blocking`(optional)，**引擎无消费者**；无环检测/关键路径。
- 落点：`k3dge check`（纯静态、零 LLM）加环检测 WARN；`status` 加 CPM 观测行。
- 实现：stdlib `graphlib.TopologicalSorter`（`CycleError`），零依赖（§7.1）。

## 边界与拆分
- 事实归属：DAG 事实（边表/环/路径）确定性归 k3dge；"这个环要不要紧"判读归复核窗。
- 边界检查：环**只 WARN 不阻断**（声明可缺，先观测）；CPM 只观测不进闸。
- 桩子先行：先读 `blocking` 建边表 + fixture 造互阻环，再上 WARN/观测行。

## 验收
- blocking 环出 WARN+证据；无环绿；status 出关键路径观测行；零依赖。

## 收尾（2026-09-13 已落）
- **立字段**：task frontmatter 可选 `blocking:`（逗号/空格分隔 task stem）写入 `docs/tasks/AUTHORING.md`（模板副本同步）。注：原票引 `peer_contract §9` 已不存在（契约 v0.6 无 §9），字段改由 tasks 契约定义。
- **实现**：`engine/task_dag.py`＝`blocking_graph`/`blocking_cycles`/`critical_path`/`summary`（stdlib `graphlib`）。
- **接入**：`k3dge status --json` / MCP `k3dge_status` 增 `task_dag`（环 + 关键路径）——**观测不判定**，不进 `check`（环不阻断，遵本票边界）。
- 测试 `test_task_dag.py`（链/环/未知依赖）。302 passed；check 绿。
