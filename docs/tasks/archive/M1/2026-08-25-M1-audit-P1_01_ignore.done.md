# 空 ignore 模式使 is_ignored 崩闸

- **Status**: done
- **Milestone**: M1
- **Priority**: P1
- **Date**: 2026-08-25

## 已确认意图
`ignore` 列表里出现 `""` 时，`Manifest.is_ignored` 调 `Path.match("")` 抛 `ValueError`，`evaluate` 循环里整闸崩溃。空列表 `[]` 已经短路，不在范围。

## 方案
循环里跳过空 pattern；或捕 `ValueError` 当「不匹配」。补测 `ignore=[""]` 时 `evaluate` 记违规或忽略该 pattern，不得 traceback。

## 入口
- `src/k3dge/engine/manifest.py` `is_ignored`
- `tests/unit/engine/`（manifest 或 evaluator）

## 来源
[docs/reviews/2026-08-25-pass1-robustness-security.md](../reviews/2026-08-25-pass1-robustness-security.md) P1-01
