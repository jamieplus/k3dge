---
status: idea
milestone: M9
priority: P1
date: 2026-09-12
---

# 封版 ADR 硬闸（所有 ADR 须 Accepted 且落地，ADR 成事实源）

- **Status**: idea
- **Milestone**: M9
- **Priority**: P1
- **可检索摘要**: 封版加硬闸——范围内 ADR 必须 `Status: Accepted` 且决策已落地（带可解析的落地指针），使 ADR 成为事实源。
- **Date**: 2026-09-12

## Intent

让"决策文档"与"已实现的现实"在封板时对齐：ADR 不再是提案，而是已落地事实的单一源。

## 上下文/切入点

- 现状：`docs/adr/.schema.json` 允许 Draft/Proposed/Accepted/Deprecated/Rejected；`k3dge check` 只查结构/章节序，**不查状态、也不查落地**。当前多为 `Proposed`/`Draft`（如 0025/0026）。
- 拟加两道（seal 前置，或并入 `k3dge check` 的 seal 档）：
  - 闸1（状态）：范围内 ADR 不得为 `Draft/Proposed`；`Superseded/Deprecated` 须带 `Superseded by`/否决理由。
  - 闸2（落地）：每条 `Accepted` ADR 带落地指针（如 `Landed-by: docs/specs/<domain>/spec.md §x` / `src/…` / task id），且指针**可解析**（文件/节/id 存在）。
- 让 `k3dge_adr_index`（`analyze_adr_coverage`）出"未 Accepted / 未落地"事实，seal 据此拒。
- **不单列 ADR**（经 Core Maintainer 2026-09-11 否决"一条小决策占一个 ADR"）：本规则并入**「硬闸契约」**（gate 配置/spec，归属见 `2026-09-12-M9-refactor-gates_config_inventory`），作为其中一条 gate rule——契约里声明 `adr_all_accepted` + `adr_landed`，执行器按契约跑。

## 边界与拆分（规则 08）

- 事实归属：ADR 文档拥有 `Status`/`Landed-by`；闸归 engine（`audit_trigger`/seal 侧）做结构校验；"落地是否真成立"归 k3dit（语义）。
- 边界检查：闸不解析 ADR 决策语义（那是 k3dit）；只验状态枚举与指针可解析，不做第二套判定语言。
- 桩子先行：先落 `Landed-by` 字段 + 指针解析器（对少数 ADR 试点），再全量上闸 + 提升流程。
