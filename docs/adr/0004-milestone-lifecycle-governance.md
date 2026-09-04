---
Status: Accepted
# Append-only after Accepted. Revise via `Amended by` / `Superseded by` below — do
# NOT rewrite this decision's prose in place, and never reuse a number (see README).
Supersedes: -
Amended-by: -
Date: 2026-08-23
Deciders: Core Maintainer
Note: -
---

# ADR-0004: 里程碑生命周期治理（Milestone Lifecycle Governance）

## 1. 上下文 (Context)
`k3dge` 初始设计覆盖微观门禁（`k3dge check` 的 L0/L1 结构与契约校验）。随着
项目进入多阶段交付，出现两类新需求：(1) 按里程碑验收目标是否达成；(2) 防止
长周期开发下 `docs/tasks/` 上下文膨胀导致 Agent 注意力衰减。需一套轻量、
确定性的里程碑状态机与物理归档机制。

## 2. 决策 (Decision)

### 2.1 目标对齐优先、拒绝常规大重构
采用四步里程碑治理：`规划与开发 → 目标对齐与验收 (k3dge milestone align) →
按需重构（准入清单卡控）→ 上下文压缩封板 (k3dge milestone seal)`。

* **Micro Gate**（日常提交）：`L0/L1` 快速阻断（`k3dge check`）。`k3dge check --with-tests` 是 **selective L2**（只跑 git 触及域的矩阵测试），不是 Full Matrix。
* **Macro Gate**（里程碑对齐）：`k3dge milestone align` 对 `manifest.domains` 做 **Full Matrix** 全域结构 + 契约 + 矩阵测试。
* **重构准入**：仅当命中 `C1 扩展硬阻塞 / C2 坏味道严重超标 / C3 契约漂移未愈`
  时才允许定向微调；否则严禁大重构。

### 2.1.1 修正（2026-08-24）
原稿把 Macro Gate 写成「`k3dge check --with-tests` 的全量触发」。实现上 Full Matrix 只在 `milestone align`；`--with-tests` 始终是增量域。以本节现稿为准，勿按旧句实现。

### 2.1.2 触发（Agent，无需用户提醒）
某 `Milestone` 字段下，`docs/tasks/` 顶层条目全部 `Status: done` → 当轮 `k3dge milestone align <id>`（Full Matrix，**无人问**）。align 通过**不等于可封**：下一步是**建议审计**（见 §2.1.4 两问拆分），不是建议封板。

### 2.1.3 封板闸机（2026-09-01）
`seal` 机器闸是：对应里程碑的 reviews 文件含 `align-pass`、不含 `align-stub`、正文列出该里程碑全部任务、`docs/guides/` 无 `guide-stub`。不读 `docs/reviews/SUMMARY.md`（禁止手维护类型索引，ADR-0018）。有意留只在 `docs/reviews/LEFTOVERS.md`。

### 2.1.4 两问拆分：审计是界限，封板只是收摊（2026-09-01）
原 §2.1.2 的 `HUMAN_CHECKPOINT`（`y` 审计 / `N`·60s 跳审计去 `seal`）把"先问封板、封板里再强制审计"做成一个剧本，但**封板没有尺子**——全 done、硬闸绿、甚至零 task 都能被说成"可封"，没有"结束里程碑最好的那一刻"。封板本身只是归档+版本+指针，不构成界限。真正的界限是**审计环收口**（12 列、待修=0、有意留进表、Full Matrix 过）。那之后问封不封，是在问"要不要压缩上下文收摊"，不是在猜该不该结束。改为两问：

- **问题一·要不要审（可量化触发，§2.1.5）**：`check`(绿)/`task done`/`align`/`status` 命中定量信号 → `[NEXT] audit_suggested` + reasons；人只答要不要审，不猜"是不是该结束"。答是 → `k3dge milestone audit <id>` 走必审→待修>0 问 agent 修(倒计时默认修)→重审；`>3` 次未闭环 → `escalated` 转人工。
- **问题二·要不要封（仅审计闭环后唯一一次）**：`待修=0` 且有报告 → `[NEXT] seal_ready`；`k3dge milestone seal <id>` 才问"封板？(y/N，无倒计时)"。未审计先调 → `audit_needed` 指回 audit。答是 → align→**归档+版本+指针**，并写 `*-closure.md` 收摊清单；答否 → 不封，里程碑继续挂着。

- **空窗 / 零 task / 只是硬闸绿**：不建议审、也不建议封（无定量事件即无建议）。
- **有意留不算待修**：进 `docs/reviews/LEFTOVERS.md` 即可往下走。
- **k3dge 只调透镜、不自己审**（sidecar，ADR-0006）：auditor 是 `k3dit`，干活的是 agent；同一 agent 不得自审自封（除非 fallback 到 `manual` 协议由人工复核）。
- **倒计时只出现在"有待修、agent 是否动手"**：超时默认"开修"，而非"跳过审计去封"。
- **封板动作 = 收摊/上下文压缩**：`seal` 机械部分只完成归档+版本+指针；`run_seal_flow` 写 `docs/reviews/<date>-<id>-closure.md` 清单，指引人/agent 补齐：落盘失败/未采用方案（ADR/INCIDENT）、清理无关上下文、更新设计文档、提交里程碑。k3dge 不替判"什么算无关"。

### 2.1.5 审计建议的量化尺子（§2.1.4 的触发条件）
"建议审"可全用 k3dge 能自量的条件（不连 MCP、不跑 LLM），过线才 `[NEXT] audit_suggested`：
- **账齐**：当前里程碑顶层任务 N>0 且 in-progress/idea=0。
- **C2 嵌套**：触及 `src/` 控制流 AST（if/for/while/try/with）最大深度 ≥ 5。
- **体积**：`src/`+`docs/specs/` 变更文件 ≥ 8。

