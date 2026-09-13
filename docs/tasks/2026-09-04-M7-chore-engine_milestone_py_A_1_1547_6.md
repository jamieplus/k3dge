---
status: idea
milestone: M9
priority: P2
date: 2026-09-04
---

# 拆分 engine/milestone.py 上帝模块（首案 A-1）+ 复杂度债登记册

- **Status**: idea
- **Milestone**: M9
- **Priority**: P2
- **Date**: 2026-09-04

## 已确认意图
按关注点拆分 `engine/milestone.py`（现 1692 行，6+ 关注点），逐块抽模块、**每步行为不变 + 测试护航**（Simplify-first，rules/02）。本票并**收编**复杂度债登记册（原 `cc_debt_register`，已并入此，物理删除）。

## 可检索摘要
拆分 `milestone.py`；兼作复杂度债登记册（CC≥11 函数 + >1000 行文件）。每函数拆/降单独成程（一 diff 一测试），禁止为过闸刷指标。

## 复杂度债登记册（2026-09-13 实测；grep 式分支计数，非严格 McCabe）

> 口径：AST 分支节点（if/for/while/try/with/BoolOp/IfExp）计数，非 `E−N+2P`。只登记，不承诺一次清。

**文件 >1000 行**：`engine/milestone.py` 1692、`cli/main.py` 1362。

**CC≥11 函数（降序）**：

| CC | 位置 | 函数 |
| --- | --- | --- |
| 38 | `doc_catalog.py:329` | `_validate_file` |
| 36 | `audit_flow.py:164` | `collect_audit` |
| 34 | `milestone.py:160` | `_auto_backfill_reviews` |
| 29 | `pipeline_schema.py:40` | `validate_pipeline_config` |
| 24 | `contract.py:203` | `extract_python_interface` |
| 23 | `main.py:749` | `cmd_milestone` |
| 21 | `main.py:357` | `cmd_task` |
| 20 | `evaluator.py:111` | `_run_batch_tests` |
| 19 | `pipeline_schema.py:144` | `_validate_transports` |
| 19 | `milestone.py:1499` | `run_audit_flow` |
| 18 | `milestone.py:1449` | `_ratchet_audit_step` |
| 18 | `milestone.py:102` | `_append_to_unreleased` |
| 18 | `main.py:280` | `cmd_doc` |
| 17 | `manifest.py:41` | `__init__` |
| 16 | `worktree.py:194` | `merge_back` |
| 16 | `version.py:205` | `append_changelog` |
| 16 | `milestone.py:832` | `_seal_archive` |
| 16 | `milestone.py:412` | `list_tasks` |
| 16 | `evaluator.py:369` | `_warn_changelog_done` |
| 16 | `doc_catalog.py:201` | `grep_docs` |
| 16 | `contract.py:276` | `collect_domain_interface` |
| 16 | `contract.py:116` | `_fmt_class` |
| 16 | `audit_flow.py:78` | `submit_audit` |
| 15 | `milestone.py:679` | `run_milestone_alignment` |
| 15 | `milestone.py:1299` | `_similar_task_hints` |
| 15 | `mcp.py:504` | `_audit_protocol_with_fallback` |
| 15 | `main.py:564` | `_sync_peers_into_mcp` |
| 15 | `main.py:1105` | `cmd_status` |
| 15 | `contract.py:178` | `_get_all_names` |
| 14 | `worktree.py:45` | `ensure` |
| 14 | `version.py:144` | `bump_version` |
| 14 | `status.py:80` | `workspace_status` |
| 14 | `pipeline_runner.py:390` | `run_action` |
| 14 | `main.py:685` | `cmd_audit` |
| 13 | `pipeline_runner.py:228` | `call_mcp_tool` |
| 13 | `milestone.py:779` | `_seal_review_gate` |
| 13 | `milestone.py:462` | `create_task` |
| 13 | `_ts.py:40` | `_decl_signature` |
| 12 | `search.py:162` | `_python_search` |
| 12 | `milestone.py:1621` | `run_seal_flow` |
| 12 | `milestone.py:1024` | `_find_report` |
| 12 | `markers.py:115` | `parse_text` |
| 12 | `evaluator.py:695` | `_check_domain_imports` |
| 12 | `evaluator.py:573` | `_check_verification_matrix` |
| 12 | `evaluator.py:417` | `_check_template_drift` |
| 11 | `worktree.py:116` | `strip_pins` |
| 11 | `pipeline_runner.py:107` | `resolve_action` |
| 11 | `milestone.py:1335` | `_related_doc_hints` |
| 11 | `milestone.py:1161` | `ask` |
| 11 | `mcp.py:347` | `k3dge_milestone_control` |
| 11 | `main.py:648` | `_cmd_mcp_probe` |
| 11 | `evaluator.py:44` | `_package_prefix` |
| 11 | `contract.py:350` | `_symbol_name` |

