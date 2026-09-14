---
status: done
milestone: M9
priority: P3
date: 2026-09-13
---

# 评估 MCP 面收敛单强工具 k3dge_explore

- **Status**: idea
- **Milestone**: M9
- **Priority**: P3
- **可检索摘要**: 评估并把 k3dge MCP 面默认收敛为一个强工具 `k3dge_explore`（NEXT + 事实 + 纵深指针），吸收 codegraph "one strong tool 胜过菜单"；来源 memo §1。
- **Date**: 2026-09-13

## Intent
减少 agent 选错工具/省上下文，呼应 ADR-0008 §2 渐进披露。

## 边界与拆分
- 事实归属：MCP 面＝k3dge CLI 桥；判定不变。
- 边界检查：单工具只聚合既有事实 + `[NEXT]` 指针，**不新增判定**；禁私有重实现门禁（ADR-0006）。
- 桩子先行：先造 `k3dge_explore`（聚合 status+next+相关 doc 指针），A/B 观测调用次数；其余工具保留可开关恢复。

## 验收
- 默认暴露 `k3dge_explore`；其余可开关恢复；行为等价、无判定漂移。

## 收尾（2026-09-13 关停/并入）
- 单一 MCP 入口＝体验（非能力）；本方针下**不囤**。
