# 堵住 seal 假回滚、L2 None 崩栈、milestone_id/manifest 路径逃逸，并校验配置类型

- **Status**: done
- **Priority**: P1
- **Date**: 2026-08-24
- **来源**：[docs/reviews/2026-08-24-8dim-vibe-audit.md](../reviews/2026-08-24-8dim-vibe-audit.md) S-01 / S-02 / S-03 / S-04 / S-11

## 可检索摘要
按 8 维「健壮性与安全」新照出五处，08-24 报告未立案：(1) seal 回滚失败被 `except: pass` 吞掉仍声称 rolled back；(2) `--with-tests` 在域有 tests、无 spec 时 `Path / None` 使异常处理器崩栈；(3) `milestone_id` 含 `../` 可把 archive/review 写到工作区外；(4) manifest 相对路径允许 `../`；(5) `ignore` 为字符串时按字符迭代且 `*` 匹配全部文件，非 str 的 src/spec 与坏的 `test_command_template` 抛未包装异常。

## 上下文/切入点
- 回滚：`src/k3dge/engine/milestone.py` `seal_milestone` 末尾双层 try
- None：`src/k3dge/engine/evaluator.py` 约 122–153 行三处 `workspace / manifest.spec_path(d)`；milestone align 的 L2 复制体同样
- 路径：`run_milestone_alignment` 写 reviews 的文件名、`seal` 的 `archive / milestone_id`
- Manifest：`Manifest.__init__` 只查 `is_absolute()`；`ignore` 未要求 list
- 复现：`ConsistencyEngine(tmp).evaluate(run_tests=True)` 在「core 有 tests 无 spec + 测试失败」时 TypeError；`ignore="*.pyc"` 时 `is_ignored("foo") is True`

## 方案
1. 回滚失败收集错误，返回 `rolled back with errors: ...`，禁止 `pass`；补 mock 第二次 move 失败的测试（与 A-04 回滚测合同一次做）。
2. `spec_rel = manifest.spec_path(d) or None`，`file_path` 用可选 str，禁止 `Path / None`。milestone 复制体一并改（或先做 align 抽函数任务）。
3. 拒绝 `milestone_id` 含路径分隔符或 `..`；`archive_dir.resolve().relative_to(tasks_archive_root.resolve())` 失败则拒绝。
4. Manifest 在 load 时把 `src/spec/tests` resolve 相对 workspace，要求结果仍 `relative_to(workspace)`；`ignore` 必须是 string 列表；非 str 路径收进 `ManifestError`（已有 `MANIFEST_INVALID`）。
5. `test_command_template.format` 包 `KeyError`/`ValueError` 为 Violation，不要冒泡。

## 触发条件
用户确认后开工。不改公开签名则无需 `k3dge sync`。
