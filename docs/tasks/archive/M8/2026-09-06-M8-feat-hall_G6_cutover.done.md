---
status: done
milestone: M8
priority: P2
date: 2026-09-06
---

# G6: 割接（seal hook/消费侧/k3lity 归档）

- **Status**: done
- **Milestone**: M8
- **Priority**: P2
- **可检索摘要**: seal hook 触发词从双动作改为单 peer+窗参数，pipeline schema/AGENTS 触发表随动，k3lity 仓废留归档；`audit advance` 主权切清（修席窗能力，Hall 只调度）；前置要求 G2 人肉窗全链跑通
- **Date**: 2026-09-06

## Intent

新老切换的唯一割接点。前置：G2 人肉窗全链绿 + **ADR-0025 Accepted**（k3lity 归档不可逆），否则不割。

## Notes

- seal hook：`k3dit.actions.audit`+`k3lity.actions.quality` → 单审计模块动作 + 窗参数；双报告（audit/quality 各一份 12 列）语义保留。
- 消费侧：pipeline schema、`[peers.*]` 声明、AGENTS 触发表、doc-audit 触发词随动。
- `audit advance`：实现搬修席窗，Hall 只调度；Hall 不写消费仓除账本（主权线）。
- k3lity 仓：代码归档（archive/），文档留指针；k3che 不动（独立 peer）。

## 边界与拆分（feat 类必填；规则 08）

- 事实归属：触发词/schema 属 k3dge 消费侧；报告语义属审计模块。
- 边界检查：割接期间双轨并行（老动作名保留 deprecated 一版），不闪断。
- 桩子先行：割接清单即桩——逐项打勾，每项有回滚位。
