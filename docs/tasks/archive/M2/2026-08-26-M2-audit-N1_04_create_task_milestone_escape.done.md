# create_task 未校验 milestone 致路径逃逸

- **Status**: done
- **Milestone**: M2
- **Priority**: P1
- **Date**: 2026-08-26

## 已确认意图
[N1-04] create_task_milestone_escape — `engine/milestone.py:194-201`

## 可检索摘要
create_task 未校验 milestone 致路径逃逸 位于 2026-08-26-M2-audit-N1_04_create_task_milestone_escape.done.md，需修复后经 k3dge check --with-tests 与 k3dit 5-Pass 审计验证，确保自包含且可回溯。

## 上下文/切入点
触发于 k3dit 5-Pass 审计，切入点 待修，关联 2026-08-26-M2-audit-N1_04_create_task_milestone_escape.done.md
