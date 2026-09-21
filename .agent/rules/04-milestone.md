# Rule 04 — Milestone Lifecycle

* **Milestone cursor**：`.agent/milestone` 纯文本 `M0`→`M1`…，`scaffold` 默认写 `M0`，`seal` 成功后原子 `bump`。
* **任务编码**：`docs/tasks/YYYY-MM-DD-<type>-<slug>.md`（`type` ∈ {audit, feat, fix, docs, chore, refactor}，`slug` 内 `_`），`Status: done` 时后缀 `.done.md`；有 `Milestone: M1` 时文件名中加入 `M1`。

* **一次声明 + 一条链（审计是封板的主体）。** 「结束里程碑」没有尺子（全 done、硬闸绿、没 task 都能被说成可封）；**审计**才是封板的主体与界限。人发起 `k3dge milestone seal <id>`（唯一入口，幂等重入）＝同时开启三相位：**预审**（align + 形式闸；失败⇒修完再 seal）→ **审计**（对**基线版本**跑；正常返回⇒**版号前进**，不管有没有报告）→ **审核后自动**（归档+版本+指针+记录）。`[NEXT] state=seal_ready` 只说"形式闸与票已齐、要不要收这一章由你决定"。

* **问题一 · 要不要审（可量化触发，k3dge 能自量，不连 MCP/LLM）** —— `k3dge check`(绿) / `task done` / `align` / `status` 命中任一信号时附 `[NEXT] state=audit_suggested` + reasons；`[NEXT]` 只出**陈述式 `fact` + 成对 `option`**（审 / 不审），不出疑问句（ADR-0026 §2.2 语法维：纯打印面无应答通道）。人只答要不要审：
  * 账齐：当前里程碑顶层任务 N>0 且 in-progress/idea = 0（本批活干完）。
  * C2 嵌套：触及 `src/` 控制流 AST（if/for/while/try/with）最大深度 ≥ 5。
  * 体积：`src/` + `docs/specs/` 变更文件 ≥ 8。
  * 答「是」→ `k3dge milestone audit <id>`：**一轮"审过一遍" = 合并审计模块（ADR-0025）一份 12 列报告**（`mcp→cli→manual`，manual=人填，不伪造分）；`待修>0` 时给 `[NEXT] audit_open`（fact + 成对 option）；**只有 prompt 侧（读 stdin）才用疑问句**，倒计时默认修 → 修完**重审同一报告**。verify 连续 >3 次未闭环 → `escalated` 停自动 loop、转人工。有意留进 `LEFTOVERS.md`。
  * **空窗 / 零 task / 只是硬闸绿：不建议审、也不建议封。** 没有定量事件就没有建议。**架构/overview 更新不再是触发**（改到里程碑 closure 里做）。

* **钉＝写源（不是"只读指针"）** —— 判读四格（严重度/优先级/类型/描述）写源＝树上钉；账本、12 列报告＝钉的投影（每轮 harvest 重生成）。审计/修/核只增/翻 kind：修席翻 `fixnote`、复核背书翻 `fixed`、有意留翻 `leftover`，**拔钉归 Hall**。`k3dge` 扫 `src/`+`docs/`（跳过 archive/reviews/generated），在 `check`/`status` 的 `[NEXT] state=pending_findings pending=N` 报出。详见 peer_contract §8 / ADR-0025 §2.7。

* **1 report = 1 task（ADR-0022）** —— 一份审计报告对应**恰好一个** `audit` task，task frontmatter 带 `report: docs/reviews/<file>.md` 指针；findings 只是报告里的 12 列行，**不再逐条建 task**。`k3dge task done <report-task>` 要求该报告 `待修==0` 才放行（关 task = 审计闭环，同一闸）。特别大的单条才在 `处置` 写 `转 sub-task <id>` 例外拆出。`_auto_backfill_reviews`（标题匹配）降为无 `report:` 指针旧 task 的遗留兜底。