同一快照只问一次：本里程碑已有报告即视为已审，不再 `audit_suggested`。不纳入"建议审"的（已有别的闸）：`check` 红（去修/`k3dge sync`）、`guide-stub`（挡真封）。
**架构/`overview.md` 更新不再是触发**：它没有可数的尺子，且"算不算持久设计、写得对不对"归 k3dit/人；改到封板 closure 清单里做（§2.1.4）。
单一事实源：`engine/nextstep.STATE_OPTIONS` + `engine/audit_trigger.py`，与 §12 同一张表；命令不手抄 SOP。

### 2.1.6 一轮 = 两份报告 + 位置钉子（2026-09-01）
- **一轮"审过一遍" = audit + quality 各出一份 12 列报告**（k3dit 健壮/架构/契约，k3lity 复杂度/重复/坏味道）。`run_audit_flow` 跑两条流；闭环界定是**两份都 `待修=0`**。改后各自复审：`k3dit.actions.verify` 核审计报告、`k3lity.actions.verify` 核质量报告，不串。`audit_trigger.audit_closed` 要求两 kind 都齐。
- **`k3dit:pending <ID>` 位置钉子**：审计在报告 `位置` 处、于代码/文档那行钉一个短标记（`# …` / `// …` / `<!-- … -->`，guide-stub 同类）。`scan_pending_findings` 扫 `src/`+`docs/`（跳 archive/reviews/generated），`check`/`status` 的 `[NEXT] pending_findings pending=N`（最高优先）报出——**修的人打开文件就看见**，补上"规则没进这一轮上下文"的同类漏。
- **标记只是指针，不是第三份事实**：理由/怎么改/验收步骤**只写报告**，不写进正文——否则报告改了注释没改、或注释在代码已修，而 L1 不哈希注释、硬闸抓不到这种漂；往配对模板里插注释还会误触 `TEMPLATE_DRIFT`。处置权在 12 列 + tasks。收口：已修→删标记；有意留→改 `k3dit:leftover <ID>`（不计 pending）。

### 2.1.7 人工入口 / Checklist 缓存 / 自动 loop 上限（2026-09-01）
- **人工主动入口**：`k3dge milestone audit <id>` 与 `k3dge milestone seal [--yes] <id>` 都是人工入口，走同一套 `run_audit_flow` / `run_seal_flow`。`--yes` 仅跳过"要不要封"提问，不跳过审计（未审计闭环时 `seal` 返回 `audit_needed`）。自动探测（`check` 的 `[NEXT] audit_suggested`/`seal_ready`）与人工入口收敛到同一条流程。
- **审计条件 Checklist 缓存（非封板 checklist）**：`.agent/audit_checklist.json` 记审计条件达成快照（账齐/C2/体积 + reasons）、audit+quality 两份报告的 `待修`、`verify_attempts`、`audit_started_at`，以当前里程碑任务状态 hash 为键；`check` 只读缓存、任务集不变不重算。**`k3dge milestone audit <id>` 发起审计时重置该 checklist**（verify 预算归零 + 打 `audit_started_at`），所以人工/自动重跑各拿一个新的 3 次预算。封板资格改由 `audit_trigger.audit_closed` 判（不再由本文件判"可封"）。
- **自动 loop 上限**：`run_audit_flow` 里若 `verify` 连续超过 3 次仍未闭环（待修不归零），返回 `escalated` 并**停止自动 loop、转人工干预**，杜绝死循环。

### 2.1.8 外来审计源落盘（2026-09-01）
人把审计报告贴进对话框（或 agent 转发）属**外部审计源**，不能直接被流程解析。必须落盘为 `docs/reviews/YYYY-MM-DD-<id>-external-audit.md` 这份**本版审计报告**：`k3dge milestone audit-submit <id> [--file <报告.md> | -]`（CLI）或 MCP `k3dge_submit_audit_report`（agent 直接调）。`persist_external_audit_report` 在缺 12 列表头时自动补表头，最新一份覆盖旧的。落盘后 `audit_trigger.audit_closed` 即可判定审计闭环，进入"问题二·要不要封"；外部源与 k3dit peer 产出走同一条落盘+解析路径，无第二套。

### 2.2 为什么通过文件系统物理移动实现上下文压缩
`k3dge milestone seal` 将 `docs/tasks/*.md` 物理移入 `docs/tasks/archive/<id>/`。
`k3dge task list` 只扫顶层活跃文件，`archive/` 不在扫描面——Token 零浪费的上下文重置，且符合 `docs/tasks/archive/` 的 append-only 审计需求。

同一次 `seal` 把本里程碑的 `docs/reviews/*.md`（文件名含该 id，或正文含 `<!-- k3dge:align-pass:<id> -->`；文件名属其他里程碑的不动）移入 `docs/reviews/archive/<id>/`，并把 `docs/reviews/LEFTOVERS.md` 里的相对链接改写成 `archive/<id>/…`。失败则回滚文件移动并还原 LEFTOVERS.md。`k3dge doc list` 默认不扫 `archive/`。

### 2.2.1 修正（2026-09-01）
原稿只归档 tasks。reviews 同属 append-only 证据，顶层堆积会把 leftovers 寻址和当前里程碑报告混在一起。以本节现稿为准。

## 3. 产生后果 (Consequences)
- **正面**：确定性验收 + 防过度工程 + 上下文经济性闭环；`engine` 域由纯判定
  扩展为"门禁判定与生命周期治理核心"，职责边界在 `overview.md` 与 `engine/spec.md`
  中显式更新。
- **负面**：`engine` 引入文件生成/移动副作用，需与 `sync` 的 spec 回写职责保持
  清晰边界（`engine` 管任务归档，`sync` 管 spec 契约）。
