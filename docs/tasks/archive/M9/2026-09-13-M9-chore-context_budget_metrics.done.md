---
status: done
milestone: M9
priority: P3
date: 2026-09-13
---

# 上下文预算度量：命令 stdout 行数 / 被加载 doc 数 / 往返

- **Status**: idea
- **Milestone**: M9
- **Priority**: P3
- **Date**: 2026-09-13

## 已确认意图
给「渐进披露」上观测：量化每条命令实际灌进 agent 上下文的量，为预算（阈值）提供事实依据。观测不判定。

## 可检索摘要
度量三件：①每条命令 stdout 行数/字节；②一次任务中被加载的 doc 数 vs 实际需要数；③往返次数。来自 `next_hook_progressive_disclosure` 残余②。

## 上下文/切入点
- 契约定锚：`ADR-0008 §2`（渐进披露）；观测面沿用 `observe`（G8 先例：只出事实、不进闸）。
- 前件：`pointers`（全状态）与 `status --deep` 已落；命令行 stdout 默认上限在 `gates_config_inventory`（本度量为其提供事实依据）。
- 边界：只统计/出事实（行数、doc 数、往返），不判"超没超"（阈值判定归配置 + 人）。
- 桩子先行：先落"每条命令 stdout 行数"计数，再谈 doc 数/往返。

## 收尾（2026-09-13 拆出跨仓）
- 拆出 k3dit `chore-context_budget_metrics`（并入 `observe`）。
