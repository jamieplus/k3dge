# 按「无测试即缺陷」补 diff/manifest/CLI 异常路径，并补 generate-docs.ps1

- **Status**: done
- **Priority**: P1
- **Date**: 2026-08-24
- **来源**：[docs/reviews/2026-08-24-8dim-vibe-audit.md](../reviews/2026-08-24-8dim-vibe-audit.md) S-07 / S-08

## 可检索摘要
本标准 Pass 4 把「无测试即缺陷」和「仅 Happy Path」设为硬规则。当前缺口：`engine/diff.py` 的 quotepath/重命名/`K3DGE_BASE_SHA`/shallow（R1-3 声称有覆盖，现 `test_evaluator` 无这些用例）；`manifest.py` 无单元测试（ignore 类型、绝对路径、`../`）；CLI `cmd_sync` / `cmd_milestone` / `check` 成功路径零测；`test_parser_has_check_and_sync_only` 不断言 `milestone` 子命令。跨平台：`generate-docs.sh` 无 `.ps1`。MCP/align/回滚测试缺口已在 A-04/A-09 任务，此处不重复。

## 上下文/切入点
- 测试树：`tests/unit/cli/test_main.py`、`tests/unit/engine/test_evaluator.py`（无 diff 直测）、无 `test_diff.py` / `test_manifest.py`
- 双轨锁：`tests/unit/templates/test_template_sync.py` `PAIRS`
- 脚本：`scripts/generate-docs.sh`、`src/k3dge/templates/assets/generate-docs.sh`

## 方案
1. 新增 `tests/unit/engine/test_diff.py`：引号路径、`orig -> new` 取目标、`K3DGE_BASE_SHA` 走 `sha...HEAD`、shallow 且无 base 时 `GitError`。
2. 新增 `tests/unit/engine/test_manifest.py`：`ignore` 非 list → `ManifestError`；相对 `../` 拒绝或规范化（与 soundness 任务方案对齐）；缺 spec 的域不崩 L2（依赖 S-02 修复）。
3. CLI：`check` 无漂移退出 0；`sync` 幂等「already up to date」；`milestone status` 无任务退出 1；parser 断言含 `milestone`。改掉 `test_parser_has_check_and_sync_only` 的过时名字。
4. 若要 Windows 收尾对等：补 `generate-docs.ps1` 与 asset，并加入 `PAIRS`。若明确「收尾只在 POSIX CI 跑」则本条改为有意留并写进 ADR，不要 silently skip。

## 触发条件
用户确认后开工。第 4 点跨平台脚本属成对物，动前若无 ADR 需先问（AGENTS.md §8）。
