---
Status: Accepted
# Append-only after Accepted. Revise via `Amended by` / `Superseded by` below — do
# NOT rewrite this decision's prose in place, and never reuse a number (see README).
Supersedes: -
Amended-by: -
Landed-by: src/k3dge/engine/nextstep.py
Date: 2026-08-24
Deciders: Core Maintainer
Note: ①-⑦ 修订痕迹见 git 历史（2026-09-10 至 2026-09-12：里程碑触发对齐 ADR-0004、正交去重/收尾、去 changelog 化、人读化改写、增补 §2 渐进披露并 Accepted→Proposed→Accepted）；新格式自 🅰1 起生效（`Amended-by`），迁移口径同 ADR-0006。
---

# ADR-0008: 触发式文档维护与先读已敲定设计

> **Related**: ADR-0004（里程碑生命周期）、ADR-0010（rules 切片）

## 1. 上下文 (Context)

- k3dge 的意图不是替用户想「做什么」，而是：用户说出任务后，Agent 在**完成该任务的同一轮**自动维护契约、spec、ADR、milestone，使下一会话仍一致。
- 口令驱动的收件（tasks/memo）可以等用户开口；align/seal 若也等「请封板」，就把维护时机推回用户。
- 架构决策已经落在 ADR（从 0001 起）；后到的 Agent 若先发明细则再让用户「确认」，等于逼用户重新设计一遍。

## 2. 决策 (Decision)

- **触发式维护**：用户只陈述工作意图；维护文档的**时机**以 `AGENTS.md §12` 事件表为准。
  - 禁止等「请写 ADR / 该 sync / 该封板」。
  - 口令仍保留的只有：tasks 收件（尚未发生「做完」）、memo 收件（尚未成事）。
- **里程碑**：触发条件与审计/封板时序见 ADR-0004 §2.1.2/§2.1.4；闸条件见 ADR-0004 §2.1.3。
  - `seal` 失败典型原因是 guide-stub：应先填 guide 再 seal，而不是停下来问「要不要封板」。
- **MCP**：不自动改其它 harness 的配置；用户要求「帮我配」时，只执行 `docs/guides/mcp-bridge.md` 固定剧本。
- **先读后说**：动手或加规则前，先读 `docs/adr/`（尤其 0001–0004）和 `docs/reviews/LEFTOVERS.md`。
  - 那是事实源，不是聊天纪要。
- **粗意图映射到已有决策**：用户一句话应对到已有 ADR/AGENTS 条款；对得上就执行，对不上就问一句。
  - **不要**先写一套新规程再让用户改；不替用户细化设计（门禁粒度、域怎么切、文档谁是判据已定过）。
  - 新 Agent 只补执行缺口（漏触发、漏 sync），不升级成另一套方法论。
- **k3dge 原意（0001）**：Soft Prompting 不够，所以用目录契约 + 哈希 + git 硬闸，让 Agent 在完成**用户说的任务**时保持代码与 spec 一致。
  - 用户负责说做什么；Agent 负责不漂。
- **渐进披露（next-hook 引导）**：与"触发"同源——状态机每条边经 `[NEXT]` 只推**最小下一步 + 指针**（doc id / ADR 节 / 命令），纵深**按需拉取**，不把全文灌进上下文。
  - 默认输出摘要、全量藏 `--json`/`--deep`；`AGENTS.md` 微核与命令 stdout 守预算（**数值归硬闸契约，不进本 ADR**）。
  - 静态"地图"仍要（`AGENTS.md` 路由公式，ADR-0018 §2.3）：防"藏太深找不到"。

## 3. 产生后果 (Consequences)

- 漏写 ADR/漏 sync 是违反协议，不是「用户没叫」。
- 渐进披露的代价：可发现性下降、往返增多；靠「钩子点名具体 doc + 确定性硬闸兜错」缓解。
  - 违反本 ADR 的典型样子：用户说「文档该自动维护」，Agent 立刻发明一张触发表让用户逐条认。
  - 正确做法是映射到 `AGENTS.md §12` 与各 `docs/<type>/AUTHORING.md`；缺的只问「是不是就是这些已经写过的时机」。
- 用户在场时仍以用户当轮口令为准；不在场时以 ADR 为准，不靠聊天记忆。
