# MCP 审计 prompt 仍只指向不存在的 k3dit protocol

- **Status**: done
- **Milestone**: M0
- **Priority**: P2
- **Date**: 2026-08-24

## 已确认意图
审计 U-07。`k3dge_5pass_audit_prompt` 与 `docs/guides/mcp-bridge.md` 仍写 `k3dit/docs/guides/protocol.md`。AGENTS.md / README 已回退到顶层 memo。违反 ADR 0016（删活文档后同轮改所有指针）。

## 方案
与 AGENTS.md §9 同一句话：优先 k3dit protocol，否则 `docs/memo/2026-08-24-audit-harness-independence.md`。

## 入口
- `src/k3dge/cli/mcp.py`
- `docs/guides/mcp-bridge.md`

## 来源
[docs/reviews/2026-08-24-post-update-8dim.md](../reviews/2026-08-24-post-update-8dim.md) U-07
