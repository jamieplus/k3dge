---
status: done
milestone: M12
priority: P3
date: 2026-09-30
---

# 降分支复杂度：cli/main.py cmd_audit/cmd_doc 与 audit_bundle 五函数


## 已确认意图
降分支复杂度：cli/main.py cmd_audit/cmd_doc 与 audit_bundle 五函数

## 可检索摘要
降分支复杂度：cli/main.py cmd_audit/cmd_doc 与 audit_bundle 五函数

## 上下文/切入点
来源：M11 审计 `value-10`（`docs/reviews/archive/M11/2026-09-29-M11-k3dit-bundle-audit.md`）转票。

**核验（2026-10-04，AST CC 实测）——债仍在，成立**：
- `cli/main.py`（1465 行）：`cmd_doc` CC39/136 行、`cmd_audit` CC39/75 行；同层 `cmd_milestone` CC31、`cmd_status` CC28。
- `engine/audit_bundle.py`（1067 行）：`_apply_sequential_merged` CC40、`apply_bundle` CC39、`consume` CC35、`reconcile_report_rows` CC26、`land_report` CC16（即票称"五函数"）。
- 同层更重者（value-10 一并点过，可纳入同一轮）：`audit_verify.verify_bundle_local` CC60、`milestone_audit._bundle_audit_leg` CC59、`doc_gate._run_schema_gate` CC51。

**切入**：先拆 CC≥30 的（解析/编排/文案门控混在一个函数里）；`audit_bundle` 装配步骤抽显式阶段对象。伴随信号：`test_layers` integration=0，缺跨组件兜底 ⇒ 拆时优先补测。

## 进度（2026-10-04，第一轮：抽函数，行为保持）

AST CC 实测（同口径）：

| 函数 | 前 | 后 |
| --- | --- | --- |
| `cli/main.py cmd_doc` | 39 | ≈2（拆 6 个 `_doc_*` + dispatch 表） |
| `cli/main.py cmd_audit` | 39 | 22（拆 `_audit_run_bundle` / `_audit_land_report`） |
| `engine/audit_bundle.apply_bundle` | 39 | 19（拆 `_apply_guards` / `_apply_fast_path`） |
| `engine/audit_bundle._apply_sequential_merged` | 40 | 22（拆 `_exclude_unclosed_hunks` / `_land_pins_in_worktree`） |
| `engine/audit_bundle.consume` | 35 | 23（拆 `_resolve_unclosed_scope`） |
| `engine/audit_bundle.reconcile_report_rows` | 26 | 16（拆 `_escalation_mark` / `_insert_ver_mark`） |
| `engine/audit_bundle.land_report` | 16 | 16（未动：已在 CC<30 面） |

- 全部为**行为保持**重构（纯抽函数/分发表），无公开签名变化 ⇒ 无契约哈希变动。
- 验证：`pytest tests` 1279 passed, 10 skipped；`k3dge check` 绿。
- 余：`audit_bundle` 已无 CC≥30；`cli/main.py` 仍存 `cmd_milestone` CC31、`cmd_status` CC28（本票面外，另议）。
