---
status: in-progress
milestone: M12
priority: P3
date: 2026-09-30
---

# 拆 ConsistencyEngine：检查组各自成模块，只共享 workspace_root


## 已确认意图
拆 ConsistencyEngine：检查组各自成模块，只共享 workspace_root

## 可检索摘要
拆 ConsistencyEngine：检查组各自成模块，只共享 workspace_root

## 上下文/切入点
来源：M11 审计 `value-14`（`docs/reviews/archive/M11/2026-09-29-M11-k3dit-bundle-audit.md`）转票。

**核验（2026-10-04）——债仍在，成立**：`src/k3dge/engine/evaluator.py` 现 **1294 行**，`ConsistencyEngine` 仍是单一 God 类，`evaluate()` 串起彼此无关的多组检查（版本一致性、模板漂移、pipeline、审计留痕、文档闸、域、验证矩阵、域契约），共享的只有 `self.workspace_root`。消费者三处（`cli/main.py:218/1018`、`cli/status.py:111`、`cli/mcp.py:139`）。

**切入**：按检查类型拆成独立 checker（各自 `(workspace, manifest) -> List[Violation]`），类只留编排；先动耦合最低的组，保持 `evaluate()` 返回 `GateReport` 的契约不变。

## 进度（2026-10-04，第一批：workspace-only 检查）

新建包 `src/k3dge/engine/checks/`，每组一个模块，公开 `check_<x>(workspace) -> List[Violation]`
（与 `pure_refs` 的 `check_*` 同形；辅助如 `_logs_*` 保持私有）：

- `version.py` / `pipeline.py` / `audit_trail.py` / `mcp_json.py` / `state_doc.py` /
  `extractors.py` / `docs_toml.py` — 七组「只依赖 `workspace_root`」的检查。
- `evaluator.ConsistencyEngine` 的对应方法改薄委托（保留方法名，`test_audit_trail` 等直调不受影响）。
- `test_gate_imports` 闸核 allowlist 登记新包 `checks` 并把 `checks/*.py` 一并纳入扫描面（不让新包成盲区）。

`evaluator.py` 1294 → 1053 行；公开面新增 7 个 `check_*`（`k3dge sync` 已回写契约哈希）。
验证：`pytest tests` 1279 passed, 10 skipped；`k3dge check` 绿。

余：`_collect_modified_domains` / `_run_affected_tests` / `_check_template_drift` / `_check_docs` /
`_check_domain`(+`_load_domain_spec`/`_check_verification_matrix`/`_check_domain_contract`/`_check_domain_imports`) /
`_check_generated_projections` / `_check_architecture_tables` / `_check_assert_tautology`（manifest/files-dependent）。
