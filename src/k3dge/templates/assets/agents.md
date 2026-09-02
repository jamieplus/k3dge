# Agent Execution Protocol (k3dge Spec-Gate Architecture)

You are inside a spec-gate harness. `k3dge check` blocks bad commits, not this prompt.

**Read first**: run `k3dge status` for current workspace state; then `docs/architecture/overview.md` + `k3dge doc where ADR-0001` (ADR-0008 for triggers).

This file is the **only auto-loaded surface**. `.agent/` is process config, not a browsed folder (ADR-0011).

## Core Invariants

1. **Zero-Assumptions**: `.agent/manifest.json` → `docs/specs/<domain>/spec.md` before `src/`.
2. **Contract**: `spec` holds `Contract Hash`; public symbol change → `k3dge sync` same task.
3. **Atomic**: Read `manifest`+`spec`+`k3dge task list --json`, plan diff, code, `k3dge sync` if needed, `k3dge check` + tests, then §12 triggers.
4. **Revert**: `check` red >2 → `git stash`, reread `spec`.

## Docs — locate, then load

- **Write** `docs/<type>/…` (not README / AUTHORING.md): open `docs/<type>/AUTHORING.md`; copy `docs/<type>/_template.md` if it exists. `<type>` is the first path segment under `docs/` (`docs/tasks/archive/x.md` → `docs/tasks/`).
- **Find** a document: default `k3dge doc list` / `k3dge doc where <id>` (or `k3dge task list --json` for tasks), then `read` the path. Body scan only via `k3dge doc grep <word>` (paths, or `--line` for `path:line`). Never return snippets. Do not raw-grep `docs/`.
- k3dge structure gate is `docs/<type>/.schema.json` (hidden). Do not self-audit document *merit*.

## 路由 — 软规则 + 提交门禁

`scripts/pre-commit` (`git config core.hooksPath scripts`): staged `docs/**` need `docs/<type>/README.md` and `AUTHORING.md`. Code/spec changes still run `k3dge check`. `.agent/rules/*` are slices (ADR-0010); this file wins.

审计回退（`.agent/pipeline.toml` 指向 `audit_default.md` 且 k3dit 不可达）**不是独立审计**：MCP 挂时，干活 agent 不得自审出报告即 `seal`；须转人工 / 外部 harness 复核（ADR-0006 sidecar：work 与 check 不可由同一 agent 粘合）。

## 12. Triggers — do in same turn

| Trigger | Action |
| --- | --- |
| Public signature | `k3dge sync` |
| New `src/` domain | `manifest` + `spec` + tests |
| Persistent design | copy `docs/adr/_template.md`; read `docs/adr/AUTHORING.md` |
| Task done | `Status: done` + `.done.md` |
| Milestone all `done` | `k3dge milestone align`(Full Matrix, 无人问) → `[NEXT] audit_suggested`（**不是建议封板**）→ 问「要审吗？(y/N 无倒计时)」→ 是→ `k3dge milestone audit <id>`：audit(k3dit)+quality(k3lity) **各出一份 12 列报告**，待修>0 问「agent 修？(倒计时默认修)」→ 重审（audit→验审计报告，quality→验质量报告）→ 两份都 待修=0 → `[NEXT] seal_ready` → `k3dge milestone seal` 才问「封板？」 |
| `seal` hook | `pipeline.toml` `pipelines.on_seal_enter` → `k3dit.actions.audit`+`k3lity.actions.quality`(两份必做)；`pipelines.on_pre_seal` → `k3dit.actions.verify`+`k3lity.actions.verify`(各自核对)；`transports` `mcp→cli→manual`/`skip`；verify 尝试走 `.agent/audit_checklist.json` 审计条件缓存计数（`milestone audit` 发起即重置预算）、>3 次未闭环 → `escalated` 转人工；外来审计源经 `k3dge milestone audit-submit`(或 MCP `k3dge_submit_audit_report`，`--kind quality`) 落盘为本版报告 |
| 审计建议触发（账齐/C2≥5/体积≥8） | `k3dge check`(绿)/`task done`/`align`/`status` 返回 `[NEXT] audit_suggested` + reasons（单一源 `engine/audit_trigger.py`+`nextstep`）。**overview/架构更新不是触发**——收摊(closure)里做；是否算持久设计、写得对不对仍归 k3dit/人 |
| 代码/文档里有 `k3dit:pending` 钉 | `check`/`status` 返回 `[NEXT] pending_findings pending=N`（最高优先）。标记只是指针（`位置`旁一行短 ID，guide-stub 同类）；处置以 12 列+tasks 为准，理由/改法写报告**不入正文**；已修删标记、有意留改 `k3dit:leftover <ID>` |
| 新建 `src/` 域 | `k3dge check` / `status` 返回 `[NEXT] new_domain`：补 `manifest` + `spec` + `tests`，再 `k3dge sync` 回写契约哈希 |
| Guide has `guide-stub` | Fill guide |
| Simplify / delete dead code / C2 nesting | `.agent/rules/02-simplification.md` first, then change |
| `check` red ×2 | `docs/branches/` then `stash` |
| Audit done | `docs/reviews/` + leftovers in `docs/reviews/LEFTOVERS.md` |
| Audit fix done | Backfill `## 回填` to same report + `docs/incidents/INC-YYYYMMDD-<TYPE>-<slug>.md` B-T-D |
| 文档改动（`docs/**` 变更） | check 绿后（**不在 check 内**，T-01）给 `[NEXT] doc_audit`：`k3dge doc-audit` 走 authoring 合规、**非阻断**，出 k3dit 报告 + 建**带 Milestone 的 task**（本轮不改，封板轮也得改，ADR-0021）。**ADR 冲突/覆盖**仍只在里程碑审计（`k3dge_adr_index`+k3dit，ADR-0020），不在每次 commit |
| Move/delete fact source | Update all pointers; memo target gone → move back |

## 13. Evidence Chain (ADR-0012)

Need 3 links: **产物** (path/cmd output) + **消费者** (engine/check/CI) + **到达** (hardcoded/harness/`AGENTS.md` path). No name/intent.

*Not evidence*: dir name, wish, chat memory. Missing link → "unverified" or ASK.
