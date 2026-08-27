# Incidents — 事故复盘知识库

`M0` 后已封板功能的回退（`REG`）与 `SEC/AST/CON/ENV` 四类事故落此，`docs/branches/` 仅为试错分支（`check` 红后 `stash` 前）。

## 命名

`INC-YYYYMMDD-<TYPE>-<slug>.md`（`TYPE` ∈ {`REG`,`SEC`,`AST`,`CON`,`ENV`}），`TYPE` 决定靶向 `harness`：`REG→k3lity`/`SEC→k3dit`/`AST→k3dge`/`CON→k3dit`/`ENV→k3cache`。

## 报告头（Frontmatter）

```yaml
---
id: INC-20260826-REG-01
type: REG
severity: P0
target_milestone: M1
status: closed
root_cause_harness: k3dge
action_task_ref: docs/tasks/2026-08-26-M3-audit-P4_01_M0_M1.done.md
---
```

## 双向回链

* `incidents/INC-*.md: action_task_ref` → `docs/tasks/*`
* `docs/tasks/*incident*.md: Incident: INC-...` → `incidents/`
* `docs/reviews/*.md` 增 `Incident: INC-...` 行
* `ADR` 增 `Incidents: INC-...` 行
* `incidents/README.md` 聚合 `MTTR` 时 `grep -r INC-` 全链路可追

## 流程

`k3lity verify` 证伪 → `incidents/INC-*.md` 建档 → `P0` 任务挂起 `M` 封板 → 修复 → `k3lity verify` 转绿 → `k3cache` 沉淀反模式
