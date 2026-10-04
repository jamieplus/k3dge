---
status: done
milestone: M11
priority: P1
date: 2026-09-20
---

# 审计票 idea 挡住 seal 唯一入口；collect 不关票；回收记录不算结案

- **可检索摘要**: `submit_audit` 建 `status: idea` 的审计票；`collect_audit` 只追加 `## 回收记录`、不 `task done`。seal 预审 `tasks_all_done` 因此进不去相位 2（本应自己跑审计）。`k3dge task done` 也不写结案段；`TASK_CLOSURE_MISSING` 不认「回收记录」标题。

## 已确认意图

ADR-0004 🅰1：`k3dge milestone seal` 是三相位唯一入口，相位 2 自己跑审计。现行闸把审计工单的票算进「未 done」，与唯一入口互斥。

## 证据（M10 真跑）

```
k3dge milestone seal --yes M10
⇒ Cannot seal … Tasks not done: ['2026-09-20-M10-audit-audit_job_1e408cbd4c78.md']
票 frontmatter status: idea（submit 建的）
collect 后只追加：
  ## 回收记录
  - 报告：…（待修 0 / 有意留 1 / 已修 11）
  - 席位：review；本 task 在报告回填闭环（待修=0）后由修复席位 `task done`
k3dge task done 后 Full Matrix：
  [GATE ERROR] TASK_CLOSURE_MISSING … 需 ## 结案 / ## 落地 / …（回收记录不在闭集）
test_evaluator.TestTaskGovernance.test_repo_tasks_conform 扫真仓，同一闸把 engine 测试打红
```

## 方案

```
① 审计工单票不算 seal 预审的「人待办」——要么 submit 不建 milestone 顶层票，
   要么 collect 待修=0 时进程关票并写认得出的结案段
② `TASK_CLOSURE_MISSING` 标题闭集纳入 `## 回收记录`，或 collect 改写 `## 结案`
③ `k3dge task done` 若正文没有结案类段，写一个最小结案桩（闸只验有没有，不验写得好）
④ 验收：全 done 工作票 + 在办棘轮单时，`seal --yes` 能进相位 2，而不是卡在 tasks_all_done
```

## 边界与拆分

- 事实归属：票生命周期归 `task_write`；seal 前置闸归 `seal.tasks_all_done`；工单态归 `audit_flow`。
- 边界检查：seal 闸只问「还有没有人待办的票」，不读 k3dit 内部 state。
- 桩子先行：临时仓 submit→collect 待修=0 → 预审 `unmet_seal_preconditions` 不含该审计票。

## 结案

- `work_pending` 只豁免账本 `ticket_task` 指针（同名模式的人开票仍挡 `tasks_all_done`）；collect 待修=0 写带报告指针的 `## 结案` 再 `mark_task_done`。`task done` **不**代写结案。
- 测试：`test_audit_job_ticket_is_not_work_pending`（账本有的豁免、同名假票仍 pending）。
