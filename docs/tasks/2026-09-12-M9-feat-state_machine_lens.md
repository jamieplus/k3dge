---
status: idea
milestone: M9
priority: P2
date: 2026-09-12
---

# 状态机转移图透镜：可达性/死状态/非法跃迁/闭包

- **Status**: idea
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
