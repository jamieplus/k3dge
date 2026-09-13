---
status: done
milestone: M9
priority: P1
date: 2026-09-04
---

# 首案真跑前遗留（k3dge 侧）——复核后剩余

- **Status**: done
- **Milestone**: M9
- **Priority**: P1
- **可检索摘要**: 2026-09-12 复核：原清单多数已过时/已完成；**剩 3 项活**——§7 复用预筛、`.mcp.json` 解释器固化、scaffold 出生即红（`PIPELINE_PEER_UNWIRED`）。
- **Date**: 2026-09-04

## 复核（2026-09-12）——已过时/已完成，不再追

- **G3 seal 换源**：已落地（seal 走报告计数 `audit_closed`，`roles.audit.mode="ratchet"`）。
- **G4 号段发放 / 席位身份登记**：过时——`claim`/`deposit`/`adjudicate` 已退役（pin-only：钉＝写源，Hall 拔）。
- **首案活体新增**：号段纪律 / 号段不可增补（随退役消解）；note ≤80（已由 `markers` 闸守）；冲突重试（已由棘轮幂等重跑解决）。
- **CLI 四动词烟测**：基本覆盖（`tests/unit/engine/test_audit_flow.py` / `test_seal_flow.py`）。

> 原文明细留 git 历史；本单只承载下列剩余项。

## 剩余（活）

1. **§7 复用预筛三条件** → **拆出** `2026-09-13-M9-feat-audit_prefilter`（跨仓依赖 k3dit `lens_version` 取数源；未就绪前不短路）。
2. ✅ **`.mcp.json` 解释器固化**：k3dit/k3che 的 `command` 改各仓 venv 绝对路径（`k3dge mcp sync` 只补缺、不覆盖已有 `command`）。
3. ✅ **scaffold 出生即红（`PIPELINE_PEER_UNWIRED`）**：取方案 b——scaffold 把 pipeline 绑定的 peer 以 stub 写进 `.mcp.json`；测 `test_pipeline_peers_declared_so_birth_not_red`。

## 边界与拆分

- 事实归属：§7 预筛口径属 `peer_contract §7` + `audit_flow`（纯形式校验）；`.mcp.json` 解释器属下游装配（`cli/mcp` + `scaffold`）；scaffold 出生红属 `scaffold` + `pipeline_schema`。
- 边界检查：预筛只做形式短路、不解释对方内部（`ADR-0006`）；scaffold 不替下游决定绑谁。
- 桩子先行：预筛先造"闭环报告 + 同基线"fixture，断短路与 `--force`；scaffold 先造空下游仓，断首跑不红。

## 验收

- 每项完成后勾除并指向证据；3 项全清后本单 `done`。
