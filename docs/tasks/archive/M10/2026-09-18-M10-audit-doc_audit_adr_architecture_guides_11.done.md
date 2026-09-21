---
status: done
milestone: M10
priority: P3
date: 2026-09-18
report: docs/reviews/2026-09-14-M10-audit.md
---

# doc-audit: 文档作者合规审计（adr, architecture, guides 等 11 处）

## 已确认意图
doc-audit: 文档作者合规审计（adr, architecture, guides 等 11 处）

## 可检索摘要
doc-audit: 文档作者合规审计（adr, architecture, guides 等 11 处）

## 上下文/切入点
本次触发 doc-audit 的受管文档（11 份），逐份对照 `docs/<type>/AUTHORING.md` 检查作者合规：

- `docs/adr/0006-mcp-foreign-harness-injection.md`
- `docs/adr/0026-projection-contract.md`
- `docs/architecture/encyclopedia.md`
- `docs/guides/mcp-bridge.md`
- `docs/memo/2026-09-13-agent-dev-tools-absorption-eval.md`
- `docs/memo/2026-09-14-gap-trap-absorption.md`
- `docs/protocols/audit_default.md`
- `docs/protocols/peer_contract.md`
- `docs/specs/cli/spec.md`
- `docs/specs/engine/spec.md`
- `docs/specs/templates/spec.md`

<!-- k3che-hints -->
## 相关文档提示（k3che · 服务性前路由，非判定；由审计席位取舍）

- `docs/tasks/2026-09-18-M10-audit-doc_audit_adr_architecture_guides_11.md` — doc-audit: 文档作者合规审计（adr, architecture, guides 等 11 处）
- `docs/guides/mcp-bridge.md` — MCP Bridge — 零漂移门禁桥接器
- `docs/tasks/archive/M7/2026-09-02-M7-feat-peer_outbound_mcp_client.done.md` — k3dge 出向 MCP 客户端与 endpoint 唯一事实源
<!-- /k3che-hints -->

## 关闭理由（2026-09-19）：本票所依附的机制已退休

ADR-0022 §2.2 经 🅰1 修订（commit `f749e27`）：doc 合规不再走"路由透镜 → 产 12 列报告 → 建里程碑票"，改为**提交时硬闸 + 新建首次排查 + seal 轮规约化**。本票是旧机制的产物，故关闭，不转为实际工作。

关闭依据（实测，非"过期"敷衍）：

1. **本票从建出来就无法执行**：`run_doc_audit` 丢弃 `run_action` 的返回值 ⇒ k3dit 的 Doc Audit 透镜说明、报告落点约定、12 列脚手架全部蒸发（`_run_mcp` 也不往 io 打）。票面只有 11 个文件名，没有透镜、没有判据、没有落点。
2. **票绑错了报告**：`report:` 指向 `docs/reviews/2026-09-14-M10-audit.md`（里程碑**代码**审计报告，待修=0）⇒ 关票不需要任何实际工作。这正是 ADR-0022 🅰1.4 把耐久从"票"改成"闸"的实证。
3. **同类前科**：`docs/tasks/2026-09-14-M10-audit-doc_audit_adr_guides_memo_4.done.md` 自述「过期空壳：触发时的 4 个文件未记录（建票时只写标题），无可执行内容」。同一机制两次产出不可执行的票。

那 11 份文档的作者合规**没有因此漏掉**，去处如下：

| 层 | 谁管 | 状态 |
| --- | --- | --- |
| 结构（frontmatter/章节/名实一致/悬空引用/markdown 完整性） | `docs/<type>/.schema.json` + pre-commit 三层闸 | 已生效；本轮这 11 份都过了闸（含两次真拦：`DANGLING_ADR_REF` 拦下裸引退役号、`DANGLING_FOOTNOTE` 拦下 code span 字面量误判） |
| 新建是否该建（冲突/覆盖/子项） | `DOC_NEW_UNSCREENED` 首次排查闸（`a04242c`） | 已生效；本轮新建的 ADR-0026 若在此闸之后建，会被要求先排查 |
| 语义质量（Context 是否写成 timeline / Decision 是否只写不变量 / 有无过程叙述） | 里程碑审计的外部透镜（seal 轮） | 归 M10 封板轮的审计；不进自动修（ADR-0022 §2.2 🅰1.3） |
| 编号/引用退役 | `ADR_NUMBER_REUSE` / `ADR_REF_RETIRED`（`48b3301`） | 已生效 |

⇒ 本票的"11 处待审"已被上面四层接管，无遗留工作项。
