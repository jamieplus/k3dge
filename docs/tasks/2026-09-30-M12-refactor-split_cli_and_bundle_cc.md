---
status: idea
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
