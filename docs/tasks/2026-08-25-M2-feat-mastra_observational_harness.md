# Mastra Observational Memory 上层 harness 落地

- **Status**: idea
- **Milestone**: M2
- **Priority**: P2
- **Date**: 2026-08-25

## 已确认意图
将 `docs/memo/2026-08-23-mastra-observational.md` 的三增益（`branches` 负记忆/`align` 摘要/`5-Pass` 轮间板）落为可验证的上层 harness，不侵入 `src/k3dge/engine`。

## 方案

1. **形态**：`k3dit` 或独立 `k3cache` 仓（`ADR 0008` 并列），`Mastra` 为可选 `Observer` 运行时，`k3dge` 侧仅暴露 `spec://manifest` + `k3dge_check`（`cli/mcp.py:1`）事实源，不新增 `engine` 依赖
2. **触发**：
   - `branches` 负记忆：监听 `k3dge check` 的 `GateReport.violations`（`models.py:22`），`Observer` 异步提炼 `假设→失败→避坑` 四段式，写 `docs/branches/YYYY-MM-DD-<slug>.md`（`AGENTS.md §7`），`k3dge check` 红时 `Observer` 先写再 `stash` 前校验
   - `align` 摘要：`milestone align` 成功后，`Observer` 将滚动窗口的架构/接口观察注入 `docs/reviews/YYYY-MM-DD-<id>-align.md` 的"交付事实摘要"段
   - `5-Pass` 轮间板：`Pass 1` 的 `Observations` 以极简 `ID|Observation` 挂载供 `Pass 3/5` 读，不重读全量对话
3. **存储**：`Mastra` 侧 `memory` 选 `vector store`（`mastra.ai/docs/memory/observational-memory`），`k3dge` 侧仅 `docs/*` 落盘，衰减语义≠`seal` 压缩，观测经 `align` 对齐后才归档
4. **失败界**：`Observer` 提炼错误由 `docs/reviews` 人审回滚（`有意留: 误提炼`），不污染 `k3dge` 门禁；`k3dge` 的 `archive` 压缩仍以 `seal` 三闸机为准，去重由 `SUMMARY.md` 索引
5. **验证**：`k3dit` 对 `k3dge` 跑一轮 `Observer` → `branches` 自动落盘 1 篇 + `M1` 对齐报告含摘要行，`k3dge check` 仍 `PASS`

## 入口
- `docs/memo/2026-08-23-mastra-observational.md`
- `src/k3dge/cli/mcp.py` `k3dge_check`
- `src/k3dge/engine/models.py` `GateReport`

## 来源
`docs/memo/2026-08-23-mastra-observational.md` + `ADR 0008` 并列 harness 分工
