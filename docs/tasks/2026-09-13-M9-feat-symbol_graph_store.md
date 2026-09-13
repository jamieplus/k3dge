---
status: idea
milestone: M9
priority: P2
date: 2026-09-13
---

# 符号/边图 + FTS（stdlib sqlite3，升 symbol-index.json）

- **Status**: idea
- **Milestone**: M9
- **Priority**: P2
- **可检索摘要**: 把扁平 `docs/generated/symbol-index.json` 升为**符号/边图 + FTS**（stdlib `sqlite3`，不破零依赖），供 search/where/impact；并吸收 codegraph 的 staleness 点名模式。来源 memo §1。
- **Date**: 2026-09-13

## Intent
更大的代码图存储（symbols/edges/files + 全文检索），零依赖可行。

## 上下文/切入点
- 现状：`engine/search.py`/`doc_catalog` 用扁平 JSON 索引 + ripgrep；`import_graph` 出边。
- 约束：**零依赖**——`sqlite3` 属 Python 标准库，可用；不引第三方（不引 codegraph 本体）。

## 边界与拆分
- 事实归属：索引/图＝k3dge 确定性工具面；judgment 不进。
- 边界检查：SQLite 仅本地生成物（`docs/generated/`），可重建；缺则回落现路径。
- 桩子先行：先建 symbols/edges 两表 + FTS，`where`/`search` 切读源，再谈 impact。

## 验收
- 索引可重建、与现 `symbol-index.json` 等价或更全；`check` 的 `DOC_INDEX_STALE` 同源点名 pending；零依赖。
