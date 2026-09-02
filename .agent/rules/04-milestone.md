# Rule 04 — Milestone Lifecycle

* **Milestone cursor**：`.agent/milestone` 纯文本 `M0`→`M1`…，`scaffold` 默认写 `M0`，`seal` 成功后原子 `bump`。
* **任务编码**：`docs/tasks/YYYY-MM-DD-<type>-<slug>.md`（`type` ∈ {audit, feat, fix, docs, chore, refactor}，`slug` 内 `_`），`Status: done` 时后缀 `.done.md`；有 `Milestone: M1` 时文件名中加入 `M1`。

* **两问拆开：审计是界限，封板只是收摊。** 「结束里程碑」没有尺子（全 done、硬闸绿、没 task 都能被说成可封）；真正的界限是**审计环收口**（**audit + quality 两份 12 列报告都到 待修=0**、有意留进表）。所以自动触发只服务「要不要审」，「要不要封」只在审计闭环后出现一次。

* **问题一 · 要不要审（可量化触发，k3dge 能自量，不连 MCP/LLM）** —— `k3dge check`(绿) / `task done` / `align` / `status` 命中任一信号时附 `[NEXT] state=audit_suggested` + reasons；人只答要不要审：
  * 账齐：当前里程碑顶层任务 N>0 且 in-progress/idea = 0（本批活干完）。
  * C2 嵌套：触及 `src/` 控制流 AST（if/for/while/try/with）最大深度 ≥ 5。
  * 体积：`src/` + `docs/specs/` 变更文件 ≥ 8。
  * 答「是」→ `k3dge milestone audit <id>`：**一轮"审过一遍" = audit(k3dit) + quality(k3lity) 各出一份 12 列报告**（`mcp→cli→manual`，manual=人填，不伪造分）；两份都 `待修>0` 时问「agent 修？(倒计时默认修)」→ 修完**重审：audit→验审计报告，quality→验质量报告**（各自核对，不串）。verify 连续 >3 次未闭环 → `escalated` 停自动 loop、转人工。有意留进 `LEFTOVERS.md`。
  * **空窗 / 零 task / 只是硬闸绿：不建议审、也不建议封。** 没有定量事件就没有建议。**架构/overview 更新不再是触发**（改到里程碑 closure 里做）。

* **钉子指针 `k3dit:pending`（帮"看见"，非第三份事实）** —— 审计/质量在报告的 `位置` 处，于代码/文档那行钉一个短标记 `# k3dit:pending <ID>`（或 `// …` / `<!-- … -->`）。`k3dge` 扫 `src/`+`docs/`（跳过 archive/reviews/generated），在 `check`/`status` 的 `[NEXT] state=pending_findings pending=N` 报出，修的人打开文件即见。**标记只是指针**：处置仍以 12 列报告 + tasks 为准；理由/怎么改/验收步骤写报告，绝不写进正文（L1 不哈希注释、硬闸抓不到注释漂）。收口时：已修→删标记；有意留→改 `k3dit:leftover <ID>`（不再计 pending）。

* **1 report = 1 task（ADR-0022）** —— 一份审计报告对应**恰好一个** `audit` task，task frontmatter 带 `report: docs/reviews/<file>.md` 指针；findings 只是报告里的 12 列行，**不再逐条建 task**。`k3dge task done <report-task>` 要求该报告 `待修==0` 才放行（关 task = 审计闭环，同一闸）。特别大的单条才在 `处置` 写 `转 sub-task <id>` 例外拆出。doc-audit 已按此建一个里程碑 task（幂等）。`_auto_backfill_reviews`（标题匹配）降为无 `report:` 指针旧 task 的遗留兜底。

* **问题二 · 要不要封（唯一在审计闭环后）** —— **audit + quality 两份报告都 待修=0** 时 `check`/`status` 给 `[NEXT] state=seal_ready`；`k3dge milestone seal <id>` 才问「封板？(y/N，无倒计时)」。未闭环先调 → `audit_needed`（指回 audit）。答「是」→ align（若还没跑）→ **归档 + 版本 + 里程碑指针**；答「否」→ 不封，里程碑继续挂着。

