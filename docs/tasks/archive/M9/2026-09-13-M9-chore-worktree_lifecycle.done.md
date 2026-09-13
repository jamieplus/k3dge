---
status: done
milestone: M9
priority: P3
date: 2026-09-13
---

# worktree 生命周期吸收（hooks 类型/自动 prune/list 状态）

- **Status**: idea
- **Milestone**: M9
- **Priority**: P3
- **Date**: 2026-09-13

## 已确认意图
把 worktrunk 的 worktree 生命周期模式（clean-room）吸收到 k3ge 审计线编排：hook 类型划分、同 commit 自动 prune、list 状态表。

## 可检索摘要
来源 memo §3。落点 `engine/worktree.py`（审计线）、`run_seal_flow`（`on_seal_enter`/`on_pre_seal`≡pre/post-merge）、`prune_finished`、`status`。

## 上下文/切入点
- pre-merge/post-merge ↔ 我们"落点闸先验后并"（`merge_back`）；同 main commit ⇒ 后台自动 remove ↔ `prune_finished`；`wt list`（ahead/behind/dirty/unpushed）↔ `status` 观测。
- 边界：**不引入 `wt` 依赖**；只吸收类型/语义，实现仍在 k3ge。

## 边界与拆分
- 桩子先行：先给 `prune_finished` 加"与主干同 commit ⇒ 自动清"；再谈 hook 命名对齐与 `status` 观测行。

## 验收
- 审计线生命周期语义与 worktrunk hook 类型对齐；`status` 出 ahead/behind/dirty 观测；零依赖。

## 收尾（2026-09-13 关停/并入）
- worktree 生命周期 k3ge 已够（`worktree.py`＋落点闸）；hook 命名/list 美观＝体验，非能力。**不囤**。
