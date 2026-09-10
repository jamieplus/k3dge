---
Status: Accepted
# Append-only after Accepted. Revise via `Amended by` / `Superseded by` below — do
# NOT rewrite this decision's prose in place, and never reuse a number (see README).
Supersedes: -
Amended-by: ADR-0025
Date: 2026-09-01
Deciders: Core Maintainer
Note: ① 2026-09-10 经 Core Maintainer 本轮显式授权，加 `Amended-by: ADR-0025`（三 harness 划分让位于合并审计模块；本 ADR 的边界裁决仍有效），依 `docs/adr/AUTHORING.md`；过闸口径 = manual fallback（实测 `command -v k3dit`/`k3dge` 无输出，no live lens）。
      ② 人读化改写（按 AUTHORING「人读优先」：决策先行、一行一点、长条拆子项；不变量与编号不变）2026-09-10，经 Core Maintainer 本轮显式授权，依 `docs/adr/AUTHORING.md`；过闸口径同上。
---

# ADR-0020: Harness Responsibility Split (k3dge / k3dit / k3lity)

> **Amended by ADR-0025**: k3dit / k3lity 作为独立 harness 的历史来源消失，audit+quality 合并为一个审计模块（同屋檐、多窗多席）。
> 下表与"three sibling harnesses"按历史记录保留；冲突处以 ADR-0025 为准。
> doc review ≠ idea scoring、k3dge 只做结构硬闸等边界裁决仍有效。

## 1. 上下文 (Context)

- We operate three sibling harnesses:
  - `k3dge` (local-first spec-gate), `k3dit` (audit peer), `k3lity` (idea/design-quality review).
- Without an explicit boundary the roles blur:
  - an agent self-audits its own gate work (ADR-0006 sidecar violated);
  - doc *merit* gets scored as if it were *idea* merit.
- A 2026-08-31 memo sketched the split; this ADR fixes it as a governance fact source.
  - It reinforces four rulings:
    - layer cuts (ADR-0005), sidecar (ADR-0006);
    - managed doc layout (ADR-0018), no load-proof (ADR-0019).

## 2. 决策 (Decision)

Three-harness split (Harness / 审 / 不审 / 硬度 / 时机):

| Harness | 审 | 不审 | 硬度 | 时机 |
|---|---|---|---|---|
| **k3dge** | 形式：哈希、章节、结构枚举 | 写得好不好、定得对不对 | 硬 | 提交时 |
| **k3dit** | 文档文本质量；ADR 集合自洽（冲突/覆盖）；代码是否遵守已商定 ADR | 商定该不该存在、换一种是否更好 | 结构硬；文本质量可勤可硬；冲突偏 CI | 文档变动时 |
| **k3lity** | 商定/实现好不好：复杂度、重复、类型、设计是否过重、ADR 是否值得、有无更简单的做法 | 契约是否漂、文档像不像该类文档 | 必须软 | 里程碑时（对变更文档） |

Key rulings:

- **Code audit and doc audit share the SAME form and the SAME path.**
  - One peer (k3dit) audit, one 12-col report, one `on_pre_seal` verify.
  - `k3dge` exposes a single pointer prompt (`k3dge_5pass_audit_prompt`).
    - It routes by `target_scope`: code → 5-Pass lens; doc → `audit_default.md` Doc Audit section.
  - No separate doc-audit prompt/transport (not a fifth domain, not a sidecar).
- **Doc review ≠ idea scoring.**
  - Doc audit compensates for the text-quality the hard gate cannot catch.
    - k3dge only verifies "report exists", not merit (ADR-0001 decision).
  - "定得对不对 / 有无更简做法" is `k3lity`'s milestone soft review, not doc audit.
- **k3dge doc hard-gating** = per-type `docs/<type>/.schema.json` structure gates.
  - Gates run via `doc_catalog`; scope ADR/tasks/incidents/…; structural only, never merit.
  - ADR conflict/coverage facts come from `k3dge_adr_index`.
    - AdrIndex + O(n) overlap/pointer findings, **non-judgmental**.
    - The conflict/redundancy *judgment* is `k3dit`'s.

## 3. 产生后果 (Consequences)

- **Up**: clean boundary.
  - `k3dge` stays deterministic and structural.
  - Semantic review lives in `k3dit`/`k3lity` (text quality, ADR conflict judgment, idea worth).
  - No self-audit collapse (ADR-0006).
- **Down**: the `k3dge` gate does NOT catch semantic coherence.
  - Semantic coherence = ADR conflict/coverage + doc text quality.
  - It relies on the `k3dit` peer on doc-change and `k3lity` at milestone; that is intentional.
  - The gate is a hard floor, not a semantic judge.
- **Supersedes**: memo `docs/memo/2026-08-31-harness-responsibility-split.md` (archived).
