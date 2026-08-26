# TC-ENG-06 写了不存在的 VERSION_MISSING

- **Status**: done
- **Milestone**: M1
- **Priority**: P1
- **Date**: 2026-08-25

## 已确认意图
矩阵写 `VERSION_MISMATCH`/`VERSION_MISSING`。代码只产 `VERSION_MISMATCH`；两边都没有 version 时 `validate_versions` 返回空（下游无 pyproject 正常）。

## 方案
采用 (a)：spec 只写 `VERSION_MISMATCH`，并注明 canonical 全缺不阻断。不要发明 `VERSION_MISSING` 规则。

## 入口
- `docs/specs/engine/spec.md` TC-ENG-06

## 来源
[docs/reviews/2026-08-25-pass4-consistency-alignment.md](../reviews/2026-08-25-pass4-consistency-alignment.md) P4-02
