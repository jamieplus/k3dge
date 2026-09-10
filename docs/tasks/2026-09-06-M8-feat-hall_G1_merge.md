---
status: idea
milestone: M8
priority: P1
date: 2026-09-06
---

# G1: 审计模块合并 + 接口冻结（一本账）

- **Status**: idea
- **Milestone**: M8
- **Priority**: P1
- **可检索摘要**: audit 为主、quality 编排去掉并入 audit：k3dit 为底，k3lity 的编排面（jobs/rounds/seats/serve）退役、扫描能力（quality/deslop/harness）作为工具面并入；接口=原 audit 面（mcp 工具名/cli 子命令保留）；k3dge 消费侧不动是迁移红线
- **Date**: 2026-09-06

## Intent

合并方向单向：audit（k3dit）是主体，quality（k3lity）去编排、留扫描。G2 起 Hall 内核只对一本账说话。

## Notes

- 合并范围：audit 侧 jobs/rounds/report/mcp/cli/seats 保留；k3lity 侧 jobs/rounds/seats/serve（编排）退役，quality/deslop/harness（扫描）并入为工具面。
- 接口冻结清单：`k3dit_run_audit_flow`、`k3dit_audit_{submit,claim,complete,collect}`、claim-round/complete-round/sign-report、12 列报告格式。k3dge 侧回归测试全绿是本 task 的 done 条件。
- 中间态：G1–G5 期间 k3lity 仓只读冻结（不删），扫描代码搬入审计模块新 `tools/` 目录；k3lity 仓废留归档放 G6。
- k3che 调用点（hints）保留：独立 peer 照常消费，不在本 task 动。

## 边界与拆分（feat 类必填；规则 08）

- 事实归属：账本 schema 属审计模块；消费侧调用形状属 k3dge（只读，不改）。
- 边界检查：本 task 不改 k3dge 任何调用点（红线）；审计模块内部重排不外溢到契约。
- 桩子先行：先合账本 schema + 跑通 k3dge 回归（对方缺席可测：dummy peer 应答）。

## Related

- `docs/adr/0025-hall-harness-topology.md`（§2.2 合并语义、§2.4 并的边界；本 task 是 G 链起点，后续 G2–G8 见各 task）
- `docs/memo/2026-09-05-hall-pattern-discussion.md`（推演账与废案表）
