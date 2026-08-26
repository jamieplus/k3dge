# darwin 上 C:\\ 盘符被当成相对路径

- **Status**: done
- **Milestone**: M1
- **Priority**: P1
- **Date**: 2026-08-25

## 已确认意图
`_require_relative_path` 只拒 `/` 开头和 `Path.is_absolute()`。POSIX 上 `C:\\Windows` / `C:/Windows` 不是绝对路径，会写进 manifest。

## 方案
在现有校验后加盘符检测（如 `^[A-Za-z]:/`）。补测 darwin/linux 上 `C:\\Windows` 必须 `ManifestError`。

## 入口
- `src/k3dge/engine/manifest.py` `_require_relative_path`

## 来源
[docs/reviews/2026-08-25-pass1-robustness-security.md](../reviews/2026-08-25-pass1-robustness-security.md) P1-03
