# Memo: Mastra Observational Memory 与 k3dge 的互补定位

- **类型**：模糊概念（in-scope 但暂无落地实现，属上层 Agent Harness 选配能力）
- **念头**：Mastra 的 Observational Memory（结构化内存/向量库/Observer 异步管道）与 `k3dge` 的文件系统物理档案（`docs/tasks|branches|memo` + `milestone seal` 压缩）高度互补，但必须严格分层：`k3dge` 守 100% 确定性门禁（AST/SHA-256/正则状态机，`src/k3dge/engine` 与 `scripts/gate.*` 零 LLM 依赖），Mastra 仅作为上层认知编排层的观测提炼器，通过 MCP 零漂移桥接（`src/k3dge/cli/mcp.py` 的 `spec://manifest` + `k3dge_check`）读事实、写回 `docs/*`。增益场景：1) 监听 `GateReport.violations` 自动提炼 `假设→失败→避坑` 生成 `docs/branches/` 负记忆，闭合 `AGENTS.md §7` 人治盲区；2) 长周期积累观察流，在 `milestone align` 时注入验收报告摘要；3) 充当 5-Pass 轮间高密度观察板，Pass 1 边界发现以 Observation 挂载供 Pass 3/5 关联，避免全量重读污染。衰减语义与物理封板解耦：滚动衰减 ≠ `seal` 压缩，观测须经 `align` 对齐 + 三闸机硬拦才归档。
- **触发场景**：用户在 MCP 零漂移桥接（`cli/mcp.py`）与 5-Pass 全绿审计后，提交外部参考 `https://mastra.ai/docs/memory/observational-memory` 并给出分工矩阵，要求评估是否下沉侵入底层门禁
- **关联度**：强相关但上层——属 `k3dge[mcp]` 同级的可选 Harness 插件，不进 `pyproject.toml` 必选依赖
- **Date**: 2026-08-23
- **处置**：仅 memo 存档，不建 `tasks`；当首个基于 Mastra/Claude Code 的真实项目需自动化 `branches` 归档或 `align` 摘要注入时，由该项目的 `docs/tasks` 晋升（`Status: idea`，附 MCP 调用示例），原 memo 移入 `archive/`；`src/k3dge/engine` 保持零依赖防线不变
- **原文锚点**：用户提交的对比矩阵与三增益场景全文见本 memo 创建时对话快照（`#8d4m2-a5`），未来晋升时以本文件 + `cli/mcp.py` 接口清单为事实源