* **封板动作 = 收摊（上下文压缩）** —— `seal` 机械部分只完成归档+版本+指针；真正的收摊写 `docs/reviews/<date>-<id>-closure.md` 清单，由人/agent 补齐：落盘**失败/未采用的方案**（ADR/INCIDENT）、清理无关上下文、**更新 `docs/architecture/overview.md` 与设计文档**、最后提交里程碑。k3dge 不替判内容——这就是 architecture 更新该待的地方，不是命令钩子。

* **人工入口** —— `k3dge milestone audit <id>` / `k3dge milestone seal [--yes] <id>` 都是人工主动入口，走同一套流程。`--yes` 跳过「要不要封」的提问，但不跳过审计。

* **doc-audit（后置、非阻断，T-01）** —— `check` 保持静态硬闸，**不跑透镜**。docs 改动时 `check` 绿后给 `[NEXT] doc_audit`，由 `k3dge doc-audit` 承接：路由 `k3dit.actions.audit` 做 **authoring 合规**（k3dit/人出报告，k3dge 不伪造），并机械建一个带 `Milestone` 的 `doc-audit` task（幂等）。恒返回 0，但 task 进里程碑 backlog → **本轮不改，封板「全 done」闸也会逼它闭环**。ADR 冲突/覆盖不在这，仍只在里程碑审计（ADR-0020）。详见 ADR-0021。

* **外来审计源落盘** —— 人贴/agent 转发的报告经 `k3dge milestone audit-submit <id> [--file <报告.md> | -] [--kind audit|quality]`（或 MCP `k3dge_submit_audit_report`）落盘为 `docs/reviews/YYYY-MM-DD-<id>-<scope>-{audit|quality}.md` 本版报告（缺 12 列表头自动补；`--kind quality` 打 `k3dge:kind: quality` 标类；最新覆盖旧）。两份都落/到 待修=0 才算闭环。

* **审计条件 Checklist（不是封板 checklist）** —— `.agent/audit_checklist.json` 记**审计条件达成 + 审计环状态**：量化触发快照（账齐/C2/体积 + reasons）、audit/quality 两份报告的 `待修`（closure）、`verify_attempts`（>3 升级用）、`audit_started_at`；以当前里程碑任务状态 hash 为键缓存（任务集不变 `check` 不重算）。**`k3dge milestone audit <id>` 发起审计时重置**（verify 预算归零 + 打 started_at，重跑拿新的 3 次预算）。封板资格不在此，由 `audit_trigger.audit_closed` 判。`k3dge milestone checklist <id>` 查看。

* **钩子链** —— `pipeline.toml`：`pipelines.on_seal_enter` = `k3dit.actions.audit` + `k3lity.actions.quality`（两份都必做）；`pipelines.on_pre_seal` = `k3dit.actions.verify` + `k3lity.actions.verify`（各自核对本报告）。`transports` 链 `mcp→cli→manual`/`skip`，`skip` 记 `HARNESS_SKIP` 于 `logs/k3dge.log`。k3dge 只调透镜、不自己审/打分（sidecar，ADR-0006）。

* **`[NEXT]` 提示（命令结果附下一跳）** —— 单一事实源 `engine/nextstep.STATE_OPTIONS` + `engine/audit_trigger.py`，与 `pipeline.toml`/`AGENTS.md §12` 同一张表。优先级：`pending_findings`（有钉的 pending）> `seal_ready`（两份报告闭环）> `audit_suggested`（量化触发）。只报合法下一步、不替人决定；`reasons` 可数。`new_domain` 仍单独报；`overview` 更新已移出钩子。

* **门禁** —— `seal` 机器闸是 `align-pass`、无 `align-stub`、无 `guide-stub`、正文列出该里程碑全部任务，缺一即 `SEAL REJECTED`。不读 `SUMMARY.md`（ADR-0018）。未闭环（缺报告或 `待修>0`）`run_seal_flow` 返回 `audit_needed`，不进封板。

* **归档** —— `seal` 将 tasks 移入 `docs/tasks/archive/<id>/`；将本里程碑 reviews（文件名含该 id，或正文含 align-pass 标记；他里程碑文件名不动）移入 `docs/reviews/archive/<id>/`，并改写 `docs/reviews/LEFTOVERS.md` 相对链接。失败回滚移动并还原 LEFTOVERS.md。
