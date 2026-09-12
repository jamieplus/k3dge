---
status: done
milestone: M8
priority: P0
date: 2026-09-06
---

# G3b: CLI root 白名单能力实测（W1 前置探测）

- **Status**: done
- **Milestone**: M8
- **Priority**: P0
- **可检索摘要**: W1 墙依赖"agent cli 原生访问控制（deny-by-default + root 限定）"，但 pi/claude/codex 的 root 限定能力均未验证——若全系无此能力，W1 需改用容器/namespace 方案；这是唯一可能推翻方案的探测项，故 P0 先行
- **Date**: 2026-09-06

## Intent

在 G3 开工前钉死答案：pi / claude / codex / opencode 四宿主，谁能把 agent 锁进专属目录（根外拒绝、无审批旁路）。

## Notes

- 已知：opencode 默认沙箱拒读仓外目录（`../k3dit/src/k3dit/seats.py:36` note 有实测）；pi 有 `--session-id` 但 root 限定未验。
- 输出矩阵：宿主 ×（root 限定有无 / 绕过路径有无 / 配置形状）。
- 若全否 → G3 改方案（容器或 userns 隔离），W1 条款回 ADR-0025 修订；若部分有 → G3 先做有的两宿主。

## 边界与拆分（feat 类必填；规则 08）

- 事实归属：宿主 CLI 能力矩阵属本 task 产物；隔离机制选型属 ADR-0025。
- 边界检查：纯观测，不碰任何仓代码。
- 桩子先行：矩阵表即交付物；无代码。
