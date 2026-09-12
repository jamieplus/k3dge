---
status: idea
milestone: M9
priority: P3
date: 2026-09-03
---

# 归档契约落地（去向标记提醒 + 显式 --archive 出口）

- **Status**: idea
- **Milestone**: M9
- **Priority**: P3
- **可检索摘要**: `ADR-0023` §2.2 立了归档三条件，但实测三处 `archive/` 共 106 份 `.md`、带去向标记的 0 份；本任务只补两件小事（增量提醒 + 显式出口），**不含**任何旧编号映射或歧义告警（那条已被 `ADR-0023` §2.3 删除）
- **Date**: 2026-09-03

## 已确认意图

让过期正文"可追溯地退场"，而不是"消失"。范围刻意收窄：上一稿曾包含"让工具读旧号表做重定向"，实测归档语料里旧号引用只有 1 处，而现行文档同号引用 134 处 ⇒ 噪声远大于收益，已连同那张表一起删掉。

## 上下文/切入点（实测）

- 机制已在：`engine/doc_catalog.py:70-78` `iter_managed_files(..., include_archive=False)`；`doc list` / `build_docs_index` / `where` / `search` 默认不吃 `archive/`（`:455` 同）。
- 存量：`docs/{memo,reviews,tasks}/archive/` 共 106 份，`Superseded-by` / `Legacy note` 命中 0 份 ⇒ 提醒必须**只对增量生效**，否则一开就 106 条噪声。
- 出口缺口：`include_archive=True` 只在引擎内部，CLI/MCP 都**没有**显式开关 ⇒ 想考古的人只能自己 `read` 路径（与本仓"不裸 grep docs/"的取向相抵）。

## 落地清单

1. `k3dge doc list --type <t> --archive`：把既有开关透出到 CLI（MCP `k3dge_doc_list` 同步加参数），输出头部明写一行「低权威层：判定以现行视图为准」。不带 `--archive` 时输出必须与今日**逐字节相同**。
2. 增量去向提醒（**非阻断**，`ADR-0021` 同族）：`k3dge doc-audit` 的待核清单里加入"**本轮 diff 新**进 `archive/` 且无 `Superseded-by`/`Legacy note`"的文件；不改 `check` 判定集、不影响退出码（`ADR-0006` §2.3.2：`check` 仍是纯静态硬闸）。
3. 存量 106 份不批量补标记、不批量删除（物理删除需人显式授权）。

## 验收

- `k3dge doc list --type reviews --archive` 列出归档件且带低权威声明；`k3dge doc list --type reviews` 输出与改动前逐字节相同（单测锁死，防默认漂移）。
- 新把一份文档移进 `archive/` 而不写去向 ⇒ 出现在 `k3dge doc-audit` 待核清单；`check` 退出码不变。
- 归档件里的引用规范：正文引归档必须含 `archive/` 段（此条由 k3dit 判，不进闸）。
- `pytest -q` 全绿（基线 202 passed / 1 skipped / 94 subtests）+ `k3dge check --force-full --with-tests` 绿。

## 边界与拆分

- 事实归属：归档成员与去向标记是文档事实；索引默认排除是引擎事实；提醒是非阻断输出。
- 边界检查：提醒不进 `check` 判定集（`ADR-0006` §2.3.2）；只对增量生效（存量 106 份不批量灌噪声）。
- 桩子先行：先造 fixture（一份无标记移入 archive 的文件）断言其入 `doc-audit` 清单且 `check` 退出码不变。

## Related

- 决策：`docs/adr/0023-low-authority-archive-tier.md`（§2.1 不建 legacy 目录；§2.2 三条契约；§2.3 明确删表且不建机器出口）
- 同一批次但不相关：`docs/tasks/2026-09-03-M7-feat-gate_exit_and_trail_checks.md`
