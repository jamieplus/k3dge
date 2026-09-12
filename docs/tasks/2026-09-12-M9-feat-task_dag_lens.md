---
status: idea
milestone: M9
priority: P2
date: 2026-09-12
---

# 任务 DAG 透镜：blocking 环检测 + CPM 关键路径

- **Status**: idea
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
