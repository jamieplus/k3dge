---
id: INC-20260902-CON-exit-and-trail-blindspot
type: CON
severity: P2
target_milestone: M7
discovery_date: 2026-09-02
status: open
root_cause_harness: k3dge
action_task_ref: docs/tasks/2026-09-03-M7-feat-gate_exit_and_trail_checks.md
---

# INCIDENT REPORT: [M7] 出口同构与审计痕迹只被文字承诺，未被任何一处机验

## 1. 现象与证伪证据 (B-T-D Evidence)

- **预期行为**: `ADR-0008`「命令结果末尾统一附 `[NEXT] state=…` 一行（**MCP 同构 JSON `next` 字段**）」；`ADR-0012` 要求"到达"是可核环节而非修辞；`ADR-0006` T-01 要求判定与降级可复述。

- **现存破损 A｜路由对人类出口就是坏的**：`k3dge status` 非 `--json` 分支末尾引用从未绑定的 `workspace`（`src/k3dge/cli/main.py` `cmd_status`），命令打印四行后 `NameError: name 'workspace' is not defined`。⇒ `status` 这条**最常被第一个执行**的命令，其 `[NEXT]` 从未输出过；`ADR-0008` 的软路由在此长期失效。
  复现：`k3dge status; echo rc=$?` → traceback。

- **现存破损 B｜机读出口根本没有这个字段**：`workspace_status()` 返回键集不含 `next` ⇒ `k3dge status --json` 与 MCP `k3dge_status` 都没有路由信息。
  复现（修复前）：`k3dge status --json | python -c "import json,sys;print(sorted(json.load(sys.stdin)))"` → `['domains','drift','gate_passed','modified_domains','pipeline','unfinished_tasks']`。即"同构"只存在于文档句子：人类出口坏、机读出口缺。

- **现存破损 C｜审计痕迹会被自己清空**：`engine/pipeline_runner._log_harness_skip()` 用 `log.write_text(...)` 写 `logs/k3dge.log` ⇒ 每次 `skip` 覆写整份日志。同文件另有正确的 append 写法（`cli/main._append_log`），两种写法并存且其中一种毁证据。
  复现（修复前）：预置一行 → 跑一次 `skip` 传输 → 原行消失。

- **现存破损 D｜结构件被当内容条目**：`milestone.list_tasks` 与 `cli/status.py` 各持一份排除名单且都漏 `AUTHORING.md`（同文件 `:304` 另一份却含它）⇒ `k3dge task list --json` 返回幽灵 task、`status` 报 `Unfinished tasks (1)`；milestone"全 done"口径被污染。同源问题在 k3che：`../k3che/src/k3che/index.py:13` 排除集只有 `readme.md` ⇒ 实测本仓 122 篇语料含 ≥6 篇 `AUTHORING.md`。

- **附带自查证据｜`task done` 不校验验收**：本轮破损 A 修完后我立即 `task done`，而该 task 验收第二条（机读出口同构，即破损 B）**当时未实现**，是事后复核验收条目才发现。活标本已记 `docs/memo/archive/2026-09-02-peer-wiring-and-seat-options.md` §2.1。

## 2. 根因剖析 (5 Whys)

1. 为什么 `[NEXT]` 长期不输出？→ 非 `--json` 分支尾部语句从未被执行到过。
2. 为什么没测试抓到？→ 该路径**只有函数级测试**，没有一条"跑到命令末尾"的测试；与本轮在 peers 仓看到的"直接调被装饰函数、从不 `mcp.run()`"是同一形状。
3. 为什么"三出口同构"没人守？→ 它写在 `ADR-0008` 与 `overview.md` 里，但**没有任何一处代码比较过这三个出口**；同构成为修辞。
4. 为什么日志一处 append 一处覆写？→ "审计痕迹文件只可追加"从未被当作契约；两个模块各写一个日志函数。
5. 为什么结构件名单能漂出四份副本？→ 排除名单是就地字面量，无单一事实源（本仓 3 份 + k3che 1 份）。
   元层：判定"做完"的席位与干活的席位同席（`task done` 无验收复核）⇒ 上面四条各自都能被一次独立复查拦下，但没有一条被制度性要求。

## 3. 防退化动作清单

- [x] 单一来源：`cli/status.lifecycle_next()`；`workspace_status()` 携带 `next`；`cli/main._lifecycle_next` 委托（不再两份逻辑）。
- [x] 三出口一致性断言：`test_status_next_is_isomorphic_across_exits`（钉一条 `k3dit:pending`，断言人类行、`--json.next`、MCP `k3dge_status.next` 字典相等）。
- [x] 命令末尾必须跑到的断言：`test_status_renders_and_ignores_doc_aux`（`rc==0` 且输出无 `Traceback`）。
- [x] 日志改追加，并断言旧行仍在（`DowngradeIsLoud`）。
- [x] 结构件名单单一事实源 `_DOC_AUX_NAMES` / `_is_doc_aux`，4 个使用点切齐 + 测试；k3che 自己那份补 `authoring.md`（其仓留痕）。
- [ ] 机验推广到所有带 `[NEXT]` 的命令（`check` / `task` / `milestone` / `doc-audit`）：三出口同构各一条断言。
- [ ] 静态闸：目标为 `logs/**` 的覆写式写入（`write_text` / `open(..., "w")`）直接违规 `AUDIT_TRAIL_APPEND_ONLY`。
- [ ] 验收复核不落席位不闭合：`task done` 时输出该 task 验收条目 + 当轮 diff/测试清单，交另一席位逐条打勾（属席位决策，见 memo §2.1，勿轻率进闸）。

## 4. 经验灌入

- **"同构"必须落在一处比较断言**，否则它只是文档里的形容词：本例三个出口两坏一缺，`Gate SUCCESS` 一路通过。
- **命令的"最后一段渲染代码"最值得有一条走完的测试**：`NameError` 是最便宜的 bug，却活过了多次全绿（`pytest` 182 项全绿同时 `status` 必崩）。
- **痕迹文件的写入模式是契约**，不是实现细节：`append` vs `truncate` 决定审计链能否被事后复述。
- **就地字面量名单必然漂移**：同一份"什么是结构件"出现四处副本、其中一处已含 `AUTHORING.md`，就是本次幽灵条目与语料污染的根。
- **不要相信同一席位的"我做完了"**：本轮由我自己复核验收才发现的过度标记，正好是 `ADR-0006` sidecar 论点的现场证据；把这类复核制度化，比再加一条软规则有效。

## 5. 双向回链

- **Task（修复动作）**：`docs/tasks/2026-09-02-M7-fix-status_nameerror_next.done.md`（含回填）、`docs/tasks/2026-09-02-M7-fix-task_list_ghost_authoring.done.md`、`docs/tasks/2026-09-02-M7-fix-k3che_indexes_authoring_files.done.md`、待办 `docs/tasks/2026-09-03-M7-feat-gate_exit_and_trail_checks.md`
- **决策**：`docs/adr/0006-mcp-foreign-harness-injection.md` §2.3.2（`check` 纯静态）、§2.4（降级不可静默）；`ADR-0008`（`[NEXT]` 单源）；`ADR-0012`（证据链）
- **Memo**：`docs/memo/archive/2026-09-02-peer-wiring-and-seat-options.md` §2.1（过度标记活标本 + 席位三层拆解）
- **跨仓同源**：`../k3che/docs/tasks/2026-09-02-fix-authoring_in_corpus.md`、`../k3dit/docs/tasks/2026-09-02-fix-mcp2_server_dead.md`
