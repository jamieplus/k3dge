---
status: idea
milestone: M7
priority: P3
date: 2026-09-02
---

# doc-audit: 文档作者合规审计（本轮 docs 改动 26 处）

- **Status**: idea
- **Milestone**: M7
- **Priority**: P3
- **可检索摘要**: 2026-09-02 就地修订 `ADR-0006`（入向/出向 + 失败语义）、`docs/adr/AUTHORING.md` 合成 Record lifecycle 一条、`Note:` 字段横展开 22 份 ADR、新增 10 条 M7 task、mcp-bridge guide 加出向与入向现状两节 —— 触发 `k3dge doc-audit`（非阻断）；本 task 承载这批文档的作者合规核对
- **Date**: 2026-09-02

## 已确认意图

`docs/**` 变更后由 `k3dge doc-audit` 出报告并建带 Milestone 的 task（`ADR-0021`，非阻断；本轮不改文档正文）。**本 task 只登记范围与切入点，不含结论**——结论须由 k3dit 透镜或人工出，见「谁来出」。

## 上下文/切入点

待核文件（本轮新增/修改）：

- `docs/adr/0006-mcp-foreign-harness-injection.md` —— **就地修订**（`Status: Accepted` → `Draft`）：§2.3 方向性不变量（含新增 7 跨仓授权、8 动作级调用）、§2.4 失败语义（撤 `--allow-manual-audit`）、§2.5 非目标；作废的旧句在 §2.3.2 / §2.4 点名
- `docs/adr/AUTHORING.md` + `src/k3dge/templates/assets/adr/AUTHORING.md` —— 生命周期四条**合并为一条 `Record lifecycle`**（三行表 + `Note:` 格式块 + 「动用例外必须填 `Note:`」）；两份逐字节同构（实测 `diff` 为空）
- `docs/adr/_template.md` + 模板副本 + 22 份既存 ADR —— 横展开 `Note: -`（元数据补齐，未逐条留痕）
- `docs/guides/mcp-bridge.md` —— 新增「出向：k3dge 作为客户端」与「入向现状：server 起不来（已搁置）」两节
- `docs/tasks/2026-09-02-M7-*.md` —— 本轮共 11 份（2 份已 done）
- 代码面（本仓）：`engine/pipeline_runner.py`（出向客户端）、`engine/milestone.py` + `cli/status.py`（结构件名单单一事实源）、`cli/main.py`（`mcp probe` + `cmd_status` NameError）、`pyproject.toml`（`mcp>=1.0,<3`）
- memo 层清理（2026-09-03）：`docs/memo/archive/2026-08-21-code-quality-discussion.md`、`docs/memo/archive/2026-08-24-docs-self-reflective-gate-vs-audit.md` 两份**新归档且首次带 `Superseded-by`**（本仓合规归档第一例）；就地勘误 `2026-08-27-h8m2k-…`（两句过期 + Capability Gating 缺口）、`2026-08-21-deferred-standards.md`（4 项已落地补落点）；`2026-09-02-plugins-main-absorption-eval.md` 4 行状态 🎯→✅ 并附文件:行 + 更正记录；`2026-09-02-peer-wiring-…` §1 折成指针表（消双源）；`docs/memo/archive/2026-08-24-audit-harness-independence.md:99` 一条裸引改全路径
- `docs/memo/2026-09-02-peer-wiring-and-seat-options.md` —— 选项账（已定 / 待研究 / 废案 / 现状快照）。核点：正文是否把对话过程冒充实测；§1 十条「已定」与 ADR·task 是否逐条对得上；§3 废案理由是否可核；§2 是否残留已被 §1 判定过的伪选项
- 跨仓留痕（不在本仓闸内）：`../k3dit`、`../k3lity`、`../k3che` 各 1 份本轮 task + `../k3dit/docs/tasks/2026-09-02-feat-audit_flow_tool.md`

核对要点（供透镜参考，非结论）：

1. `ADR-0006` 是否仍满足 `docs/adr/.schema.json`（三段标题、段号递增、`Status` 取值）与 `AUTHORING.md` 的 Context/Decision/Consequences 文体（不写过程、不写"某人说"）。
2. §2.3.2 对旧句的"作用域收窄"是否构成与 §2 其他条目的隐性冲突（AUTHORING：k3dit 可标两条 Decision 互相否定）。
3. 新 task 是否自包含（`ADR-0012` 三环：产物/消费者/到达）、是否残留仅凭对话才能理解的指代。
4. 本文件「谁来出」那条是否被当成结论引用。

## 谁来出（不得自审自发过闸）

**这批治理文件目前没人审**——`AUTHORING.md` / `README.md` / `ADR-0006` 正是"谁能改规则"本身，最不该由改它们的席位自证合规。审计能力本轮已具备，只差一步：

```
$ k3dge mcp probe                      →  k3dit ALIVE tools=['k3dit_check_report','k3dit_run_audit','k3dit_run_doc_audit']
$ run_action("k3dit.actions.audit")    →  WARN[DOWNGRADE] action=k3dit.actions.audit mcp->manual
                                          reason=Error executing tool k3dit_run_audit: 2 validation errors … pass_number Field required
```

（本节写于补动作级入口之前；那条卡点同日已解：`../k3dit/docs/tasks/2026-09-02-feat-audit_flow_tool.md` 标 done，`k3dit.actions.audit` 实测 `provider=mcp lens_count=5 downgrades=0`。）三条路径，按独立性排序：

- **(b) 外部席位真审（推荐，现在就能做）**：你在装了 k3dit MCP 的宿主里跑 doc-audit 透镜，报告落 `docs/reviews/`，本仓只核对。
- **(c) 整轮驱动（现已可行）**：`k3dge milestone audit M7` —— 动作级入口已到位，链上 `provider=mcp`、`downgrades` 为空；报告执笔席位仍需分开（谁写报告 = 不是改代码的那个席位）。
- **(a) 我照真透镜指令执笔**：可以调 `k3dit_run_doc_audit` 取指令、按指令写报告，但 `审计人` 只能记「agent 执笔 + 指令来自 k3dit」、`透镜来源` 记 `mcp(instruction)+agent(drafting)`——**不构成独立审计**，`seal` 前仍需 (b)/(c) 复判。

我不自选 (a)。本轮 ADR 的 `Note:` 已如实写 `过闸口径 = manual fallback`。

## Related

- 决策源：`docs/tasks/2026-09-02-M7-docs-adr0006_inplace_revise.done.md`
- 前置缺陷：`docs/tasks/2026-09-02-M7-fix-k3dge_mcp2_resource_strict.md`（入向 server 起不来，已搁置）
- 卡点：`../k3dit/docs/tasks/2026-09-02-feat-audit_flow_tool.md`（动作级 audit 入口缺失）
- 人读面尚未同步：`docs/tasks/2026-09-02-M7-docs-align_rules_overview_outbound.md`（rules/07 + overview 两张图仍写着 agent 编排）

<!-- k3che-hints -->
## 相关文档提示（k3che · 服务性前路由，非判定；由审计席位取舍）

- `docs/tasks/2026-09-02-M7-fix-k3che_indexes_authoring_files.done.md` — k3che 检索索引把 docs/*/AUTHORING.md 当语料
- `docs/tasks/2026-09-02-M7-audit-doc_audit_adr_4.md` — doc-audit: 文档作者合规审计（本轮 docs 改动 26 处）
- `docs/branches/2026-08-27-k8d3e-a78-repro.md` — 分支：k8d3e-a78 5-Pass 穿透 01-05 缺陷 B-T-D 复现（镜像）
<!-- /k3che-hints -->
