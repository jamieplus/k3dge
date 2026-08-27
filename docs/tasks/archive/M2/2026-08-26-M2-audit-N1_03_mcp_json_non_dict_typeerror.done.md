# .mcp.json 根为 list/int 时 _ensure_mcp_config 抛未捕 TypeError

- **Status**: done
- **Milestone**: M2
- **Priority**: P1
- **Date**: 2026-08-26

## 已确认意图
.mcp.json 根为 list/int 时 _ensure_mcp_config 抛未捕 TypeError

## 可检索摘要
.mcp.json 根为 list/int 时 _ensure_mcp_config 抛未捕 TypeError 位于 src/k3dge/templates/scaffold.py，需修复后经 k3dge check 与 k3dit 审计验证，确保自包含。

## 上下文/切入点
触发于 k3dit 审计，切入点 src/k3dge/templates/scaffold.py，关联 2026-08-26-M2-audit-N1_03_mcp_json_non_dict_typeerror.done.md
