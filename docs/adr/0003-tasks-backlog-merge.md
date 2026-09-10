---
Status: Accepted
# Append-only after Accepted. Revise via `Amended by` / `Superseded by` below — do
# NOT rewrite this decision's prose in place, and never reuse a number (see README).
Supersedes: -
Amended-by: -
Date: 2026-08-21
Deciders: Core Maintainer
Note: ① 人读化改写（按 AUTHORING「人读优先」：决策先行、一行一点、长条拆子项；不变量与编号不变）2026-09-10，经 Core Maintainer 本轮显式授权，依 `docs/adr/AUTHORING.md`；过闸口径 = manual fallback（实测 `command -v k3dit` 无输出，no live lens）。
---

# ADR-0003: tasks 与 backlog 合并为单一 tasks 目录

## 1. 上下文 (Context)

`docs/backlog/`（想法收件箱）与 `docs/tasks/`（工作登记处）并存一个周期后，backlog 零条目。

- 所有"先记下来"实际都落入 tasks。
- 例：0002 模块状态地图即"带触发条件的暂缓项"，与 backlog 定义重合。

更根本的：backlog 的 intake 闸门是"**Agent 给出方案 → 用户确认做不做**"。

- 入库条目从第一天起就是具体的：有方案、有切入点。
- 从未存在过"模糊想法"；模糊性只出现在召回端（"之前那个..."）。
- 召回端已由自包含可检索摘要解决。

因此 backlog 与 task 的区别只剩目录名，语义差异为零。

## 2. 决策 (Decision)

1. 合并为单一 `docs/tasks/`，删除空 backlog 目录。
2. 成熟度用条目内 **Status 字段**表达：`idea → deferred → in-progress → done`。
3. backlog 的核心纪律并入 `docs/tasks/AUTHORING.md` 与 `k3dge task list --json`，全部保留。
   - 自包含可检索摘要。
   - 开工扫盘。
   - 模糊召回匹配。
4. memo（弱相关闪念）与 branches（已证伪分支）保持独立，语义不重叠。

## 3. 产生后果 (Consequences)

- **正面**：
  - 单一扫描目标，修复了 lifecycle 第 1 步漏扫 tasks 的不一致。
  - 少一对需要辨析的成对物。
  - Status 流转比目录迁移更轻。
- **负面**：tasks 目录混合模糊想法与明确任务，靠 Status 区分——阅读时需多看一行。
