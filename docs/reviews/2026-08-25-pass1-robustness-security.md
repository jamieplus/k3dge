# 审计：Pass 1 健壮性与安全（边界/类型/正则/子进程/事务/注入）

- **Date**: 2026-08-25
- **基线**：`70 passed / 1 skipped / 44 subtests / k3dge check --with-tests PASS / 4 域契约已同步`
- **审计人**：Agent（Grok）Pass 1 单透镜 + 人复核
- **范围**：`src/k3dge/engine/*` `src/k3dge/cli/*` `src/k3dge/sync/*` `scripts/*` `tests/*` 全量，透镜仅开健壮性与安全
- **输入**：`docs/memo/2026-08-24-audit-harness-independence.md` 8 维「安全性 + 数据输入」+ Vibe 特检

## 发现

| ID | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P1-01 | 高 | P1 | 缺陷 | `ignore: [""]`（不是空列表）时 `Path.match("")` 抛 `ValueError`，`evaluate` 崩闸 | `manifest.py:90-102` → `evaluator.py:150` | 待修 | [tasks/2026-08-25-M1-audit-P1_01_ignore.md](../tasks/2026-08-25-M1-audit-P1_01_ignore.md) | `ignore=[""]` 才崩；`[]` 已短路 |
| P1-02 | 中 | P1 | 缺陷 | spec / milestone / version 的 `read_text` 未捕 `UnicodeDecodeError`。契约抽取已收成 `_ExtractError`，不是四处均崩 | `evaluator.py` 读 spec；`milestone.py`；`version.py` | 待修 | [tasks/2026-08-25-M1-audit-P1_02_utf8.md](../tasks/2026-08-25-M1-audit-P1_02_utf8.md) | contract 路径已包装 |
| P1-03 | 中 | P1 | 缺陷 | `C:\Windows` 在 darwin 上 `Path.is_absolute()` 为假，相对路径校验绕过 | `manifest.py:17-26` | 待修 | [tasks/2026-08-25-M1-audit-P1_03_Windows.md](../tasks/2026-08-25-M1-audit-P1_03_Windows.md) | POSIX 上盘符不是绝对路径 |
| P1-04 | 中 | P1 | 缺陷 | 路径 NUL 未拒，后续 `Path` 可抛未捕获 `ValueError` | `manifest.py:17-26` | 待修 | [tasks/2026-08-25-M1-audit-P1_04_NUL.md](../tasks/2026-08-25-M1-audit-P1_04_NUL.md) | `_require_relative_path` 无空字节检查 |
| P1-05 | 中 | P1 | 缺陷 | `rglob("*")`+`is_file()` 跟随符号链接，域外 `.py` 可进哈希 | `contract.py:245` | 待修 | [tasks/2026-08-25-M1-audit-P1_05_rglob.md](../tasks/2026-08-25-M1-audit-P1_05_rglob.md) | 未跳过 `is_symlink()` |
| P1-06 | 低 | P2 | 规范 | `K3DGE_BASE_SHA` 未校验即作为 git 修订范围。argv 列表不是 shell 注入 | `diff.py:86-88` | 有意留 | 有意留：本地环境、无 shell。若要收紧，校验 `^[0-9a-fA-F]{4,40}$` 并在 `diff` 参数前加 `--`。何时重开：该变量来自不可信环境 | 参数是 `{sha}...HEAD` 单个 argv |
| P1-07 | 中 | P2 | 缺陷 | `append_changelog` 直接 `write_text`，非原子 | `version.py:191-224` | 待修 | [tasks/2026-08-25-M1-audit-P1_07_changelog.md](../tasks/2026-08-25-M1-audit-P1_07_changelog.md) | `bump_version` 已有回滚，changelog 没有 |
| P1-08 | 低 | P2 | 缺陷 | `parse_version` 用 `int()`，`1.-2.3` 被接受 | `version.py:47-51` | 待修 | [tasks/2026-08-25-M1-audit-P1_08_SemVer.md](../tasks/2026-08-25-M1-audit-P1_08_SemVer.md) | `int("-2")== -2` |
| P1-09 | 低 | P2 | 规范 | `test_command_template` 未白名单 | `evaluator.py:43` | 有意留 | 有意留：能改 manifest 的人已能改测试命令（同 S-13 信任面） | 本地可控 |

> `A-11/S-13` 已判有意留不重开；13 正则均无 ReDoS（`[^\n\r]+` 有界，1MB <15ms）。

## 结论

Pass 1：7 项转 M1 tasks（P1-01/02/03/04/05/07/08），2 项有意留（P1-06 非 shell 注入、P1-09 manifest 信任面）。P1-02 已降级：不是四处均崩。

## 验证

- `70 passed / 1 skipped` 基线绿
- `k3dge check` 对应 `TEMPLATE_DRIFT` 等已验
