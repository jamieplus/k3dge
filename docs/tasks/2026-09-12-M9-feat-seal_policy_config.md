---
status: idea
milestone: M9
priority: P1
date: 2026-09-12
---

# 封版策略配置文件（何时可封 + 封板做什么）

- **Status**: idea
- **Milestone**: M9
- **Priority**: P1
- **可检索摘要**: 把"里程碑何时可封 + 封板具体做哪些事"从代码硬编码抽成声明式配置（拟 `.agent/seal.toml`），`seal` 只当执行器。
- **Date**: 2026-09-12

## Intent

把封版条件与动作外置为配置，`k3dge milestone seal` 读配置逐条执行；缺项即拒。

## 上下文/切入点

- 现状硬编码点：`engine/milestone.py` 的 `run_seal_flow`（审计闭环→enter prompt→align→seal）、`seal_milestone`（tasks 全 done / `_seal_review_gate` / `scan_unfilled_guides`）、`_seal_archive`（archive + `bump_milestone`）、`_write_closure_note`。
- 目标 schema（草案）：
  - `[preconditions]`：`tasks_all_done`、`audit_closed`、`adrs_accepted`（依赖 M9 `seal_adr_gate`）、`guides_filled`、`align_pass`、`report_format`。
  - `[actions]`：`full_matrix`、`archive_tasks`、`archive_reviews`、`version_bump`、`closure_note`、`prune_audit_lines`、`pointer_next`。
- 配置放 `.agent/`（与 `pipeline.toml` 同级）。

## 边界与拆分（规则 08）

- 事实归属：封版策略＝配置文件（数据）；执行器＝`engine/milestone.py`；判 ADR 内容对错归 k3dit（本项只查状态/指针）。
- 边界检查：配置只声明"条件名/动作名"，不含实现细节与表达式；executor 认识动作名，不让 config 知道内部状态机。
- 桩子先行：先落 schema + 把现有硬编码逐条搬过去（行为不变），再逐项替换实现引用。
