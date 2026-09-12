---
status: idea
milestone: M9
priority: P1
date: 2026-09-12
---

# next-hook 引导 / 渐进披露落地（ADR-0008 §2）

- **Status**: idea
- **Milestone**: M9
- **Priority**: P1
- **可检索摘要**: 按 ADR-0008 §2「渐进披露」实现——`[NEXT]` 只推最小下一步+指针，纵深按需；默认摘要、`--deep`/`--json` 取全量；守预算。
- **Date**: 2026-09-12

## Intent

把"推送式灌上下文"改成"拉取式"：状态机每条边只给下一步与纵深指针，实现已有契约（ADR-0008 §2）。

## 上下文/切入点

- 已有半成品：`engine/nextstep.py` 出 `[NEXT] state=… ask/if_y/if_n/note`（＝引导边）。
- 待做：
  - `[NEXT]` 增 `pointers[]`（doc id / ADR 节 / 命令），`note` 由散文改指针。
  - 命令默认摘要，全量藏 `--json`/`--all`；人用 `--deep` 看全景可下钻。
  - `AGENTS.md` 微核预算（≤~80 行，模板已有 WARN）；命令 stdout 默认上限。
  - 度量：每条命令上下文行数、被加载 doc 数 vs 需要数、往返次数。

## 边界与拆分（规则 08）

- 事实归属：契约/文案＝ADR-0008 + 硬闸契约（数值）；执行＝`engine/nextstep.py` 与各命令。
- 边界检查：`nextstep` 只出"边+指针"，不承载纵深内容（内容留在被指的 doc）。
- 桩子先行：先给 `[NEXT]` 加 `pointers`（行为兼容），再逐状态把 `note` 散文降为指针，最后上预算检查。
