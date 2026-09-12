---
status: idea
milestone: M9
priority: P2
date: 2026-09-12
---

# 补 spec §1 边界：engine/cli In-Scope 漏列模块

- **Status**: idea
- **Milestone**: M9
- **Priority**: P2
- **可检索摘要**: engine spec §1 In-Scope 漏列 markers/nextstep/audit_trigger/audit_checklist/audit_flow/store/worktree/pipeline_runner/search；cli §1 命令列表漏 status/doc-audit/markers/search/where/index/commit/mcp。
- **Date**: 2026-09-12

## 意图
补齐 spec §1 人读边界，使其与 `src/k3dge/{engine,cli}/` 现存文件一致（B2/B3）。

## 来源/证据
- memo `doc-code-misalignment-list` B2/B3（2026-09-05）。
- 逐条对照 `src/k3dge/{engine,cli}/` 现存文件与对应 spec §1。

## 边界
只改 §1 人读段（`check` 不解析自然语言）；**不动 §2 接口块/契约哈希**。
