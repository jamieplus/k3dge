# .mcp.json 损坏/非 dict 时静默覆盖丢 peer 条目，写入非原子

- **Status**: done
- **Milestone**: M2
- **Priority**: P1
- **Date**: 2026-08-26

## 已确认意图
.mcp.json 损坏/非 dict 时静默覆盖丢 peer 条目，写入非原子

## 可检索摘要
.mcp.json 损坏/非 dict 时静默覆盖丢 peer 条目，写入非原子 位于 src/k3dge/templates/scaffold.py，需修复后经 k3dge check 与 k3dit 审计验证，确保自包含。

## 上下文/切入点
触发于 k3dit 审计，切入点 src/k3dge/templates/scaffold.py，关联 2026-08-26-M2-audit-N1_01_mcp_json_corrupt_overwrite.done.md
