---
status: done
milestone: M10
priority: P2
date: 2026-09-14
---

# engine 解耦：门面不再当总线 + 闸核禁依赖生命周期 + mcp.json 单读取器

- **可检索摘要**: engine 内部直 import 叶子；闸核不得 import 生命周期；`.mcp.json` 读取归 `mcp_json`

## 已确认意图
按导入图三刀：① `milestone.py` 只给 CLI/测试做兼容门面，engine 内部走叶子；② 闸核 `evaluate` 及其检查不得 import 写盘/出向路径；③ `.mcp.json` 读取进无 MCP 客户端的 `engine/mcp_json.py`（templates 孤岛仍自解析，ADR-0001）。

## 边界与拆分
- 事实归属：指针→`milestone_pointer`；任务→`task_index`/`task_write`；报告→`audit_report`；endpoint 表→`mcp_json`；闸核只出 `Violation`。
- 边界检查：不拆第五域；CLI 可继续走门面；templates 不 import engine。
- 桩子先行：先加闸核 import 不变量测试，再改 import。
