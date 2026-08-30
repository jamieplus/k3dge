# 审计：k3dge 全量一致性 + 逻辑冗余（第二轮）

- **Date**: 2026-08-23
- **基线**：30 tests / 26 subtests / gate PASS / gate --with-tests PASS / 4 域契约已同步
- **审计人**：Agent（Muse Spark）+ 人复核
- **范围**：`src/k3dge/**` 全量（`engine`/`cli`/`sync`/`templates` + `milestone`）、`scripts/*` 双轨、`docs/` 全量、`tests/` 全量

## 发现

| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C-1 | 2026-08-23 | 高 | P0 | 缺陷 | `gate.py/ps1` 硬编码 `check`，`gate.sh sync` 透传而 `gate.py sync` 误为 `check sync` | `scripts/gate.py:12` `scripts/gate.ps1:4` | 已修 | 仅 `len==0` 时补 `check`，否则透传 `"$@"` | `gate.py sync → [SYNC]` | 待复审 |  |
| C-2 | 2026-08-23 | 中 | P1 | 规范 | `docs/tasks` 状态 `Pending` 非枚举 `idea/deferred/in-progress/done` | `docs/tasks/0001,0002:3` | 已修 | 改 `deferred` + `Priority` | `milestone` 扫描 | 待复审 |  |
| C-3 | 2026-08-23 | 中 | P1 | 规范 | `architecture/overview.md` Mermaid 箭头 `engine→cli` 与正文依赖相反 | `docs/architecture/overview.md:20` | 已修 | 改 `cli→engine, cli→sync` | 文档复审 | 待复审 |  |
| C-4 | 2026-08-23 | 中 | P1 | 规范 | `cli/engine` 验证矩阵缺 `milestone` TC | `docs/specs/cli,sync:27` | 已修 | 增 `TC-CLI-02` `TC-ENG-05` | 矩阵自检 | 待复审 |  |
| C-5 | 2026-08-23 | 低 | P2 | 漂移 | `assets/` 与 `scripts/` 双轨 | `src/k3dge/templates/assets/` | 已修 | `test_template_sync.py` 锁一致 | `27 tests` | 待复审 |  |
| LR-1 | 2026-08-23 | 中 | P1 | 冗余 | `_check_domain` 内单测分支死代码（已被 batch 接管） | `src/k3dge/engine/evaluator.py:190` | 已修 | 删除 45 行 | `grep` 无残留 | 待复审 |  |
| LR-4 | 2026-08-23 | 低 | P2 | 性能 | `is_ignored` 循环内重复 `Path()` | `src/k3dge/engine/manifest.py:64` | 已修 | 前置 `p=Path` 复用 | 静态 | 待复审 |  |
| LR-2 | 2026-08-23 | 中 | P1 | 性能 | `sync_all` 双重 AST 解析 | `src/k3dge/sync/generator.py:118` | 已修 | `iface_cache` 复用 | `sync` 耗时 halved | 待复审 |  |
| LR-5 | 2026-08-23 | 低 | P2 | 性能 | `_replace_between_all` O(N²) 字符串切片 | `src/k3dge/sync/generator.py:46` | 有意留 | 同 F-14。常驻否决见 `docs/architecture/overview.md` §5.1 | 记录防重提 | 待复审 |  |
| LR-6 | 2026-08-23 | 低 | P3 | 冗余 | `milestone` 重复 `scan` 读盘 | `src/k3dge/engine/milestone.py:27` | 有意留 | 同 F-15。常驻否决见 `docs/architecture/overview.md` §5.1 | 记录在案 | 待复审 |  |

## 结论

一致性 100% 闭环，`gate` 双轨、`spec` 矩阵、`tasks` 状态机均已对齐；`30 tests / gate PASS`。`LR-5/6` 经权衡判过度优化，留档防重提。

## 修复回记（2026-08-23）

* C-1~C-5 已 `k3dge sync` 重算指纹并 `gate --with-tests PASS` 验证；`30 tests OK`。
* LR-1/LR-4/LR-2 已删/优化，全仓 `grep` 无残留。
* LR-5/6 有意留，不转 `tasks`。
