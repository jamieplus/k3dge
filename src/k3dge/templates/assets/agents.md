# Agent Execution Protocol (k3dge Spec-Gate Architecture)

You are operating inside a strictly regulated codebase. The rules below are enforced
mechanically by `k3dge check` at commit time, not just by this prompt. Follow them to
avoid blocked commits.

This design was settled stepwise with the user (see `docs/adr/`, especially 0001).
Read those first and map the user's coarse intent onto them (ADR 0010). Do not make
the user re-specify the architecture in fine grain, and do not invent a new protocol
when an existing ADR already covers it. If it does not fit, ASK once.
The point of k3dge is to keep later projects (this repo included) from drifting,
hallucinating, and breaking the whole while fixing a part — the list is not exhaustive
(ADR 0011). The gate plus this file stand in for that list.

This file is the **only agent discovery surface** (harnesses auto-load it).
It says **how** to work. `.agent/` says **where** (domain routing) and holds
path-addressed slices; it is process config, not a folder you browse
(ADR 0014). When you need domain routing, read the path
`.agent/manifest.json`. When simplifying, read
`.agent/rules/02-simplification.md`. Do not `ls` `.agent/` looking for clues.

`.agent/rules/*.md` are on-disk slices of this protocol, plus Rule 02 (the
simplification procedure, not duplicated here). They are not a second protocol.
If a rule file disagrees with this file, **this file wins** — then update the
rule file in the same task (ADR 0012).

Assertions about this repo need an evidence chain (ADR 0015 / §13). A name
or an intention is not a consumer.

## 1. Zero-Assumptions & Module Scoping
- Before modifying or creating code under `src/`, locate the owning domain in
  `.agent/manifest.json`.
- Read the corresponding `docs/specs/<domain>/spec.md` first.
- NEVER invent API signatures or state transitions that contradict the spec.

## 2. The Contract Invariant
- The spec stores a `**Contract Hash**` derived from the domain's public interface.
- Any change to a public symbol (function/class/method signature) MUST be followed by
  `k3dge sync` to regenerate the interface block and hash in the SAME task.
- Body-only or cosmetic changes do not alter the contract and need no spec update.

## 3. Atomic Task Lifecycle
1. Read `.agent/manifest.json` (known path, not a directory to browse), the targeted `spec.md`, and scan `docs/tasks/` + `docs/branches/` for relevant context. Do not re-read `.agent/rules/00|01|03` as a competing source. When the work is simplification / dead-code / 拆冗余, read `.agent/rules/02-simplification.md` before deleting.
2. Formulate a step-by-step diff plan; state the impact surface (who consumes your outputs, whose outputs you consume).
3. Implement code; if public interfaces changed, run `k3dge sync`.
4. Run `k3dge check` (and unit tests) to self-verify before committing.
5. In the **same turn**, apply §12 document/milestone triggers. Do not wait for the user to say "该写文档了 / 该封板了".

## 4. Revert Discipline
- If `k3dge check` or tests fail > 2 consecutive times, `git stash` your work,
  re-read the spec, and start over. Do NOT apply random hotfixes.
- NEVER use `git checkout .` — it silently destroys valid work including spec edits.

## 5. Task Intake Discipline (Agent 自忘防护)
- User says "先记下来 / 放 tasks" → immediately write `docs/tasks/YYYY-MM-DD-<slug>.md` with **已确认意图 as title** (Status: idea), plus a self-contained retrievable summary, context, and entry point. Do not rely on chat memory.
- At task start and when user later recalls with fuzzy description ("之前那个...") → scan `docs/tasks/` (read all files) and fuzzy-match, do not hallucinate.

## 6. Memo Discipline (灵光收件箱)
- Memo collects three kinds of not-yet-actionable thoughts: fuzzy concepts (in-scope but no concrete plan yet), not-yet-landable ideas (blocked by dependency/tech/timing), and flashes weakly related to this system.
- User says "memo一下 / 灵感记一下 / 这个不排期先存着" → immediately write `docs/memo/YYYY-MM-DD-<slug>.md` (类型 + 念头 + 触发场景). If idea is in-scope but has no plan, or out-of-scope entirely, Agent MAY proactively propose memoing it and write on confirmation.
- When a memo matures into a concrete plan → promote to `docs/tasks/` (Priority assigned there) and MOVE the original memo into `docs/memo/archive/` (scans cover `docs/memo/*.md` top level only — archived entries are never re-read). Do not rely on chat memory.
- Archive only after the **new living file already exists** on disk. Promoting to a guide/PROTOCOL/sibling repo is allowed, but if that target is later deleted, MOVE the memo back to `docs/memo/` in the **same turn** (ADR 0016). Do not leave the scan horizon empty.

## 7. Branches Discipline (思维分支裁剪)
- `k3dge check` red and will retry → first archive the failed branch to `docs/branches/YYYY-MM-DD-<slug>.md` with a self-contained summary (tried path / hypothesis / why it failed / what was learned), then `git stash` and re-read spec.
- Before retrying, read `docs/branches/` to avoid repeating the same failed approach.

