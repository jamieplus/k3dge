# Agent Execution Protocol (k3dge Spec-Gate Architecture)

You are inside a spec-gate harness. `k3dge check` blocks bad commits, not this prompt.

**Read first**: `docs/architecture/overview.md` + `docs/adr/` (esp. 0001), map coarse intent onto them (ADR 0010).

This file is the **only auto-loaded surface**. `.agent/` is process config, not a browsed folder (ADR 0014).

## Core Invariants

1. **Zero-Assumptions**: `.agent/manifest.json` → `docs/specs/<domain>/spec.md` before `src/`.
2. **Contract**: `spec` holds `Contract Hash`; public symbol change → `k3dge sync` same task.
3. **Atomic**: Read `manifest`+`spec`+`k3dge task list --json`, plan diff, code, `k3dge sync` if needed, `k3dge check` + tests, then §12 triggers.
4. **Revert**: `check` red >2 → `git stash`, reread `spec`.

## 路由 — 软规则 + 提交门禁

受管文档的写法由**所在目录 README 的 `## 文档编撰规则 (Document Authoring Rules)` 段**约束，作为**软规则**：编辑时直接读该段并照办，**不注入、不强制**。

提交门禁（结构-only）：`scripts/pre-commit`（已 `git config core.hooksPath scripts`）校验暂存文档所在目录的 README 是否含该锚定段；**破坏结构即拦提交，不验内容**。无 README 或 README 无该段 → 无规则（放行）。

代码侧验证（`k3dge check`）维持不变，保证微观形式/结构正确。`.agent/rules/*` 仍按 ADR 0012 作为协议切片，由本文件点名路径读取。

## 12. Triggers — do in same turn

| Trigger | Action |
| --- | --- |
| Public signature | `k3dge sync` |
| New `src/` domain | `manifest` + `spec` + tests |
| Persistent design | 解析目标路径协议（`k3dge protocol resolve --path <file>`）并遵循之；产物形态由对应协议（如 `adr`）决定 |
| Task done | `Status: done` + `.done.md` |
| Milestone all `done` | `k3dge milestone align` → `HUMAN_CHECKPOINT(60s/N)` → `audit` or `seal` |
| `align` hook | `pipeline.toml` `pipelines.on_align_success` → `peers` `mcp→cli→manual`/`skip`；`pipelines.on_pre_seal` → `k3dit.actions.verify` |
| Guide has `guide-stub` | Fill guide |
| `check` red ×2 | `docs/branches/` then `stash` |
| Audit done | `docs/reviews/` + `SUMMARY` |
| Audit fix done | Backfill `## 回填` to same report + `docs/incidents/INC-YYYYMMDD-<TYPE>-<slug>.md` B-T-D + `SUMMARY` 回填行 |
| Move/delete fact source | Update all pointers; memo target gone → move back |

## 13. Evidence Chain (ADR 0015)

Need 3 links: **产物** (path/cmd output) + **消费者** (engine/check/CI) + **到达** (hardcoded/harness/`AGENTS.md` path). No name/intent.

*Not evidence*: dir name, wish, chat memory. Missing link → "unverified" or ASK.
