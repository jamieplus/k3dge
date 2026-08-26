# 脚手架↔本仓对齐必须进 `k3dge check`，不能只靠 pytest

- **Status**: done
- **Milestone**: M0
- **Priority**: P1
- **Date**: 2026-08-24

## 已确认意图
用户：下游脚手架与 k3dge 本体功能未对齐时门控没触发，因此改了，要求审计这次改。审计结论：只加长了 `test_template_sync.PAIRS`，`k3dge check` 仍不红。

## 方案
1. 在 `evaluate()` 里做与 `validate_versions` 同级的 **总是运行** 比对（或把 PAIRS 右侧路径映射为 `templates` 域的 touched）。规则 id 如 `TEMPLATE_DRIFT`。
2. 配对表只维护一份（engine 可读的清单），`test_template_sync` 与 check 共用，禁止第三份。
3. 补测：只改 `AGENTS.md`（不同步 assets）→ `k3dge check` 无 `--with-tests` 也失败；pre-commit 默认入口同样失败。
4. 不要用「把 pre-commit 改成 `--with-tests`」代替：那会让每次提交跑全域 pytest，且仍修不了 G-02（目标文件不标 templates）。

公开新符号则同任务 `k3dge sync`。

## 入口
- `src/k3dge/engine/evaluator.py`
- `tests/unit/templates/test_template_sync.py`
- `scripts/gate.py`（保持默认 `check`，锁进 evaluate）

## 来源
[docs/reviews/2026-08-24-scaffold-gate-lock.md](../reviews/2026-08-24-scaffold-gate-lock.md) G-01 / G-02
