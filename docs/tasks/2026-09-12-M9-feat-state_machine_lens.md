---
status: done
milestone: M9
priority: P2
date: 2026-09-12
---

# 状态机转移图透镜：可达性/死状态/非法跃迁/闭包

- **Status**: done
- **Milestone**: M9
- **Priority**: P2
- **可检索摘要**: task 状态枚举 / milestone 生命周期 / rounds `submit→claim→complete→sign→collect` 都是现成图；按声明转移表查可达性/死状态/非法跃迁/转移闭包（大厅规则典）。
- **Date**: 2026-09-12

## Intent
状态机从"枚举存在性"升级到"边"：可达性/死状态/非法跃迁/闭包成为声明可比的事实。

## 上下文/切入点
- 来源：memo `docs/memo/archive/2026-09-05-graph-lens-for-audit-and-qa.md` §1.3/§6（本仓最富矿）。
- 现状：只验"在不在枚举"（k3dit Pass 4 + k3dge check），**不验边**；非法跃迁仅席判。
- 落点：大厅规则典（有转移表声明可比）+ `k3dge check`；"状态数虚多"→价值窗。
- 实现：自造 dict+BFS（声明小且固定，§7.1 自造豁免）。

## 边界与拆分
- 事实归属：可达/死状态/闭包＝确定性事实（k3dge）；"预留还是废弃"判读归价值窗；最小化裁量。
- 边界检查：**有声明转移表才检**；无声明不臆造边。
- 桩子先行：先为 task 状态机写声明转移表 + BFS，再逐机（milestone/rounds）扩充。

## 验收
- 不可达态 / 无出边非终态 / 未声明跃迁出事实；有声明才检；零依赖。

## 收尾（2026-09-13 已落）
- **立表（声明源）**：`engine/state_machine.py` 声明 task 状态机 `TASK_STATES` / `TASK_TRANSITIONS`（与 `docs/tasks/AUTHORING.md` 的 Status 枚举、`mark_task_done` 的合法流转一致）。
- **事实**：`reachable` / `dead_states` / `unreachable` / `undeclared_targets` / `summary`（纯 stdlib，零依赖）。
- **接入**：`k3dge status --json` / MCP `k3dge_status` 增 `state_machine`（可达/死状态/未声明目标）——**观测不判定**，不进 `check`。
- 测试 `test_state_machine.py`（默认表 + 自造坏表）。304 passed；check 绿。
- 注：本仓无现成里程碑声明转移表；本票按"先立表"先落 **task 状态机**（最简、事实现成）。里程碑生命周期表（`overview.md §6`）待后续按同法立。
