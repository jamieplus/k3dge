# ADR 0006: MCP 是对外 harness 注入面，不是第二套人机 UI

- **Status**: Accepted
- **Date**: 2026-08-24
- **Deciders**: Core Maintainer

## 1. 上下文 (Context)
ADR 0005 把 cli 写成「全部 I/O：终端 + MCP」，容易读成「MCP 是给本仓终端用户的第二套界面」。实际用途是：其它 Agent harness（DSH、Codex、Claude Code、OpenCode 等）通过 MCP stdio 注入，读 k3dge 事实、调 `check`/`sync`/`milestone`，**禁止在那些 harness 里私有重实现门禁**。

## 2. 决策 (Decision)

- **CLI**（`k3dge.cli.main`）：本仓人/脚本的原生入口（shell、pre-commit、CI）。
- **MCP**（`k3dge.cli.mcp`）：对外兼容层。只委托 `engine` / `sync` / `milestone`，零漂移。消费者是外部 harness，不是第二套交互设计。
- 仍放在 `cli` 域（都是传输，不判定）。不新建 mcp 域。
- 透镜审计仍在 `harnesses/audit/`；MCP prompt 只指路，不在桥里演进规程。
- 本机 stdio：信任边界 = 调起该 MCP 的 OS 用户（S-13）。网络化后再重开鉴权。

## 3. 后果 (Consequences)
- 文档与 C4 必须点名「外部 harness 注入」，避免 Agent 把 MCP 当本仓 TUI。
- 给 DSH/Codex/Claude Code/OpenCode 接 k3dge 时，只配 MCP server，不要在那些工具里再写一份 hash 逻辑。
