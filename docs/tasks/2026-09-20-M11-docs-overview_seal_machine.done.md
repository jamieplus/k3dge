---
status: done
milestone: M11
priority: P2
date: 2026-09-20
---

# overview §6 状态机仍是两问/audit_needed，未跟 ADR-0004 🅰1 三相位

- **可检索摘要**: `docs/architecture/overview.md` mermaid 仍是 align → 要不要审 → 要不要封；正文「未审计调 seal → audit_needed」。ADR-0004 🅰1 已改成 seal 三相位唯一入口。M10 审计 doc-3 只改了 T-01 段，同篇状态机没动。`cli/mcp.py:459` 注释同样还写 audit_needed。

## 已确认意图

操作层指针跟 ADR 编号，不复写其已废正文。overview 是全局状态机的人读面，必须与 `run_seal_flow` / AGENTS.md §12 同一张图。

## 证据

```
overview.md §6 mermaid：DRAFT→ALIGNED→AUDIT_SUGGESTED→AUDITING→SEAL_READY→SEALED
文案：「两问拆开」…「未审计调 seal → audit_needed」
ADR-0004 §2.1.9：唯一入口 seal；预审 → 审计 → 审核后自动；未闭环返回在办，不是 audit_needed
mcp.py:459：「If not closed, run_seal_flow returns audit_needed」
代码：run_seal_flow 相位 2 自己跑审计；MCP 传 skip_enter_prompt=True
LEFTOVERS SEAL-01 / T-01 仍引用已废 on_pre_seal、doc-audit
```

## 方案

```
① overview §6/§7 改成与 ADR-0004 🅰1 同一张状态机（seal 唯一入口、三相位）
② 删/改「audit_needed」表述；MCP 注释跟代码
③ LEFTOVERS 里点名已废机制的行，要么改指针要么标已推翻
```

不新开 ADR（并入 0004 的投影，不是新决策）。

## 结案

- overview §6/§7 改成 seal 三相位唯一入口；mcp.py 注释去掉 audit_needed。