* **要不要封（人发起，只问一次）** —— `check`/`status` 给 `[NEXT] state=seal_ready`（事实陈述 + 成对 option：seal / 不封）；`k3dge milestone seal <id>` 的 prompt 侧才问一次（无倒计时，N=不封）。**未审不是"不可封"**：审计由 seal 相位 2 自己跑。答「是」→ 预审 → 审计 → **归档 + 版本 + 里程碑指针**；答「否」→ 不封，里程碑继续挂着。

* **版号与边界（都落在相位 3）** —— 版号在**审计正常返回后**前进（`--no-version-bump` 逃生）；`seal` 自己写**封版提交**（归档+提版+收摊+审计产出一起进，trailer 四键 `Seal-milestone`/`Audit-baseline`/`Audit-seat`/`Audit-result`）并立 **边界 tag `tag <M> = <B>`**（B＝审计基线，审哪版封哪版）——记录挂在**必然发生的封版提交**上，因为审计常常零提交、报告只落工作树：挂在"审计的提交"上没有载体。**本地账（`audit_jobs.json`/`audit_checklist.json`）是运行态投影，不作判据**（冲突以 git 为准）。

* **封板动作 = 收摊（上下文压缩）** —— `seal` 机械部分只完成归档+版本+指针；真正的收摊写 `docs/reviews/<date>-<id>-closure.md` 清单，由人/agent 补齐：落盘**失败/未采用的方案**（ADR/INCIDENT）、清理无关上下文、**更新 `docs/architecture/overview.md` 与设计文档**、最后提交里程碑。k3dge 不替判内容——这就是 architecture 更新该待的地方，不是命令钩子。

* **人工入口** —— `k3dge milestone audit <id>` / `k3dge milestone seal [--yes] <id>` 都是人工主动入口，走同一套流程。`--yes` 跳过「要不要封」的提问，但不跳过审计。

* **重挂（边界之后开的票）** —— 边界确立后（`tag <M> = <B>`），B 之后新开的票若指针未前进就会挂在旧里程碑上 ⇒ `[GATE WARN] TASK_MILESTONE_AFTER_BOUNDARY`（**advisory**：只指出"边界那一版还没有它"，不判该归哪一版）。重挂用 `k3dge milestone reassign <M> --to <新号> [--dry-run]`：**frontmatter 与文件名同改**（半吊子会被 `TASK_MILESTONE_MISMATCH` 拦），幂等。

* **文档合规（三层，T-01）** —— `check` 保持静态硬闸、**不跑透镜**。①**提交时**：结构/schema 硬闸 + 新建受管文档首次筛查闸 `DOC_NEW_UNSCREENED`（阻断一次，判定归 agent）；②**可确定修的偏差**：`[NEXT] doc_fix` 引导 `k3dge doc fix`（闭集规则、幂等、`--dry-run`），封板前置 `docs_normalized` 验"做没做"——规约化必须在**封板前**完成，否则改在审计闭环之后会让刚闭环的审计证据失效；③**语义质量**（Context 是否写成 timeline、Decision 是否只写不变量、有无过程叙述）：归**里程碑审计**（合并审计模块的 scope 含 `docs`），不进自动修。原「doc-audit 出报告 + 建里程碑票」路径**已退休**（ADR-0022 §2.2 🅰1：`run_doc_audit` 丢弃透镜返回、票绑错报告，实测未走通）。ADR 冲突/覆盖仍在里程碑审计（ADR-0005）。

* **外来审计源落盘（只补证据）** —— 人贴/agent 转发的报告经 `k3dge milestone audit-submit <id> [--file <报告.md> | -]`（或 MCP `k3dge_submit_audit_report`）落盘为 `docs/reviews/YYYY-MM-DD-<id>-<scope>-audit.md` 本版报告（缺 12 列表头自动补；最新覆盖旧）。**不推进版号、不触发封板**（ADR-0004 §2.1.10）：版号前进只认"审计正常返回"（seal 相位 2）。报告＝**可选产物**——存在则须合格（12 列 + `审计人`/`透镜来源`/`基线`），不存在不卡流程；`audit_closed`（报告存在 ∧ 待修=0）只是**报告合格性**，不再是封板前置。判据只认 git 事实（`audit_flow.audit_evidence`：边界 tag + 封版提交 trailer / tag 注解），本地账是投影、**冲突以 git 为准**。（`--kind quality` 保留为 legacy，不再有独立质量腿。）

