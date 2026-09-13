---
status: done
milestone: M9
priority: P3
date: 2026-09-12
---

# WikiSkill 残项入 ADR 层：W1 隔离实证 + PURPOSE 回指惯例

- **Status**: done
- **Milestone**: M9
- **Priority**: P3
- **可检索摘要**: ①把 WikiSkill 论文 ablation（执行席开 wiki → 准确率 63.7%→60.9%）引为 ADR-0025 W1（执行席只读当轮材料）依据 + Reopen 反向证据；②落 §3 PURPOSE 回指惯例（重大透镜修订在 ADR Decision 写缘起 pattern）。
- **Date**: 2026-09-12

## 意图
给 W1 隔离补"对照实验数字"依据（我方此前只有论证）；并立 **PURPOSE 回指**惯例——重大透镜修订在 ADR Decision 写驱动它的 pattern（并入既有 ADR 惯例，不新增机制）。

## 来源/证据
- memo `docs/memo/archive/2026-09-06-wikiskill-absorption-eval.md` §2、§1.3、§3。
- ADR-0025 §2.3 W1；`docs/adr/AUTHORING.md`。

## 边界
只补依据/Reopen 反向证据与惯例；**不改 W1 决策、不新增机制**。

## 收尾（2026-09-13 已落）
- ADR-0025 追加 **Note ㉘**：① WikiSkill ablation（arXiv:2608.27454 Table 3，63.7%→60.9%）为 W1 第三方依据；② §3 Reopen 补反向条件（放开隔离须先复现并推翻该 ablation）；③ 立 PURPOSE 回指惯例。
- `docs/adr/AUTHORING.md` 人读优先节增「**缘起回指（PURPOSE）**」惯例。
- 未改 W1 决策、未新增机制。
