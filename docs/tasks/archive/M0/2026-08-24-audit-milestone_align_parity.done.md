# 让 `milestone align` 复用 evaluator，并补齐 align/回滚测试

- **Status**: done
- **Milestone**: M0
- **Priority**: P1
- **Date**: 2026-08-24
- **来源**：[docs/reviews/2026-08-24-5pass-audit.md](../reviews/2026-08-24-5pass-audit.md) A-03 / A-04 / A-10

## 可检索摘要
`run_milestone_alignment` 手写了一份与 `ConsistencyEngine` 平行的 L2：漏捕 `FileNotFoundError`、用全文 `` `tests/...` `` 而非 Verification Matrix 段收集测试引用，却在模块顶层导入了从未调用的 `ConsistencyEngine`。F-09 / TC-CLI-02 / TC-ENG-05 声称 align 与 seal 回滚已测，但 `tests/unit/engine/test_milestone.py` 只测了 seal 三闸机；`run_milestone_alignment` 仅出现在 import 行。`_check_domain(run_tests=...)` 在 F-12 删分支后成为死参数。

## 上下文/切入点
- 复制体：`src/k3dge/engine/milestone.py` `run_milestone_alignment` 中「全域回归」段（manifest 遍历 + subprocess）
- 正本：`src/k3dge/engine/evaluator.py` `evaluate` 的 batch pytest 与 `_check_domain` 的矩阵段扫描
- 测试：`tests/unit/engine/test_milestone.py`；规格 `docs/specs/engine/spec.md` TC-ENG-05、`docs/specs/cli/spec.md` TC-CLI-02
- 死参：`ConsistencyEngine._check_domain(..., run_tests=False)` 函数体不读该参数
- 相关：MCP `force_full`（另一任务）若要 Full Matrix，应调用这里抽出来的全域校验，禁止第三份复制

## 方案
1. 从 evaluator 抽出「对给定域集合做结构+契约（+可选 L2）」的纯函数，`evaluate` 传入 git 触及域，`run_milestone_alignment` 传入 `manifest.domains.keys()`。
2. 测试引用只扫 Verification Matrix 段；`FileNotFoundError` / timeout / pytest 缺失与 evaluator 同构。
3. 删除 milestone 顶层未使用的 `ConsistencyEngine`/`GateReport` 导入；删除 `_check_domain` 的 `run_tests` 死参（内部方法，不进契约哈希）。
4. 补测：`run_milestone_alignment` 无任务/未完成拒绝；全域契约失败拒绝；`seal_milestone` 在 `shutil.move` 中途失败时回滚（可 mock 第二次 move 抛错）。

## 进展（2026-08-24）
已顺手修：align 补 `FileNotFoundError`、测试引用改扫 Verification Matrix、`spec_path` None 不再崩、模板 KeyError 包装。**仍未做**：抽出与 evaluator 共用的全域校验函数（两份 L2 仍并行）。任务保持 idea。

## 触发条件
用户确认后开工。抽函数若变成新的公开符号，必须同任务 `k3dge sync`。
