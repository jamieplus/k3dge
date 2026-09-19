---
Status: Draft
Supersedes: -
Amended-by: -
Landed-by: src/k3dge/engine/<module>.py
Date: YYYY-MM-DD
Deciders: Core Maintainer
Note: -
---

# ADR-NNNN: <title>

<!--
Frontmatter is DATA ONLY (no prose comments — a `#` line inside it is read as an
H1 by naive parsers and corrupts `k3dge doc list` / docs-index titles).

- Append-only after Accepted: revise via the `Amended-by` list
  (`- 🅰<n> | <授权席位> | <日期> | <简述>`) + an inline footnote `[^🅰n.m]` at each
  edited spot. Never rewrite this decision's prose in place.
- Supersede via `Supersedes:` (new ADR only); the gate flips the old one to
  `Status: Superseded` and moves it to `obsolete/` (`adr_gate.reconcile_supersedes`).
- `Landed-by:` is required before Accepted — the seal gate `adr_landed` resolves it.
- `Note:` = non-revision metadata only; default `-`. Revision traces never go here.
- Numbers are never reused. See AUTHORING.md (the single delivery point for these rules).
-->
<!--
Section-number rule (hard-gated by `k3dge check`, code ADR_SECTION_ORDER):
numbered sections must ascend in document order — ## 1, ## 2, ### 2.1, ### 2.1.1, …
Never insert a new subsection out of order or reuse a number.
-->
<!--
Readability (soft; k3dit audits it — docs/adr/AUTHORING.md "人读优先"):
decision-first; one point per line (~100 chars); implementation details (function
names, paths, command sequences) go to docs/specs or tasks; cross-refs at end of
sentence; titles are noun phrases, no slash-stacking.
-->

## 1. 上下文 (Context)

<objective constraints only>

## 2. 决策 (Decision)

<invariants, contracts, explicit non-goals>

## 3. 产生后果 (Consequences)

- **Up**:
- **Down**:
- **Reopen when**:
