# Architecture Decision Records (ADR)

k3dge 的架构决策记录。每条是一次取舍的单一事实源：只记决策与权衡，不记过程。

- **Address**: `k3dge doc list --type adr` / `k3dge doc where ADR-0001`. Do not grep `docs/adr/`.
- **Write**: read [`AUTHORING.md`](AUTHORING.md); copy [`_template.md`](_template.md). Do not invent a skeleton.
- **Rules**: 修订/取代/编号/归档的规则一律以 [`AUTHORING.md`](AUTHORING.md) 为准（唯一投递点，本文件不复述）。
- **Retired**: `Superseded` / `Rejected` 由闸自动移入 [`obsolete/`](obsolete/)（`adr_gate.reconcile_supersedes`）；编号永久退役，不再分配。

## Topics

- **Gate / baseline**: 0001
- **Docs**: 0018, 0023
- **Lifecycle**: 0004, 0008, 0022
- **Agent / harness**: 0005, 0006, 0009, 0010, 0012, 0025, 0026
- **Audit report schema**: 0017
