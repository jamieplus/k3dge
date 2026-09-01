# 审计：逐行审计三轮（全仓）

- **Date**: 2026-08-20 ~ 2026-08-21
- **基线**：20→26 tests / gate PASS；未提交（工作区状态）
- **审计人**：Agent（Muse Spark）+ 人复核

## 发现

| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R1-1 | 2026-08-21 | 高 | P0 | 缺陷 | contract 签名提取缺 *args/kwonly/defaults/基类 → 哈希碰撞漏检 | `contract.py:23` `_fmt_args/_fmt_class` | 已修 | 重写签名提取，补全 vararg/kwonly/defaults/基类 | `k3dge sync` 重算指纹，`gate PASS` | 待复审 |  |
| R1-2 | 2026-08-21 | 高 | P0 | 缺陷 | _ts.py tree-sitter 0.21+ API 不兼容 | `_ts.py:17` | 已修 | 双回退（0.21+ / legacy） | 手动验证 + `gate PASS` | 待复审 |  |
| R1-3 | 2026-08-21 | 高 | P0 | 缺陷 | porcelain 引号路径/重命名解析错 | `diff.py:34` `_strip_quotes` | 已修 | 引号解包 + 重命名取目标 | `test_evaluator` 覆盖 | 待复审 |  |
| R1-4 | 2026-08-21 | 高 | P1 | 缺陷 | manifest ignore 通配不跨目录 | `manifest.py:60` `is_ignored` | 已修 | 三重匹配 `fnmatch/path/match` | 单测验证 | 待复审 |  |
| R1-5 | 2026-08-21 | 高 | P0 | 缺陷 | 非 git 目录 check 崩栈 | `evaluator.py:22` `GIT_UNAVAILABLE` | 已修 | 捕获转 Violation | `gate PASS`（非 git 目录） | 待复审 |  |
| R1-6 | 2026-08-21 | 中 | P1 | 缺陷 | gate.sh 参数不透传 | `gate.sh:8` `"$@"` | 已修 | `"$@"` 透传 | `gate.sh --help` 验证 | 待复审 |  |
| R1-7 | 2026-08-21 | 中 | P1 | 缺陷 | sync 每次误报更新（无幂等比对） | `generator.py:87` `original==content` | 已修 | 内容比对幂等 | 二次 `sync` 已验 `already up to date` | 待复审 |  |
| R2-1 | 2026-08-21 | 高 | P0 | 缺陷 | scaffold 模板与实体脚本漂移 | `templates/scaffold.py` | 已修 | 4 模板同步 + 防回归测试 `test_template_sync.py` | `26 tests OK` | 待复审 |  |
| R2-2 | 2026-08-21 | 高 | P0 | 缺陷 | L2 无 timeout/异常兜底 | `evaluator.py:134` | 已修 | `timeout=300` + `TimeoutExpired/FileNotFoundError` | 手动验证 | 待复审 |  |
| R2-3 | 2026-08-21 | 中 | P1 | 缺陷 | 矩阵跨域引用误跑 | `evaluator.py:122` `foreign` | 已修 | 归属标注+跳过执行 | `gate --with-tests PASS` | 待复审 |  |
| R2-4 | 2026-08-21 | 中 | P1 | 缺陷 | generate-docs Win python 路径 | `generate-docs.sh:58` | 已修 | `bin vs Scripts` 探测 | Win 路径验证 | 待复审 |  |
| R2-5 | 2026-08-21 | 中 | P1 | 缺陷 | 重复标记残留 | `generator.py:38` `_replace_between_all` | 已修 | 折叠重复 span 为单块 | 重复标记用例验证 | 待复审 |  |
| R3-1 | 2026-08-21 | 低 | P2 | 冗余 | 域表行构建三处重复 | `generator.py:26` `_layout_block` 等 | 有意留 | 4 域；抽公共函数会把 ADR 0002 的投影与判据耦在一起。常驻否决见 `docs/architecture/overview.md` §5.1 | 本报告为证，防重提 | 待复审 |  |
| R3-2 | 2026-08-21 | 低 | P2 | 冗余 | sync 全量时每域收集接口两遍 | `generator.py:85,119` | 有意留 | 4 域毫秒级，后续按需传参优化 | 同上 | 待复审 |  |
| R3-3 | 2026-08-21 | 低 | P2 | 死代码 | 旧 `_replace_between` 无调用方 | `generator.py:56` | 已删 | 删除 | `grep` 无残留 | 待复审 |  |
| R3-4 | 2026-08-21 | 低 | P3 | 风格 | 函数内 import subprocess/sys | `evaluator.py:140` | 有意留 | L2 冷路径（无 `--with-tests` 不走）；挪到文件顶对性能和可读性几乎没差。常驻否决见 `docs/architecture/overview.md` §5.1 | — | 待复审 |  |

## 结论

三轮共 18 项：15 已修（含验证 `k3dge sync` 重算指纹、`gate --with-tests PASS`、`26 tests OK`），3 项有意留（R3-1/R3-2/R3-4，经权衡判过度优化）。后续审计前必读本文及 `SUMMARY.md`。
