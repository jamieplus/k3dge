---
status: done
priority: P3
date: 2026-09-13
---

# 复杂度债续（非 milestone 文件）：CC≥11 函数逐个拆

- **Status**: done
- **Priority**: P3
- **可检索摘要**: A-1 已拆完 `milestone.py`（1692→114 facade）；本票接续 **质量席首程（`docs/reviews/archive/M7/2026-09-04-M7-quality.md`）Q-1/Q-2/Q-4/Q-5** 的非 argparse 派 CC 重函数，逐函数拆/降（Simplify-first，一 diff 一测试）。**Q-3（argparse 派函数）审计已判 `有意留`，不列、不刷指标。**
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
| M9 value-7 | `align.py` | `run_milestone_alignment`（CC16：校验/门控/评审脚手架落盘/guide 桩四类职责混居） |

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
- ✅ 本会话已拆：<code>doc_catalog._validate_file</code>(38)、<code>pipeline_schema.validate_pipeline_config</code>(29)、<code>contract.extract_python_interface</code>(24)/<code>_get_all_names</code>(15)/<code>_fmt_class</code>(16)、<code>changelog._append_to_unreleased</code>(18)、<code>doc_catalog.grep_docs</code>(16)、<code>Manifest.__init__</code>(17)、<code>version.bump_version</code>(14)/<code>append_changelog</code>(16)。（另 <code>_auto_backfill_reviews</code> 等随 A-1 迁移至 task_write 等模块。）
- ⬜ 余（非派）：<code>audit_flow.collect_audit</code>(36)、<code>task_write._auto_backfill_reviews</code>(34)、<code>milestone_audit.run_audit_flow</code>(19)/<code>_ratchet_audit_step</code>(18)、<code>pipeline_schema._validate_transports</code>(19)、<code>evaluator._run_batch_tests</code>(20)/<code>_warn_changelog_done</code>(16)、<code>worktree.merge_back</code>(16)、<code>seal._seal_archive</code>(16) 等，逐块一 diff 一测试。

## 复判（2026-09-14）
- ✅ `align.run_milestone_alignment`(CC21)：提取 `_align_run_gates()`（gate 注册+dispatch），主函数退为四步清单；77 tests pass。
- ✅ `pipeline_schema._validate_transports`(CC21)：提取 `_validate_mcp_transport` / `_validate_cli_transport` / `_validate_manual_transport` + dispatch dict；加 provider 只加一行；77 tests pass。
- 🔕 余 14 个函数经代码复判：CC 来自防御性错误处理/状态机/线性扫描，无结构性问题（无重复逻辑、无跨域耦合、无抽象泄漏）。**拆了跨文件追反而降低可读性**，已入 `docs/reviews/LEFTOVERS.md`（CC-01..CC-14）。
- 本票可关。
