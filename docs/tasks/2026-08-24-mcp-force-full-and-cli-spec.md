# 让 MCP `force_full` 真正跑 Full Matrix，并补齐 cli spec / TC

- **Status**: done
- **Priority**: P1
- **Date**: 2026-08-24
- **来源**：[docs/reviews/2026-08-24-5pass-audit.md](../reviews/2026-08-24-5pass-audit.md) A-02 / A-09

## 可检索摘要
`k3dge_check(..., force_full=True)` 目前只把该开关 OR 进 `ConsistencyEngine.evaluate(run_tests=...)`，评估范围仍是 git 增量触及的域。`docs/guides/mcp-bridge.md` 却写「触发全量门禁」。Agent 经 MCP 会误以为已做里程碑级 Full Matrix。同时 `docs/specs/cli/spec.md` In Scope 仍只列 `check`/`sync`，公共接口已含 `cmd_milestone` 与 `mcp.py` 六个符号，且 MCP 无 Verification Matrix TC、无单测。

## 上下文/切入点
- 实现：`src/k3dge/cli/mcp.py` `k3dge_check`（约第 92–116 行）
- 文档：`docs/guides/mcp-bridge.md` 能力表第 3 行；`docs/specs/cli/spec.md` §1 In Scope、§4 矩阵
- 对照事实源：ADR 0004 的 Full Matrix 实际在 `k3dge.engine.milestone.run_milestone_alignment`，不在 `k3dge check --with-tests`（那是 selective L2）
- 相关：若 A-03 先把 align 抽成可复用的全域校验，MCP `force_full` 应委托它，而不是再复制一份

## 方案
1. 明确语义（二选一，推荐 a）：
   - (a) `force_full=True` 对所有 `manifest.domains` 做结构+契约校验，`with_tests` 仍控制是否跑测试；与 git diff 解耦。
   - (b) 删除 `force_full` 参数（破坏 MCP 契约，需 `k3dge sync`），只保留 `with_tests`，并改正指南措辞。
2. 更新 `docs/guides/mcp-bridge.md`，禁止「全量门禁」与 `--with-tests` 混用。
3. `cli` spec：In Scope 补 milestone 路由与 MCP 桥接；矩阵加 TC-CLI-03（`force_full` 行为）与 MCP 资源/工具冒烟。
4. 为 `k3dge_check` / `_find_workspace` 加单元测试（不依赖真实 MCP 包，走现有 DummyMCP 路径即可）。

## 触发条件
用户确认本方案后改为 `in-progress`。公开签名若删改 `force_full` 必须同任务 `k3dge sync`。
