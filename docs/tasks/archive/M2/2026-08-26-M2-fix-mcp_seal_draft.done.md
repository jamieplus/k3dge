# MCP 封板未读 changelog 草稿致 CLI/MCP 双轨漂移

- **Status**: done
- **Milestone**: M2
- **Priority**: P1
- **Date**: 2026-08-26

## 已确认意图
MCP 的 seal 未读 .agent/changelog_draft.md（或 Unreleased），致 CLI 与 MCP 封板产出不同 CHANGELOG

## 可检索摘要
cli/mcp.py:313 的 seal 仅 f"Seal milestone {id}." 单句，未读 draft 人话，致 CLI 的 seal 含任务清单而 MCP 的 seal 为空壳，双轨漂移；M1 的 CLI/MCP 已同轨为对照

## 上下文/切入点
触发于 M2 的 MCP 封板，切入点 src/k3dge/cli/mcp.py 的 k3dge_milestone_control seal 分支与 src/k3dge/cli/main.py 的 seal
