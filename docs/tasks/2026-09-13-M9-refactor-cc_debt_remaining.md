---
status: idea
milestone: M9
priority: P3
date: 2026-09-13
---

# 复杂度债续（非 milestone 文件）：CC≥11 函数逐个拆

- **Status**: idea
- **Milestone**: M9
- **Priority**: P3
- **可检索摘要**: A-1 已拆完 `milestone.py`（1692→114 facade）；本票接续 **k3lity 质量席首程（`docs/reviews/archive/M7/2026-09-04-M7-quality.md`）Q-1/Q-2/Q-4/Q-5** 的非 argparse 派 CC 重函数，逐函数拆/降（Simplify-first，一 diff 一测试）。**Q-3（argparse 派函数）审计已判 `有意留`，不列、不刷指标。**
- **Date**: 2026-09-13

## 意图
不整体销账：把审计 Q-1/Q-2/Q-4/Q-5 指认的 CC 重函数逐个收敛（Q-7 体积＝A-1，已完）。

## 待拆（非派函数；来源＝审计原判 + 2026-09-13 复测）
| 来源 | 位置 | 函数 |
| --- | --- | --- |
| Q-1 | `audit_flow.py` | `collect_audit` |
| Q-2 | `audit_flow.py` | `submit_audit` |
| Q-2 | `pipeline_schema.py` | `validate_pipeline_config` |
| Q-2 | `pipeline_schema.py` | `_validate_transports` |
| Q-4 | `contract.py` | `extract_python_interface` |
| Q-4 | `contract.py` | `collect_domain_interface` |
| Q-4 | `contract.py` | `_fmt_class` |
| Q-4 | `contract.py` | `_get_all_names` |
| Q-4 | `contract.py` | `_symbol_name` |
| Q-2 | `evaluator.py` | `_run_batch_tests` |
| Q-4 | `evaluator.py` | `_warn_changelog_done` / `_check_domain_imports` / `_check_verification_matrix` / `_check_template_drift` / `_package_prefix` |
| Q-4 | `doc_catalog.py` | `grep_docs` |
| Q-4 | `manifest.py` | `Manifest.__init__` |
| Q-4/Q-5 | `worktree.py` | `merge_back` / `ensure` / `strip_pins` |
| Q-5 | `version.py` | `append_changelog` / `bump_version` |
| Q-4 | `_ts.py` | `_decl_signature` |
| Q-4 | `markers.py` | `parse_text` |
| Q-2 | `milestone_audit.py`(移入) | `_ratchet_audit_step` / `run_audit_flow` |
| Q-1/Q-2 | `task_write.py`(移入) | `_auto_backfill_reviews` / `mark_task_done` / `_finalize_task_done` |
| Q-1/Q-2 | `seal.py`(移入) | `seal_milestone` / `_seal_archive` / `_seal_review_gate` |

## 有意留（Q-3；审计已判，不拆、不刷指标）
`cli/main.py` 的 `cmd_*`（argparse 派形状天然多分支）+ `_sync_peers_into_mcp` / `_cmd_mcp_probe`；`cli/mcp.py` 的 `_audit_protocol_with_fallback` / `k3dge_milestone_control`；`pipeline_runner.py` 的 `run_action` / `call_mcp_tool` / `resolve_action`；`cli/status.py` 的 `workspace_status`；`search.py` 的 `_python_search`；`nextstep.py`。**记录在册，不拆。**

## 边界与拆分
- 事实归属：拆分归本票；CC 阈值口径归 `audit_trigger`/质量工具面。
- 处置纪律：每函数拆/降**单独成程**（一 diff 一测试）；**禁止为过闸刷指标**；Q-3 不拆。
- 桩子先行：先挑 `pipeline_schema.validate_pipeline_config`（自含、已有 `_validate_transports` 分件）→ 再 `contract._fmt_class`/`_get_all_names`。

## 进度（2026-09-13）
- ✅ `doc_catalog._validate_file`（CC38，Q-1 → <11）：拆 8 个 schema 检查 helper，`_validate_file` 退为编排；行为不变（`b2eb8f8`）。
- 🔁 登记册按审计原判重校（剔 Q-3，标有意留）。
- ✅ `pipeline_schema.validate_pipeline_config`（CC29，Q-1/Q-2 → <11）：拆 `_validate_legacy_keys`/`_validate_roles`/`_validate_peers`/`_validate_pipelines`，退为编排；行为不变（`7695d17`）。剩 `_validate_transports` CC19。
- ⬜ 余按上表逐函数进行。
