# Memo: 未落地的对标项（6 类标准评估小结）

- **类型**：暂无法落地
- **念头**：扫描 `manifest/specs/AGENTS/architecture` 后，对 6 类成熟标准做对标评估——
  已落地 4 项（改一行声明/加一张图即可，零新增门禁逻辑）——2026-09-03 逐个复核落点：`Diátaxis` 显性声明 = `docs/architecture/overview.md:4`；`C4-C1` 上下文图 = 同文件 `:6` 起（`C4Context` mermaid，`:13` 含外部 audit harness 节点）；`Conventional Commits` 门禁 = `scripts/commit-msg:2`（可执行位已置）；`V-model Level` 列 = `docs/specs/cli/spec.md` 第 4 节验证矩阵的 `L0/L1/L2` 列（如 `:74` 行 `TC-CLI-01 | L1`）；
  暂缓 3 项：`ISO 25010` 全量八特性（`k3dge` 现只守功能适合性，其余 7 特性交 `quality` 另 harness）、`12-Factor` 剩余 8 条（`k3dge` 仅 `2 依赖/3 配置/5 构建/10 等价`，全量对标属业务 `VPS` 部署层）、`CITATION.cff` 及 `SLSA` 可重现构建（开源分发阶段再补）
- **触发场景**：在 `docs/architecture/overview.md` 补 `Diátaxis/C4-C1` 后，追问"还有哪些可对标"时提出
- **关联度**：弱相关——属 `harness` 模板的"选配"而非"底线"，业务方按需对表即可
- **Date**: 2026-08-21
- **处置**：不排期为 `tasks`；当首个真实项目需 `ISO 25010` 全量体检或 `12-Factor` 全量部署时，由该项目的 `docs/memo` 提升为 `tasks`（`Status: idea`）
