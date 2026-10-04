# Agent Execution Protocol (k3dge Spec-Gate Architecture)

> **权威源**：协议与模板以 <https://github.com/jamieplus/k3dge>（`docs/protocols/peer_contract.md`）为准；本地兄弟仓仅为工作副本。

You are inside a spec-gate harness. `k3dge check` blocks bad commits, not this prompt.

**Read first**: run `k3dge status` for current workspace state; then `docs/architecture/overview.md` + `k3dge doc where ADR-0001` (ADR-0008 for triggers).

This file is the **only auto-loaded surface**. `.agent/` is process config, not a browsed folder (ADR-0010).

## Core Invariants

1. **Zero-Assumptions**: `.agent/manifest.json` → `docs/specs/<domain>/spec.md` before `src/`.
2. **Contract**: `spec` holds `Contract Hash`; public symbol change → `k3dge sync` same task.
3. **Atomic**: Read `manifest`+`spec`+`k3dge task list --json`, plan diff, code, `k3dge sync` if needed, `k3dge check` + tests, then §12 triggers.
4. **Revert**: `check` red >2 → `git stash`, reread `spec`.
5. **Boundary**: 设计先拆后做——先写「事实归属」（哪个模块拥有哪个事实），方案不许让 A 模块知道 B 的内部（步骤数/内部状态/实现方式）；先桩后实（契约冻结 + dummy 跑通骨架）再进局部细节。细则 `.agent/rules/08-design-discipline.md`。

## Docs — locate, then load

- **Write** `docs/<type>/…` (not `docs/<type>/README.md` / `docs/<type>/AUTHORING.md`): open `docs/<type>/AUTHORING.md`; copy `docs/<type>/_template.md` if it exists. `<type>` is the first path segment under `docs/` (`docs/tasks/archive/x.md` → `docs/tasks/`).
- **Find** a document: default `k3dge doc list` / `k3dge doc where <id>` (or `k3dge task list --json` for tasks), then `read` the path. Body scan only via `k3dge doc grep <word>` (paths, or `--line` for `path:line`). Never return snippets. Do not raw-grep `docs/`.
- k3dge structure gate is `docs/<type>/.schema.json` (hidden). Do not self-audit document *merit*.

## 路由 — 软规则 + 提交门禁

`scripts/pre-commit` (`git config core.hooksPath scripts`): staged `docs/**` need `docs/<type>/README.md` and `docs/<type>/AUTHORING.md`. Code/spec changes still run `k3dge check`. `.agent/rules/*` are slices (ADR-0010); this file wins.

审计回退（`.agent/pipeline.toml` 指向 `docs/protocols/audit_default.md` 且 k3dit 不可达）**不是独立审计**：MCP 挂时，干活 agent 不得自审出报告即 `seal`；须转人工 / 外部 harness 复核（ADR-0006 sidecar：work 与 check 不可由同一 agent 粘合）。

## 12. Triggers — do in same turn

| Trigger | Action |
| --- | --- |
| Public signature | `k3dge sync` |
| New `src/` domain | `manifest` + `spec` + tests |
| Persistent design | **先并同类 ADR**（AUTHORING「先并入，后新建」）；确无同类才 copy `docs/adr/_template.md`；read `docs/adr/AUTHORING.md` |
| Task done | `Status: done` + `.done.md` |
| Milestone all `done` | `[NEXT] audit_suggested`（**不是建议封板**）：`fact` 陈述触发事实 + 成对 `option`（审 / 不审）→ 选审 → `k3dge milestone audit <id>`：合并审计模块（ADR-0025）**一份 12 列报告**；待修>0 → `[NEXT] audit_open`（fact + 成对 option；**疑问句只在 prompt 侧**，倒计时默认修）→ 重审（同一报告 verify）→ 待修=0 → `[NEXT] seal_ready`。**也可直接 "
  `k3dge milestone seal <id>`**（相位 2 会自己跑审计）；封板判定只在 prompt 侧问一次（无倒计时，N=不封） |
