---
status: done
milestone: M7
priority: P1
date: 2026-09-02
---

# ADR-0006 就地修订为入向/出向双向契约 + AUTHORING 例外条款

- **Status**: done
- **Milestone**: M7
- **Priority**: P1
- **可检索摘要**: ADR-0006 只定义了 MCP 的入向（外部 harness 注入 k3dge），出向（k3dge 连 peers）无位置；本任务把它改成双向契约，并在 `docs/adr/AUTHORING.md` 加"就地修订需显式人工授权"例外条款
- **Date**: 2026-09-02

## 已确认意图

- k3dge 是**一致性自治系统**；k3dit / k3lity / k3che 是 peers：**功能上从属**（由 k3dge 使唤做 audit / quality / cache），**地位上对等**（各自独立、各自发 MCP server、可被别的 harness 使用）。
- 现状与此意图差一件**部件**：k3dge 侧没有 MCP 客户端（`src/k3dge/engine/pipeline_runner.py:152 _run_mcp_best_effort()` 只做 `shutil.which("k3dit")` 探针），所以"由 k3dge 使唤"只存在于注释里，实际调 peer 的是 agent，调不到就由 agent 代笔。
- 编排失败语义（`ADR-0006` §2.4 定稿口径）：`manual` 是合法档位，**不设逐次放行开关**（曾考虑的 `--allow-manual-audit` 不采纳）；但每次降级必须显式 `WARN[DOWNGRADE]` + 落 `logs/k3dge.log` + 写进报告 `透镜来源`，并且**出总结时必须高亮**哪几项是降级产物。`escalated` 只保留一个含义：审计链整体落到 `manual` 且人未确认它作数时，`seal` 不放行。
- 治理缺口：未跑通的流程其 ADR `Accepted` 是过早的；为防文档膨胀，允许**就地替换**正文，但必须显式人工授权 + 文件内留痕。本任务把这条例外写进 AUTHORING。

## 上下文/切入点

- 就地修订对象：`docs/adr/0006-mcp-foreign-harness-injection.md`（`Status` 改回 `Draft`，作废句在正文点名）。
- 例外条款**只写 `docs/adr/AUTHORING.md`**，不写 `docs/adr/README.md`：该特权敏感，不留多处入口。
- 机验耦合：`src/k3dge/engine/pairs.py:48` 要求 `templates/assets/adr/AUTHORING.md` 与 `docs/adr/AUTHORING.md` 逐字节相同（漏改即 `check` 红）。
- `docs/adr/.schema.json` 的 `Status` 枚举含 `Draft`，不新增取值。

## 验收

- `k3dge check` 绿（含 PAIRS 模板同构、`ADR_SECTION_ORDER`、`ADR_FRONTMATTER_MISSING`）。
- 0006 正文含：方向性不变量（入向/出向互不借道）、`check` 纯静态硬闸（不调 agent/透镜/peer 验证）、endpoint 唯一事实源 = `.mcp.json`、peer 双传输、跨仓授权（§2.3.7）、动作级调用（§2.3.8）、§2.4 失败语义（不设逐次放行开关；四处不可静默 + 总结高亮；`escalated` 仅剩「同席/manual 产物未经人确认则 `seal` 不放行」一义）、作废句点名、`Note:` 留痕（过闸口径 = `manual` fallback）。
- AUTHORING 例外条款三条条件齐（授权 / 留痕 / 点名作废句），且 README 未被写入该特权。
- 派生任务已建，未被本轮实现的项有 task 承载（见 `Related`）。

## Related

- 派生：`2026-09-02-M7-feat-peer_outbound_mcp_client.md`（真客户端 + endpoint 形状）
- 派生：`2026-09-02-M7-docs-align_rules_overview_outbound.md`（rules/07 + overview 两张图按 §2.4 重写）
- 派生：`2026-09-02-M7-feat-check_gate_by_doc_status.md`（按文档 `Status` 区分过闸口径，本轮不迭代）
- 派生：`2026-09-02-M7-feat-k3che_cli_transport.md`（peer 双传输不变量落地）
- 跨仓前置：`../k3che/docs/reviews/2026-09-01-peer-bringup.md` K3C-BRING-02（`mcp` SDK 2.x 删除 `mcp.server.fastmcp` 的双路径修法，吸收给 k3dit / k3lity / k3dge）
