---
status: deferred
milestone: M7
priority: P2
date: 2026-09-02
---

# check 按文档 Status（Draft/Accepted）区分过闸口径

- **Status**: deferred
- **Milestone**: M7
- **Priority**: P2
- **可检索摘要**: 未跑通流程的 ADR 只能按 `manual` fallback 过闸，其 `Status` 却与已跑通的决策同等计分；`check`（及审计闸）应按文档 `Status` 区分严格度 —— **本轮不迭代，仅登记**
- **Date**: 2026-09-02

## 已确认意图

`Draft` / `Proposed` 决策不该与 `Accepted` 吃同一套硬闸；反之 `Accepted` 也不该在正文自称已被真透镜复审。当前目的是把流程调通，`Accepted` 过早是事实而非错误，所以需要的是**区分**而不是放松。

## 上下文/切入点

- 现状 `check` 对 ADR 只验结构：`docs/adr/.schema.json`（`filename`/`h1`/`sections`/`section_order`/`frontmatter.Status` 枚举），**不读 `Status` 的语义**。
- 本次实践样本：`docs/adr/0006-mcp-foreign-harness-injection.md` 被就地修订并置 `Draft`，其 `Deciders:` 行携带"过闸口径 = `manual` fallback"字样 —— 这正是可被机验的结构化事实，但目前无人消费。
- 边界约束（不得破）：`ADR-0006` §2.3 保留「`check` 不连 MCP、不跑 CLI（T-01）」。所以区分只能落在**文档静态事实**上（`Status` + 过闸口径标记），不能变成"check 去问 peer 有没有审过"。
- 关联既有决策：`ADR-0012`（证据链三环：产物/消费者/到达）、`ADR-0021`（doc-audit 非阻断、`[NEXT] doc_audit` 在 check 之后）。

## 验收

- 明确一条机验规则（草拟）：`Status: Accepted` 的 ADR 若 `Deciders:` 含 `manual` fallback 而无后续真透镜复审记录 → `check` 给 WARN（是否阻断由该轮决定）；`Status: Draft` 则不要求。
- 规则写进 `docs/adr/AUTHORING.md`（特权/口径类只此一处，见 `ADR-0006` 就地修订条款的同一理由）与 `docs/adr/.schema.json` + 其模板副本（`engine/pairs.py` 逐字节耦合）。
- 至少一条单测覆盖 Draft/Accepted 两分支。

## 边界与拆分

- 事实归属：文档 `Status`/`Note:` 是文档事实；闸口径是引擎事实；"哪个决策过早"是人的判断，不进机器。
- 边界检查：闸只读 `Status` 与 `Note:` 的结构，不读决策内容（`ADR-0012`：机器不判真伪）。
- 桩子先行：先造 fixture（一份 Draft + 一份 Accepted 的 ADR）跑通两分支断言，再接入闸。

## Related

- `docs/tasks/2026-09-02-M7-docs-adr0006_inplace_revise.done.md`（本项由该次就地修订暴露）
