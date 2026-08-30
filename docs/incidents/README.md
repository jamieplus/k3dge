# Incidents — 事故复盘知识库

本目录是 k3dge 的**事故复盘知识库（Incidents）**：`M0` 后已封板功能的回退（`REG`）与 `SEC/AST/CON/ENV` 四类事故落此。

- **用途**：把"哪坏了、为何坏、怎么修、证据在哪"固化成可追责、可复盘的 B-T-D 记录；`docs/branches/` 仅为 `check` 红后试错分支，不在此。
- **组织**：按 `INC-YYYYMMDD-<TYPE>-<slug>.md` 命名，`TYPE` 决定靶向 harness。
- **怎么写**：新增 / 修订 incident 的写法与机检契约见本页 `## 文档编撰规则` 段。
- **怎么读**：审计 / 修复前先读本目录全量，grep `INC-` 追全链路。

## 文档编撰规则 (Document Authoring Rules)

> **事实源**：`k3dge` 仅验"文件存在 / 注册一致"（`k3dge check`）；本文件载事故报告的机检契约，叙事质量由评审保证。

### 交付

`docs/incidents/INC-YYYYMMDD-<TYPE>-<slug>.md`，含 `背景(B)` / `触发(T)` / `处置(D)` 三段与证据链。

### 格式契约

- 文件名满足 `^INC-\d{8}-[A-Z]+-[\w-]+\.md$`，`TYPE` ∈ {`REG`,`SEC`,`AST`,`CON`,`ENV`}
- Frontmatter：`id` / `type` / `severity` / `status` / `root_cause_harness` / `action_task_ref`
- 文件名日期与文件内 `Date` 一致

### 章节

- `## 背景 (B)`：客观事实与影响面
- `## 触发 (T)`：复现条件 / 根因假设
- `## 处置 (D)`：修复动作与验证

### Constraints

L2 入场券须逐条确认：

- 文件名满足 `^INC-\d{8}-[A-Z]+-[\w-]+\.md$`
- 含 `## 背景` / `## 触发` / `## 处置` 三节（B-T-D 不可缺）
- 含至少一条可机器核验的证据链接（产物路径 / 命令输出 / 消费者引用）
- 文件名日期与文件内 `Date` 一致
- 双向回链：task / ADR / reviews 反向 `Incident:` / `Incidents:` 行

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
