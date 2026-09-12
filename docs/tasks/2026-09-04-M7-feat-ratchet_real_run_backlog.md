---
status: idea
milestone: M9
priority: P1
date: 2026-09-04
---

# 首案真跑前遗留（k3dge 侧）——复核后剩余

- **Status**: idea
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

1. **§7 复用预筛三条件**：人工入口 `k3dge milestone audit <id>` 命中「闭环报告 + `provenance.baseline` == 线上基线 + `lens_version` == 当前」⇒ 告知"无审计需要执行" + `--force`，痕迹 `PRE-FILTER` 落 `logs/k3dge.log`。现状：`peer_contract §7` 有规范、**代码无实现**。
2. **`.mcp.json` 解释器固化**：k3dit/k3che server 由 `"command":"python"` + `PYTHONPATH` 改为各仓 venv **绝对路径**（demo 已验证该形）。现状：`.mcp.json` 仍是 `"python"`。
3. **scaffold 出生即红（`PIPELINE_PEER_UNWIRED`）**：新下游仓 pipeline 默认绑 k3dit/k3che，但 scaffold 的 `.mcp.json` 不声明 peers ⇒ 首跑 `check` 报红。修法二选一：scaffold 生成**无 role 绑定的空 pipeline**，或 init 在缺 `.mcp.json` 条目时自动注 stub。

## 边界与拆分

- 事实归属：§7 预筛口径属 `peer_contract §7` + `audit_flow`（纯形式校验）；`.mcp.json` 解释器属下游装配（`cli/mcp` + `scaffold`）；scaffold 出生红属 `scaffold` + `pipeline_schema`。
- 边界检查：预筛只做形式短路、不解释对方内部（`ADR-0006`）；scaffold 不替下游决定绑谁。
- 桩子先行：预筛先造"闭环报告 + 同基线"fixture，断短路与 `--force`；scaffold 先造空下游仓，断首跑不红。

## 验收

- 每项完成后勾除并指向证据；3 项全清后本单 `done`。
