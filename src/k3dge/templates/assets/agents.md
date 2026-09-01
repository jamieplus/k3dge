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
| Milestone all `done` | `k3dge milestone align` → `HUMAN_CHECKPOINT(60s/N)` → `audit` or `seal` |
| `align` hook | `pipeline.toml` `pipelines.on_align_success` → `peers` `mcp→cli→manual`/`skip`；`pipelines.on_pre_seal` → `k3dit.actions.verify` |
| Guide has `guide-stub` | Fill guide |
| Simplify / delete dead code / C2 nesting | `.agent/rules/02-simplification.md` first, then change |
| `check` red ×2 | `docs/branches/` then `stash` |
| Audit done | `docs/reviews/` + leftovers table in `docs/reviews/README.md` |
| Audit fix done | Backfill `## 回填` to same report + `docs/incidents/INC-YYYYMMDD-<TYPE>-<slug>.md` B-T-D |
| 文档改动（`docs/<type>` 变更） | 走同一条 `k3dit.actions.audit` 链；`target_scope` 为文档时套用 Doc Audit 节（ADR-0020），同一 12 列报告 + `on_pre_seal` verify |
| Move/delete fact source | Update all pointers; memo target gone → move back |

## 13. Evidence Chain (ADR-0012)

Need 3 links: **产物** (path/cmd output) + **消费者** (engine/check/CI) + **到达** (hardcoded/harness/`AGENTS.md` path). No name/intent.

*Not evidence*: dir name, wish, chat memory. Missing link → "unverified" or ASK.
