# Memo: 代码质量与全局优化不归本 harness

- **闪念**：Agent 常陷局部最优、缺全局视野致系统优化不足、重构差；不同 Agent 能力不一，有的堆大量共线性判断与冗余逻辑
- **触发场景**：讨论"本 harness 能否解决"时提出（`docs/architecture/overview.md` 补全后）
- **关联度**：与本系统弱相关——属**质量/优化层**，非一致性层
- **结论**：`k3dge` 只守"一致性"（接口契约漂移），不评"优劣性"。过度逻辑与全局重构应由**另 harness**并联处理；硬塞进 `k3dge` 会因误伤被 `--no-verify` 绕过，反丢底线。`manifest` + `architecture` 已提供全局视野材料，使质量闸有据可依。
- **Date**: 2026-08-21

## Agent 给出的质量 Harness 构建方案

**定位**：与 `k3dge` 并联的独立质量门禁，不塞进同一 harness。

**三闸分层**：
- L1 `k3dge`（一致性）：接口契约漂移（已落地）
- L2 `quality`（简洁性）：过度逻辑、冗余、圈复杂度
- L3 `review`（全局最优）：跨域重构与架构优化，需人或 reviewer Agent

**选型（零/低依赖，pre-commit 直连）**：
- `ruff --select C901`：lint + 圈复杂度
- `mypy --strict`：类型收口，间接抑制堆砌判断
- `radon cc -a 10` / `jscpd`：复杂度与重复度阈值

**门禁形态**：
- `.pre-commit-config.yaml` 另起一 hook `quality`，与 `k3dge-check` 并列（`always_run`）
- 阈值先宽后严（如 `radon < 15` 起步），避免首日即 `--no-verify`

**防能力差异**：提示词"写能过 spec 的最简实现" + 硬门禁兜底；强的被闸逼简，弱的被闸拦冗余。

**落地步骤**：`pip install ruff mypy radon -e .[dev]` → 加 `quality` hook → 本地调阈值 → CI 与 `k3dge check` 并列 required。
