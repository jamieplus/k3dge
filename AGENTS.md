# Agent Execution Protocol (k3dge Spec-Gate Architecture)

You are inside a spec-gate harness. `k3dge check` blocks bad commits, not this prompt.

**Read first**: `docs/architecture/overview.md` + `docs/adr/` (esp. 0001), map coarse intent onto them (ADR 0010).

This file is the **only auto-loaded surface**. `.agent/` is process config, not a browsed folder (ADR 0014).

## Core Invariants

1. **Zero-Assumptions**: `.agent/manifest.json` → `docs/specs/<domain>/spec.md` before `src/`.
2. **Contract**: `spec` holds `Contract Hash`; public symbol change → `k3dge sync` same task.
3. **Atomic**: Read `manifest`+`spec`+`k3dge task list --json`, plan diff, code, `k3dge sync` if needed, `k3dge check` + tests, then §12 triggers.
4. **Revert**: `check` red >2 → `git stash`, reread `spec`.

## Routing — read on demand

| Scenario | Read |
| --- | --- |
| Task intake/recall | `.agent/rules/00-core-discipline.md`（快筛用 `k3dge task list --json`） |
| Memo flash | `.agent/rules/06-memo.md` |
| Branches retry | `.agent/rules/05-branches.md` |
| Audit | `.agent/rules/07-audit.md` + `docs/protocols/audit_default.md` |
| Milestone align/seal | `.agent/rules/04-milestone.md` |
| Simplify | `.agent/rules/02-simplification.md` |
| External pattern absorption | `.agent/rules/09-absorption.md` |
| Paired artifacts | `docs/architecture/overview.md` + `docs/adr/` |
| Self-contained docs | `.agent/rules/03-self-contained.md` |
| Assertion chain | §13 below |

Other `§5-11` details live in `.agent/rules/`; this file wins if conflict (ADR 0012).

## 12. Triggers — do in same turn

| Trigger | Action |
| --- | --- |
| Public signature | `k3dge sync` |
| New `src/` domain | `manifest` + `spec` + tests |
| Persistent design | `docs/adr/NNNN-*.md` + `docs/adr/README.md` |
| Task done | `Status: done` + `.done.md` |
| Milestone all `done` | `k3dge milestone align` → `HUMAN_CHECKPOINT(60s/N)` → `audit` or `seal` |
| `align` hook | `pipeline.toml` `hooks.on_align_success` `mcp→cli→manual` |
| Guide has `guide-stub` | Fill guide |
| `check` red ×2 | `docs/branches/` then `stash` |
| Audit done | `docs/reviews/` + `SUMMARY` |
| Audit fix done | Backfill `## 回填` to same report + `docs/incidents/INC-YYYYMMDD-<TYPE>-<slug>.md` B-T-D + `SUMMARY` 回填行 |
| Move/delete fact source | Update all pointers; memo target gone → move back |

## 13. Evidence Chain (ADR 0015)

Need 3 links: **产物** (path/cmd output) + **消费者** (engine/check/CI) + **到达** (hardcoded/harness/`AGENTS.md` path). No name/intent.

*Not evidence*: dir name, wish, chat memory. Missing link → "unverified" or ASK.