* **审计条件 Checklist（不是封板 checklist）** —— `.agent/audit_checklist.json` 记**审计条件达成 + 审计环状态**：量化触发快照（账齐/C2/体积 + reasons）、该审计报告的 `待修`（closure）、`verify_attempts`（>3 升级用）、`audit_started_at`；以当前里程碑任务状态 hash 为键缓存（任务集不变 `check` 不重算）。**`k3dge milestone audit <id>` 发起审计时重置**（verify 预算归零 + 打 started_at，重跑拿新的 3 次预算）。**它是运行态投影，不作封板判据**（判据只认 git 事实：基线 hash / `tag <M>` / 封版提交 trailer）。`k3dge milestone checklist <id>` 查看。

* **钩子链（`seal` 相位 2 是消费者）** —— `seal` **自己跑审计**（声明面 `[checks.seal].actions` 里的 `audit` 节点，位在 `full_matrix` 之后、`archive` 之前）；`k3dge milestone audit <id>` / 外部报告 `k3dge milestone audit-submit <id>` 是**独立的主动入口**，语义不变。审计结果只认**闭集** `closed` / `degraded-manual`（须署名）/ `escalated` / `refused`：只有前两者推进版号，**`skip` 与空转一律 `refused`**（先判"这一跳真跑过"，再谈报告在不在）。外部步声明在 `[checks.audit]`：`stages_produce` = `k3dit.actions.audit`（一份必做）；`stages_verify` = `k3dit.actions.verify`（核对本报告）。缺省在 `engine/gates.DEFAULTS`，**声明面唯一**＝`.agent/pipeline.toml`（`[checks.*]`/`[gates.*]`），下游可配、坏配置回落缺省；`.agent/gates.toml` 已废（存在即红一次逼迁移）；声明了却解析不到 peer action ⇒ `PIPELINE_UNRESOLVED_STAGE`（不让声明空转）。原 `[pipelines.on_seal_enter]` / `[on_pre_seal]` **已废**：那两处只有 schema 校验、没有执行者。`transports` 链 `mcp→cli→manual`/`skip`，`skip` 记 `HARNESS_SKIP` 于 `logs/k3dge.log`。k3dge 只调透镜、不自己审/打分（sidecar，ADR-0006）。

* **`[NEXT]` 提示（命令结果附下一跳）** —— 单一事实源 `engine/nextstep.STATE_OPTIONS` + `engine/audit_trigger.py`，与 `pipeline.toml`/`AGENTS.md §12` 同一张表。优先级：`pending_findings`（有钉的 pending）> `seal_ready`（审计报告闭环）> `audit_suggested`（量化触发）。只报合法下一步、不替人决定；`reasons` 可数。`new_domain` 仍单独报；`overview` 更新已移出钩子。

* **门禁（两道机械）** —— ①**预审**（进审计的门槛）：`tasks_all_done` + `align-pass`/无 `align-stub`/正文列出全部任务 + `docs/guides/` 无 stub + ADR 全 Accepted 且带落地指针 + `docs_normalized`；②**落点闸**：审计线合并回主干时跑 `sync + check + doc-gate + pytest`，红则回滚主干（先验后并）。不读 `SUMMARY.md`（ADR-0018）。**报告降为可选产物**（存在则须合格：12 列 + `审计人`/`透镜来源`/`基线`），不再作封板前置；边界由 `tag <M>=<B>` 表达。

* **归档** —— `seal` 将 tasks 移入 `docs/tasks/archive/<id>/`；将本里程碑 reviews（文件名含该 id，或正文含 align-pass 标记；他里程碑文件名不动）移入 `docs/reviews/archive/<id>/`，并改写 `docs/reviews/LEFTOVERS.md` 相对链接。失败回滚移动并还原 LEFTOVERS.md。
