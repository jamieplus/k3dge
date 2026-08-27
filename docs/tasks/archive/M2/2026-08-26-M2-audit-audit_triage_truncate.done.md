# 审计转任务截断致任务失自包含

- **Status**: done
- **Milestone**: M2
- **Priority**: P1
- **Date**: 2026-08-26

## 已确认意图
k3dge audit triage 的批量脚本按 slug[:30] 截断致 M2 的 13 条审计任务失自包含，违 AGENTS.md §10

## 可检索摘要
k3dge 的 audit triage 脚本（cli/main.py:127）在 M1→M2 时按 9 列表行 slug 截 30 字生成任务，导致 13 条 M2 审计任务的 可检索摘要 与上下文仅复读标题，失自包含；M1 的 14 条人读任务为对照

## 上下文/切入点
触发于 M2 的 k3dit 审计后 triage，切入点 src/k3dge/cli/main.py 的 audit triage 路径与 docs/tasks/2026-08-26-M2-audit-*.md
