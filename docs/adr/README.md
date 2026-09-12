# Architecture Decision Records (ADR)

k3dge 的架构决策记录。每条是一次取舍的单一事实源：只记决策与权衡，不记过程。

- **Address**: `k3dge doc list --type adr` / `k3dge doc where ADR-0001`. Do not grep `docs/adr/`.
- **Write**: read [`AUTHORING.md`](AUTHORING.md); copy [`_template.md`](_template.md). Do not invent a skeleton.

**Before creating a new ADR, prefer folding into an existing one of the same class**（见 AUTHORING「先并入，后新建」）. Entries are append-only after Accepted. Revise via `Amended by` / `Superseded by`. Physical delete only with explicit human authorization. Numbers are never reused.

## Topics

- **Gate / baseline**: 0001, 0014
- **Docs**: 0003, 0018, 0019, 0023, 0024
- **Lifecycle**: 0004, 0008, 0021, 0022
- **Agent / harness**: 0005, 0006, 0009, 0010, 0012, 0025
- **Bootstrap / version**: 0015
- **Audit report schema**: 0017