| 审计＝封板主体（seal 相位 2） | `k3dge milestone seal <id>` 是三相位唯一入口（幂等重入）：**预审**（align + 形式闸；失败⇒修完再 seal）→ **审计**（`[checks.seal].actions` 的 `audit` 节点，位在 `full_matrix` 后、`archive` 前）→ **审核后自动**（归档+版本+指针）。**审计正常返回⇒版号前进**（相位 3①，`--no-version-bump` 逃生），不管有没有报告；相位 3②写**封版提交**（trailer 四键 `Seal-milestone`/`Audit-baseline`/`Audit-seat`/`Audit-result`）+ 立 **边界 tag `<M> = <B>`**（B＝审计基线，审哪版封哪版）；report 降为可选产物（ADR-0004 §2.1.9/§2.1.10）。审计结果只认闭集 `closed`/`degraded-manual`(**走了 manual 传输**，不论降级位还是首选位，须署名)/`escalated`/`refused`——**`skip` 与空转一律 `refused`**（先判"跳真跑过"再谈报告）。审计调用声明在 `[checks.audit]` 的 `stages_produce` → `audit.actions.audit`、`stages_verify` → `audit.actions.verify`（缺省 `engine/gates.DEFAULTS`，**声明面唯一**＝`.agent/pipeline.toml`；原 `[pipelines.*]` 与 `.agent/gates.toml` 已废）；`transports` `mcp→cli→manual`/`skip`；verify 预算走 `.agent/audit_checklist.json`（**运行态投影，非判据**），>3 次未闭环 → `escalated` 转人工；独立入口 `k3dge milestone audit <id>` / 外来源 `k3dge milestone audit-submit` 保留（**只补证据**：不推进版号、不触发封板）；报告＝**可选产物**（存在则须合格：12 列 + `审计人`/`透镜来源`/`基线`），judged 只用 git 事实（`audit_evidence`：边界 tag + 封版提交 trailer），本地账（`audit_jobs`/`audit_checklist`）是投影、冲突以 git 为准 | 相位 3 的 closure 会**先刷纯投影**（`docs/generated/{api,domains}.md`、`docs-index.json`、符号索引、README 自动块——全部派生、幂等；**不跑整条 sync**：spec 接口块/哈希与 ADR reconcile 是事实源写，审计后动它们等于改审计看过的内容），再**算出**设计文档新鲜度（最近边界 tag..HEAD 内 `src/`/`docs/specs/` 变过而 `docs/architecture/{overview,encyclopedia}.md` 未动 ⇒ 收摊清单与 seal 输出逐件列出；域表的**事实列**另有 `check` 闸 `ARCH_TABLE_DRIFT`；新鲜度**仍不阻断**——写得好坏归人/k3dit）。
| 审计建议触发（账齐/C2≥5/体积≥8） | `k3dge check`(绿)/`task done`/`align`/`status` 返回 `[NEXT] audit_suggested` + reasons（单一源 `engine/audit_trigger.py`+`nextstep`）。**口径与数值**：定义见 `src/k3dge/engine/audit_trigger.py` 模块 docstring（账齐＝本里程碑顶任务 N>0 且无在办/idea；C2＝触及 `src/` 控制流 AST 深度；体积＝本轮改动量），阈值取 `pipeline.toml [gates.audit_trigger]` 的 `c2_nesting_max`/`volume_max`（改数即改这一处，别在散文里另立）。**overview/架构更新不是触发**——收摊(closure)里做；是否算持久设计、写得对不对仍归 k3dit/人 |
| 代码/文档里有 `k3dit:pending` 钉 | `check`/`status` 返回 `[NEXT] pending_findings pending=N`（最高优先）。**钉＝写源**（判读四格 sev/prio/type/desc，见 peer_contract §8 / ADR-0025 §2.7）；账本/12 列＝钉的投影，每轮重生成。修席翻 `fixnote`（不删钉）、复核背书翻 `fixed`、有意留翻 `leftover`，**拔钉归 Hall** |
| 新建 `src/` 域 | `k3dge check` / `status` 返回 `[NEXT] new_domain`：补 `manifest` + `spec` + `tests`，再 `k3dge sync` 回写契约哈希 |
| Guide has `guide-stub` | Fill guide |
| Simplify / delete dead code / C2 nesting | `.agent/rules/02-simplification.md` first, then change |
| 同一叮嘱要写第二遍 / 重复纠正 | `.agent/rules/10-structure-over-prose.md` first（下沉机制，别加散文） |
| 新增机制/模块/注册表/声明文件/命令 | `.agent/rules/12-introduction-discipline.md` first（完整＋实测正向作用；不单独扩基建） |
| `check` red ×2 | `docs/branches/` then `stash` |
| 空转（同动作+同错误 ≥3 次，含改而复改） | **立即停机 surface**：列已试签名，问人或转 `docs/branches/`；禁止第四次重试（机制化=tool-call 计数器 task；Hall 侧 W6） |
| Audit done | `docs/reviews/` + leftovers in `docs/reviews/LEFTOVERS.md` |
| Audit fix done | Backfill `## 回填` to same report + `docs/incidents/INC-YYYYMMDD-<TYPE>-<slug>.md` B-T-D |
| 新建受管文档（主观撰写类：adr/memo/guides/architecture/protocols/incidents/branches） | `scripts/pre-commit` 阻断一次（`DOC_NEW_UNSCREENED`）：按规约先排查是否与既存文档**冲突/覆盖/只是其子项**——**判定归 agent**（进程判不了语义），闸只把排查送到动手这一刻。并入既存 ⇒ 收编 + 删新文件 + `k3dge sync`；确认新建 ⇒ `k3dge doc screen <path>`（回执 ephemeral，`.protocol-ack/`，不入库；同文件不再拦）。确定性流程生成的文档（`docs/generated|specs|tasks|reviews`）与 aux 不在排查面 |
| 文档改动（`docs/**` 变更） | 三层：①**提交时硬闸**（结构/schema）+ 新建受管文档**首次筛查闸** `DOC_NEW_UNSCREENED`（阻断一次）；②`[NEXT] doc_fix` 引导**主动动作** `k3dge doc fix`（闭集规则、幂等、`--dry-run`），封板前置 `docs_normalized` 验"做没做"；③**语义质量**归里程碑审计（合并审计模块的 scope 含 `docs`）。原「doc-audit 出报告 + 建里程碑票」路径已退休（ADR-0022 §2.2 🅰1：实测未走通）。**ADR 冲突/覆盖**仍在里程碑审计（`k3dge_adr_index`+k3dit，ADR-0005） |
| 提交信息里裸写 `k3ge`（**错写**，正确名 `k3dge`，无此仓） | 提交时机检**提示**（advisory，不阻断）：`scripts/commit-msg` → `k3dge check-msg`；反引号跨度＝在引用这个错写，不提示 |
| CHANGELOG 条目 | **不由 `task done` 写**（双写＝漏项/漂移的来源）：封版时由**提交区间**生成（上一里程碑 `tag` .. HEAD 的非机械提交，类型取 conventional 前缀，ADR-0004 §2.1.12）；闸只验不漏项（无前缀的提交进 `uncovered` 告警），写得好归人 |
| Move/delete fact source | Update all pointers; memo target gone → move back |
| 票落在边界之后（`[GATE WARN] TASK_MILESTONE_AFTER_BOUNDARY`） | advisory：`k3dge milestone reassign <M> --to <新里程碑>`（frontmatter + 文件名同改，幂等、`--dry-run` 可预览）；不阻断——归属判定归人，闸只说「边界那一版还没有它」 |
| 新增一条可机检规则（`check`/schema/hook 能红的那种） | 同轮配**三件**：①违规码（`engine/gate_facts.py`）②消费者＝修复器（`engine/doc_fix.py` 的 `FIXABLE_RULES`）**或**命令（`doc_fix.BY_COMMAND`）③`[NEXT]` 引导（`engine/nextstep.py` 的 `GATE_NEXT`）。反向机检兜住：`tests/unit/engine/test_doc_fix.py::TestRuleSetConsistency::test_every_deterministic_code_has_a_consumer`（码声明 deterministic 却没消费者 ⇒ 红）。只写进 `AGENTS.md`/`.agent/rules` 散文、没有到达执行者 → 本轮补闸或标有意留。**不**因此硬阻断人写的散文 |

## 13. Evidence Chain (ADR-0012)

Need 3 links: **产物** (path/cmd output) + **消费者** (engine/check/CI) + **到达** (hardcoded/harness/`AGENTS.md` path). No name/intent.

*Not evidence*: dir name, wish, chat memory. Missing link → "unverified" or ASK.
