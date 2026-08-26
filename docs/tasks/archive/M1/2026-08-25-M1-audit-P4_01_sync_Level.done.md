# sync spec 矩阵缺 Level 列

- **Status**: done
- **Milestone**: M1
- **Priority**: P1
- **Date**: 2026-08-25

## 已确认意图
`docs/specs/sync/spec.md` Verification Matrix 无 `Level` 列，与 `_template` 及 engine/cli/templates 不一致。`validate_structure` 不验列头，门禁不红。

## 方案
给现有 TC-SYNC 行补 `Level`（建议 L1）。哈希只锁接口块，改表头不必 sync，除非误改接口区。

## 入口
- `docs/specs/sync/spec.md` §4

## 来源
[docs/reviews/2026-08-25-pass4-consistency-alignment.md](../reviews/2026-08-25-pass4-consistency-alignment.md) P4-01
