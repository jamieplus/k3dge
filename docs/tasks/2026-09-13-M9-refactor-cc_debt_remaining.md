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
- **可检索摘要**: A-1 已拆完 `milestone.py`（1692→114 facade）；本票接续登记册里**其余文件**的 CC≥11 函数，逐函数拆/降（Simplify-first，一 diff 一测试）。
- **Date**: 2026-09-13

## 意图
不整体销账：把 A-1 合并登记册中除 `milestone.py` 外的 CC≥11 函数逐个收敛。

## 登记册（2026-09-13 实测；grep 式分支计数，非严格 McCabe）
| CC | 位置 | 函数 |
| --- | --- | --- |
| 38 | `doc_catalog.py` | `_validate_file` |
| 36 | `audit_flow.py` | `collect_audit` |
| 29 | `pipeline_schema.py` | `validate_pipeline_config` |
| 24 | `contract.py` | `extract_python_interface` |
| 23 | `cli/main.py` | `cmd_milestone` |
| 21 | `cli/main.py` | `cmd_task` |
| 20 | `evaluator.py` | `_run_batch_tests` |
| 19 | `pipeline_schema.py` | `_validate_transports` |
| 18 | `cli/main.py` | `cmd_doc` |
| 17 | `manifest.py` | `__init__` |
| 16 | `worktree.py` | `merge_back` |
| 16 | `version.py` | `append_changelog` |
| 16 | `evaluator.py` | `_warn_changelog_done` |
| 16 | `doc_catalog.py` | `grep_docs` |
| 16 | `contract.py` | `collect_domain_interface` |
| 16 | `contract.py` | `_fmt_class` |
| 16 | `audit_flow.py` | `submit_audit` |
| 15 | `mcp.py` | `_audit_protocol_with_fallback` |
| 15 | `cli/main.py` | `_sync_peers_into_mcp` |
| 15 | `cli/main.py` | `cmd_status` |
| 15 | `contract.py` | `_get_all_names` |
| 14 | `worktree.py` | `ensure` |
| 14 | `version.py` | `bump_version` |
| 14 | `cli/status.py` | `workspace_status` |
| 14 | `pipeline_runner.py` | `run_action` |
| 14 | `cli/main.py` | `cmd_audit` |
| 13 | `pipeline_runner.py` | `call_mcp_tool` |
| 13 | `_ts.py` | `_decl_signature` |
| 12 | `search.py` | `_python_search` |
| 12 | `markers.py` | `parse_text` |
| 12 | `evaluator.py` | `_check_domain_imports` |
| 12 | `evaluator.py` | `_check_verification_matrix` |
| 12 | `evaluator.py` | `_check_template_drift` |
| 11 | `worktree.py` | `strip_pins` |
| 11 | `pipeline_runner.py` | `resolve_action` |
| 11 | `mcp.py` | `k3dge_milestone_control` |
| 11 | `cli/main.py` | `_cmd_mcp_probe` |
| 11 | `evaluator.py` | `_package_prefix` |
| 11 | `contract.py` | `_symbol_name` |

## 边界与拆分
- 事实归属：拆分归本票；CC 阈值口径归 `audit_trigger`/质量工具面。
- 处置纪律：每函数拆/降**单独成程**（一 diff 一测试）；CLI argparse 派函数（`cmd_*`）若属"派形状天然分支多"，可只调阈值口径不修码（记录）；禁止整体销账。
- 桩子先行：先挑 `doc_catalog._validate_file`（最高）+ `audit_flow.collect_audit` 两个，各起一程。

## 进度（2026-09-13）
- ✅ `doc_catalog._validate_file`（CC38 → <11）：拆 `_validate_filename`/`_validate_h1`/`_validate_sections_when`/`_validate_sections`/`_validate_section_order`/`_validate_frontmatter`/`_validate_headers`/`_validate_index`，`_validate_file` 退为编排；行为不变（`b2eb8f8`）。移出清单，剩 `doc_catalog.grep_docs` CC16。
- ⬜ 余按上表逐函数进行（每程一 diff 一测试）。
