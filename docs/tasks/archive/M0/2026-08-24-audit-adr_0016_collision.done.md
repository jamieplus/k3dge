# 两份 ADR 都叫 0016：版本决策无法唯一引用

- **Status**: done
- **Milestone**: M0
- **Priority**: P1
- **Date**: 2026-08-24

## 已确认意图
审计 U-01：`docs/adr/0016-living-doc-relocation.md` 与 `docs/adr/0016-version-and-changelog.md` 撞号。overview §5 只登记了活文档接续。

## 方案
把版本那份改号为 **0017**（或下一空号），所有引用一起改；在 overview §5 加版本单源/seal bump 一行。禁止再手写已占用的 ADR 号。

## 入口
- `docs/adr/0016-version-and-changelog.md`
- `docs/architecture/overview.md` §5
- `docs/guides/changelog.md`

## 来源
[docs/reviews/2026-08-24-post-update-8dim.md](../reviews/2026-08-24-post-update-8dim.md) U-01