## 边界与拆分
- 事实归属：关注点拆分归本票；CC 阈值口径归 `audit_trigger`/质量工具面。
- 处置纪律：每函数拆/降**单独成程**（一 diff 一测试）；CLI argparse 派函数（`cmd_*`）若属"派形状天然分支多"，可只调阈值口径不修码（记录，不在此票）；**禁止整体销账**。
- 桩子先行：先定目标模块清单（如 `milestone/` 包：tasks / align / seal / audit_flow / report），再逐块抽；每块 `k3dge sync` + 全量测试绿。

## 验收
- 逐模块/逐函数闭环（每步一 diff 一测试）；或质量席复程改判；不得整体销账。

## 进度（2026-09-13）
- **首块 ✅**：`_Prompt` → `engine/prompt.py`（`milestone` 以 `_Prompt` 别名兼容）。1692 → 1670。
- **第二块 ✅**：`get/set/bump_milestone` + `_validate_milestone_id` + `_SAFE_MILESTONE_ID_RE` → `engine/milestone_pointer.py`（milestone re-export，行为不变）。1670 → 1629。
- **第三块 ✅**：`_has_milestone_token` / `_is_doc_aux` / `_is_review_aux` / `_filename_milestone` / `_DOC_AUX_NAMES` / `_REVIEW_AUX` / `_FILENAME_MILESTONE_RE` → `engine/milestone_files.py`（re-export）。1629 → 1601。
- **第四块 ✅**：report 查找/归类/计数 `_find_report` / `_find_audit_report` / `_report_kind` / `_parse_audit_stats` / `_AUDIT_HEADER` / `_QUALITY_MARKER_RE` → `engine/audit_report.py`（re-export）。1601 → 1552。
- **第五块 ✅**：doc-audit 族 `_changed_docs` / `_new_archive_without_note` / `_ensure_doc_audit_task` / `_similar_task_hints` / `_related_doc_hints` / `_attach_k3che_hints` / `run_doc_audit`（+`_AUDIT_EXCLUDE_DOCS`/`_K3CHE_HINT_RE`）→ `engine/doc_audit.py`（milestone 内部依赖惰性 import 避环；re-export）。1552 → 1346。
- **第六块 ✅**：reviews 归档机械 `_living_review_files` / `_reviews_to_archive` / `_rewrite_leftover_links` / `_safe_archive_dir` → `engine/review_archive.py`（re-export）。1346 → 1298。
- **余块待抽**：seal 流程（`seal_milestone`/`seal_preconditions_error`/`_seal_archive`/`_seal_review_gate`/`_align_review_path`/`_strip_align_stub`/`run_seal_flow`/`_write_closure_note`）——最安全攸关，独立一轮；align；audit_flow；tasks（`list_tasks`/`create_task`/`mark_task_done` 一族）。
- **余块待抽**：report 解析（`_find_report`/`_parse_audit_stats`/`_seal_review_gate`…）→ `engine/audit_report.py`；doc-audit（`run_doc_audit`/`_changed_docs`/`_ensure_doc_audit_task`）→ `engine/doc_audit.py`；seal（`seal_milestone`/`seal_preconditions_error`/`_seal_archive`）；audit_flow；tasks；align。
- 纪律：每块一 diff 一测试、`k3dge sync` + 全量绿；别名/转发保调用面，行为不变。
