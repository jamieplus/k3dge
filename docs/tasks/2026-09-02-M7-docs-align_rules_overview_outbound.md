---
status: idea
milestone: M7
priority: P1
date: 2026-09-02
---

# rules/07 与 overview 对齐 ADR-0006 出向编排与 downgrade 表述

- **Status**: idea
- **Milestone**: M7
- **Priority**: P1
- **可检索摘要**: `overview.md` 把 agent 画成调 peer 的编排者、`rules/07` 的角色流同调，与 `ADR-0006` §2.3/§2.4（k3dge 调 peer、失败即 escalated 且显式表述 downgrade）冲突，需同步
- **Date**: 2026-09-02

## 已确认意图

编排者只有一个：k3dge。agent 使唤 k3dge，k3dge 使唤 peers。任何降级必须被**显式表述**为 downgrade，不许静默。

## 上下文/切入点

- 冲突点 1：`docs/architecture/overview.md:80-88`（C4：`System(agent, ..., "编排者：读 pipeline，调 k3dge 与外部 harness 的 MCP")`）与 `:126-127`（sequence：`Agent->>Audit: k3dit.actions.audit`）——现主张 agent 编排。
- 冲突点 2：`.agent/rules/07-audit.md:6` 角色流写成「审计角色调 `peers.k3dit.actions.audit`」；`:9` 已有 `WARN[HARNESS FALLBACK]` + 报告 `透镜来源` 注明 `manual` vs `k3dit` 的要求，但**没有"降级须表达为 downgrade 并计入过闸口径"**这一层。
- 权威源：`ADR-0006` §2.3（方向性不变量）、§2.4（失败语义 = escalated + `WARN[DOWNGRADE]`）。
- 机验耦合：`.agent/rules/07-audit.md` 与 `src/k3dge/templates/assets/rules/07-audit.md` 由 `engine/pairs.py` 逐字节比对，必须同改；`docs/architecture/overview.md` 无模板副本。
- 同时需校订：`.agent/pipeline.toml` 头部注释与 `src/k3dge/templates/assets/pipeline.toml.template`（PAIRS 耦合，注释里"EXECUTION MODEL"要与 §2.4 一致，且 `[peers.k3che]` 只有 `mcp→skip`）。

## 验收

- overview 两张图与 rules/07 的角色流：调 peer 的主语是 k3dge；agent 的动词只剩"调 k3dge / 修 / 收摊"。
- 任何 fallback 路径输出含 `WARN[DOWNGRADE]` 与其后果（哪一级判定从"进程外证据"降为"自证"），报告 `透镜来源` 必须携带该字样；**agent 出总结时同样必须高亮降级项**（`ADR-0006` §2.4.1 第四项），rules/07 要把它写成角色义务而不是一句提示。
- 改完 `k3dge check` 绿（PAIRS 全等）。

## Related

- `docs/tasks/2026-09-02-M7-feat-peer_outbound_mcp_client.md`（实现主体；本任务是其人读面）