## 8. Paired-Artifact Discipline (成对物防混淆)
- Before merging, deleting, or "deduplicating" anything that looks redundant (same-name files, overlapping docs, dual-track scripts) → first check `docs/adr/` and the global invariants in `docs/architecture/overview.md`. An archived memo plus the PROTOCOL/guide it was promoted into is a paired set: deleting the living file without restoring the memo empties the scan horizon (ADR 0016).
- No documented basis → STOP and ask the user. Never decide silently.
- Each clarification MUST be recorded as a numbered micro-ADR so the next agent doesn't need the user present.

## 9. Audit Records Discipline (审计结果归档)
- 透镜规程不在 k3dge 包内。优先 `docs/guides/protocol.md` 或 `../k3dit/docs/guides/protocol.md`；两者都不在则读 `docs/memo/2026-08-24-audit-harness-independence.md`（8 维现行清单；勿读 archive 里 08-23 短五轮）。
- Agent audits/line-reviews produce a report at `docs/reviews/YYYY-MM-DD-<scope>.md`:
  findings table with severity + disposition (已修 / 转 tasks / 有意留+理由).
- Unfixed, unrefuted findings MUST become `docs/tasks/` entries — never report-only.
- Before a new audit, read `docs/reviews/SUMMARY.md` first for summaries; then read
  only relevant `docs/reviews/*.md` reports. Do not re-report fixed items or
  re-propose refuted ones.

## 10. Self-Contained Documents Discipline
- Every document (spec, ADR, guide, memo, task, architecture overview) MUST be self-contained: a future reader with no prior conversation can understand it from the file alone.
- Include what, why, and when to revisit in the file itself. Do not rely on chat history.

## 11. Milestone Alignment & Anti-Overengineering Protocol
- **目标对齐第一**：禁止脱离目标随意发散。重构仅当命中 C1 扩展硬阻塞 / C2 坏味道严重超标 / C3 契约漂移未愈。
- **触发见 §12**：不要等用户提醒 "该 align / 该 seal"。

## 12. Unsolicited Document & Milestone Triggers（用户不必再喊）

用户只负责说**要做什么**。下列事件一旦发生，Agent **当轮必须**维护对应物，禁止等下一句显式指令。

| 触发（已发生即做） | 维护 |
| --- | --- |
| 公开签名变更 | 同任务 `k3dge sync` |
| 新建 `src/` 树或新域 | `.agent/manifest.json` 登记 + `docs/specs/<domain>/spec.md`（从 `_template`）+ tests 目录 |
| 用户给出持久设计选择/澄清（哪怕随口） | 下一号 `docs/adr/NNNN-*.md`，并在 overview §5 加一行 |
| 跨域不变量变化 | `docs/architecture/overview.md` |
| 本任务做完 | 对应 `docs/tasks/*` 的 **Status: done** |
| 某 `Milestone` 下顶层 tasks 全部 `done` | 立刻 `k3dge milestone align <id>` |
| align 已成功且本轮能填验收 | 去掉 `align-stub`、保留 `align-pass`、更新 `docs/reviews/SUMMARY.md`；无 `guide-stub` 则立刻 `k3dge milestone seal <id>`；有 stub 则先填再 seal |
| 改到的功能，其 guide 仍含 `<!-- k3dge:guide-stub -->` | 本轮填掉该 guide |
| `k3dge check` 连续红两次还要再试 | 先写 `docs/branches/` 再 stash |
| 做了审计 | `docs/reviews/` + SUMMARY |
| 用户说「先记下来 / 放 tasks」 | §5（仍要口令，因为尚未发生「任务完成」） |
| 用户说「memo一下」 | §6（仍要口令或你提议后确认） |
| 用户说「帮我配 MCP」或「接入 DSH/Codex/Claude Code/OpenCode」 | **只**走 `docs/guides/mcp-bridge.md` 的固定剧本，禁止自创 JSON/路径 |
| 用户要求简化 / 删死代码 / 拆冗余，或里程碑 C2 勾了深层嵌套 | 按 `.agent/rules/02-simplification.md` 举证后再动；不是门禁 |
| 即将断言本仓事实（路径用途、谁消费、还能触发、没有设计问题） | §13：三条链齐了再说；缺链写「未核」或问，不许装成已核 |
| 搬走或删除仍被点名为事实源/扫描入口的文件 | 同轮改所有指针；若是 memo 晋升目标且目标已不在，把 memo 搬回 `docs/memo/` 顶层（ADR 0016） |

不要自动去改用户机器上其它 harness 的配置文件，除非用户说了「帮我配」。配的时候不许即兴发挥。

## 13. Assertion Evidence Chain（断言须有证据链）

对**本仓库的事实**下结论（某路径干什么、谁读它、某能力是否还在、没有设计问题、Agent 会发现 X）时，同一轮给出：

1. **产物** — 打开过的路径或跑过的命令输出
2. **消费者** — engine / `k3dge check` / CI / 本文件自动加载 / 无
3. **到达方式** — 硬编码、harness 自动加载、本文件点名的路径。禁止「会逛到点目录」

不是证据：目录名、愿望、聊天记忆、「我没提过所以没问题」。缺一环则说未核或 ASK，不要写成肯定句。改代码仍走 spec + `k3dge check`；本条不进门禁（ADR 0015）。
