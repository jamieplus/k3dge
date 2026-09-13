---
status: done
milestone: M9
priority: P2
date: 2026-09-12
---

# 补 spec §1 边界：engine/cli In-Scope 漏列模块

- **Status**: done
- **Milestone**: M9
- **Priority**: P2
- **可检索摘要**: engine spec §1 In-Scope 漏列 markers/nextstep/audit_trigger/audit_checklist/audit_flow/store/worktree/pipeline_runner/search；cli §1 命令列表漏 status/doc-audit/markers/search/where/index/commit/mcp。
- **Date**: 2026-09-12

## 意图
补齐 spec §1 人读边界，使其与 `src/k3dge/{engine,cli}/` 现存文件一致（B2/B3）；并补 `docs/architecture/overview.md` engine 描述漏列 `milestone / version / TEMPLATE_DRIFT`（C5）。

## 来源/证据
- memo `docs/memo/archive/2026-09-05-doc-code-misalignment-list.md` B2/B3/C5（2026-09-05）。
- 逐条对照 `src/k3dge/{engine,cli}/` 现存文件与对应 spec §1 / overview engine 行。

## 边界
只改 §1 人读段（`check` 不解析自然语言）；**不动 §2 接口块/契约哈希**。

## 收尾（2026-09-13 已落）
- `docs/specs/engine/spec.md` §1 增「其余引擎面」：`markers`/`nextstep`/`audit_trigger`/`audit_checklist`/`audit_flow`/`worktree`/`pipeline_runner`/`pipeline_schema`/`gates`/`adr_gate`/`search`（B2）。
- `docs/specs/cli/spec.md` §1 命令列表补 `status`/`markers`/`audit`/`search`/`where`/`index`/`commit`/`incident`/`mcp`/`init`（B3）。
- `docs/architecture/overview.md` engine 行补 `milestone / version / TEMPLATE_DRIFT`（C5）。
- 290 passed；check 绿。
