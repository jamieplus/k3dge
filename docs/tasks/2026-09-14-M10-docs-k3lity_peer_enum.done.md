---
status: done
milestone: M10
priority: P2
date: 2026-09-14
---

# 清活协议面：去掉 k3lity 点名与 4-peers 枚举，改按 pipeline.toml 角色路由

- **可检索摘要**: 活协议面不再枚举实现仓；吸收/降级纪律只指向 `pipeline.toml` `[roles.*]`

## 已确认意图
Agent 还当真话读的面（rules / 模板 / CLI help / 有意留 / 现行 guide+contract）去掉 k3lity 点名和「4 peers」枚举。路由进已声明角色，不在散文里写死 bind 实现。ADR/incident/归档报告作决策史保留。

## 边界与拆分
- 事实归属：角色集合归 `pipeline.toml` `[roles.*]`；bind 实现名只出现在那一行。
- 边界检查：本票不改出向行为、不删 `--kind quality` 对旧报告的读取、不改 ADR 正文。
- 桩子先行：不适用（措辞/注释/help）。

## 结案

- 关闭提交：`ebaff64`（2026-09-18）
- 落地记录：见该提交 message 与本文正文（回填于 2026-09-19，事实取自 `git log --diff-filter=AR -1 -- <path>`）。
