---
status: done
milestone: M11
priority: P3
date: 2026-09-21
---

# 同批小闸：状态表 priority 数字对账 + 抽取器插件新鲜度 + docs.toml 键落点

- **可检索摘要**: 横展扫描出的三个"声明面 vs 事实"缺口补闸：① `overview §6.3` 的 priority **数字**（此前只查状态名，数字写反过：旧文 `ratchet_open` 排在 `seal_ready` 之上）；② `.agent/extractors.toml` vs `.agent/extractors/*.py`（配置改了没 sync ⇒ 静默用过时插件抽接口）；③ `.agent/docs.toml` 的 `= true` 键是否真会被 `scripts/generate-docs.sh` 处理。

## 方案

1. `ARCH_STATE_DOC_DRIFT` 扩展：除状态名齐备外，用 `<priority> | \`state\`` 行与 `STATE_OPTIONS[*].priority` 逐行比数字。
2. 新码 `EXTRACTOR_PLUGIN_STALE`：`resolve_languages` + `render_plugin` 与盘上文件逐字比（缺文件、手改、配置改了未 sync 都算）。
3. 新码 `DOCS_TOML_KEY_UNKNOWN`：键表**从写脚本自己的 `gen "<key>" "<file>" "<title>"` 行读**（不另造第二份键表）；读不到 `gen` 行 ⇒ 跳过。**只查键，不查文件是否已生成**——`= true` 而桩未落是收尾流程常态。

## 边界与拆分

- 事实归属：状态闭集/priority 归 `nextstep`；插件渲染归 `extractor_gen`；docs.toml 的键归写脚本（读侧镜像它）。
- 有意留（LEFTOVERS）：`PRE-06` 记"配了却没生成"仍无人管。

## 结案

- 落地：`engine/evaluator.py`（`_check_state_doc_coverage` 加 priority 对账、新增 `_check_extractor_plugins` / `_check_docs_toml`）、`engine/gate_facts.py`（`EXTRACTOR_PLUGIN_STALE` block / `DOCS_TOML_KEY_UNKNOWN` warn）。
- 测试：`tests/unit/engine/test_projection_drift_gates.py`（8 例：缺插件/新鲜/手改/无配置；未知键/已知键无文件/readme 键）；`test_state_doc_coverage.py` 夹具改用真实 priority。
- 矩阵：TC-ENG-29/30/31。
- 验证：`k3dge check --with-tests` 绿（四域）；`pytest -q` 731 passed, 2 skipped。
