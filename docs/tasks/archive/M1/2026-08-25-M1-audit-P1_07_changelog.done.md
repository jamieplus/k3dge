# append_changelog 非原子写

- **Status**: done
- **Milestone**: M1
- **Priority**: P2
- **Date**: 2026-08-25

## 已确认意图
`bump_version` 已先算再写、失败回滚。`append_changelog` 仍直接 `write_text`，中途 `OSError` 可截断 CHANGELOG。

## 方案
写临时文件再 `replace`，或与 bump 同一套 originals 回滚。补测模拟写失败后文件仍完整。

## 入口
- `src/k3dge/engine/version.py` `append_changelog`

## 来源
[docs/reviews/2026-08-25-pass1-robustness-security.md](../reviews/2026-08-25-pass1-robustness-security.md) P1-07
