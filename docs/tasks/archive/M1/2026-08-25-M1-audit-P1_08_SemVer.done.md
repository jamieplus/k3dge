# parse_version 接受负数分量

- **Status**: done
- **Milestone**: M1
- **Priority**: P2
- **Date**: 2026-08-25

## 已确认意图
`parse_version` 用 `int()`，`1.-2.3` 会得到 `(1, -2, 3)`。

## 方案
分量须 `>= 0`，或整串匹配 `^\\d+\\.\\d+\\.\\d+$`（可带可选 `v` 前缀）。补测负数/非数字拒绝。

## 入口
- `src/k3dge/engine/version.py` `parse_version`

## 来源
[docs/reviews/2026-08-25-pass1-robustness-security.md](../reviews/2026-08-25-pass1-robustness-security.md) P1-08
