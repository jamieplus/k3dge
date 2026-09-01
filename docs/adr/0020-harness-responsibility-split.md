---
Status: Accepted
Date: 2026-09-01
Deciders: Core Maintainer
---

# ADR-0020: Harness Responsibility Split (k3dge / k3dit / k3lity)

## 1. 上下文 (Context)

We operate three sibling harnesses: `k3dge` (local-first spec-gate), `k3dit` (audit peer), and `k3lity` (idea/design-quality review). Without an explicit boundary the roles blur — an agent self-audits its own gate work (ADR-0006 sidecar violated), or doc *merit* gets scored as if it were *idea* merit. A 2026-08-31 memo sketched the split; this ADR fixes it as a governance fact source, reinforcing ADR-0005 (layer cuts), ADR-0006 (sidecar), ADR-0018 (managed doc layout), ADR-0019 (no load-proof).

## 2. 决策 (Decision)

Three-harness split (Harness / 审 / 不审 / 硬度 / 时机):

| Harness | 审 | 不审 | 硬度 | 时机 |
|---|---|---|---|---|
| **k3dge** | 形式：哈希、章节、结构枚举 | 写得好不好、定得对不对 | 硬 | 提交时 |
| **k3dit** | 文档文本质量；ADR 集合自洽（冲突/覆盖）；代码是否遵守已商定 ADR | 商定该不该存在、换一种是否更好 | 结构硬；文本质量可勤可硬；冲突偏 CI | 文档变动时 |
| **k3lity** | 商定/实现好不好：复杂度、重复、类型、设计是否过重、ADR 是否值得、有无更简单的做法 | 契约是否漂、文档像不像该类文档 | 必须软 | 里程碑时（对变更文档） |

Key rulings:

- **Code audit and doc audit share the SAME form and the SAME path.** One peer (k3dit) audit, one 12-col report, one `on_pre_seal` verify. `k3dge` exposes a single pointer prompt (`k3dge_5pass_audit_prompt`) that routes by `target_scope`: code → 5-Pass lens, doc → `audit_default.md` Doc Audit section. No separate doc-audit prompt/transport (not a fifth domain, not a sidecar).
- **Doc review ≠ idea scoring.** Doc audit compensates for the text-quality the hard gate cannot catch (ADR-0001 decision: k3dge only verifies "report exists", not merit). "定得对不对 / 有无更简做法" is `k3lity`'s milestone soft review, not doc audit.
- **k3dge doc hard-gating** = per-type `docs/<type>/.schema.json` structure gates (ADR/tasks/incidents/…) via `doc_catalog` — structural only, never merit. ADR conflict/coverage facts come from `k3dge_adr_index` (AdrIndex + O(n) overlap/pointer findings, **non-judgmental**); the conflict/redundancy *judgment* is `k3dit`'s.

## 3. 产生后果 (Consequences)

- **Up**: clean boundary; `k3dge` stays deterministic and structural; semantic review (text quality, ADR conflict judgment, idea worth) lives in `k3dit`/`k3lity`; no self-audit collapse (ADR-0006).
- **Down**: semantic coherence (ADR conflict/coverage, doc text quality) is NOT caught by the `k3dge` gate — it relies on the `k3dit` peer on doc-change and `k3lity` at milestone. That is intentional: the gate is a hard floor, not a semantic judge.
- **Supersedes**: memo `docs/memo/2026-08-31-harness-responsibility-split.md` (archived).
