# Architecture Decision Records (ADR)

k3dge 的架构决策记录。每条是一次取舍的单一事实源：只记决策与权衡，不记过程。

- **Address**: `k3dge doc list --type adr` / `k3dge doc where ADR-0001`. Do not grep `docs/adr/`.
- **Write**: read [`AUTHORING.md`](AUTHORING.md); copy [`_template.md`](_template.md). Do not invent a skeleton.

Entries are append-only after Accepted. Revise via `Amended by` / `Superseded by`. Physical delete only with explicit human authorization. Numbers are never reused.

## Topics

- **Gate / baseline**: 0001, 0014
- **Docs**: 0002, 0003, 0018, 0019
- **Lifecycle**: 0004, 0008, 0021, 0022
- **Agent / harness**: 0005, 0006, 0009, 0010, 0011, 0012
- **Bootstrap / version**: 0007, 0013, 0015, 0016
- **Audit report schema**: 0017

## Legacy numbers

Archived reviews/tasks/memos may still cite old ids. Numbers are never reused.

| Old | Now | Note |
| --- | --- | --- |
| 0008 | 0006 | sibling harnesses merged into 0006 |
| 0009 | 0008 | renumber (Triggered Doc Maintenance) |
| 0010 | 0008 | settled-design merged into 0008 |
| 0011 | 0009 | renumber (Purpose) |
| 0012 | 0010 | renumber (Agent Rules) |
| 0013 | 0011 | self-description merged into 0011 |
| 0014 | 0011 | renumber (Agent Dir) |
| 0015 | 0012 | renumber (Evidence Chain) |
| 0016 | 0018 | living-doc relocation merged into 0018 |
| 0017 | 0013 | renumber (Version) |
| 0018 | 0014 | renumber (Template Drift) |
| 0019 | 0015 | renumber (Downstream-First) |
| 0020 | 0016 | renumber (Pattern Absorption) |
| 0021 | 0017 | renumber (Report Schema) |
| 0022 | 0019 | load-proof abandoned, recorded in 0019 |
| 0023 | 0018 | renumber then merged into layout ADR |
| 0024 | 0019 | renumber (Load-Proof Abandoned) |
