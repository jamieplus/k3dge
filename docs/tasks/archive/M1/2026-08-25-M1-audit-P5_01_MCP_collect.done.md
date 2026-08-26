# MCP verify 后再 collect，同一域解析两遍

- **Status**: done
- **Milestone**: M1
- **Priority**: P2
- **Date**: 2026-08-25

## 已确认意图
`k3dge_verify_domain_contract` 调 `verify_contract`（内部已 `collect_domain_interface`）再 `collect` 一次取展示接口。域小则毫秒级，但是重复。

## 方案
`verify_contract` 顺带返回 interface，或 MCP 只 collect 一次再本地哈希比对 spec。行为与现 JSON 字段兼容。补测调用次数。

## 入口
- `src/k3dge/cli/mcp.py` `k3dge_verify_domain_contract`
- `src/k3dge/engine/contract.py` `verify_contract`（若改返回值须 sync）

## 来源
[docs/reviews/2026-08-25-pass5-simplicity-performance.md](../reviews/2026-08-25-pass5-simplicity-performance.md) P5-01
