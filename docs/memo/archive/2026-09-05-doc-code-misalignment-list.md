# Memo: 文档↔代码未对齐清单（2026-09-05 对账，待核实回填）

> **Legacy note（归档 2026-09-12）**: B2/B3/C5 落 k3dge `docs-spec_boundary_fill`；A1 已由 ADR-0005 ④ 修订解决，B4/C6/C7 已修；D8 历史报告死链**有意留**（append-only 快照，非阻断）。

- **类型**: 暂无法落地
- **念头**: 全仓 doc↔code 对账发现 8 处未对齐，机器门禁全绿（check/契约哈希/矩阵/钉）未捕获。列入待核实，未来封板轮 doc-audit 或人工复核时逐条核对；处置后本 memo 存档。
- **触发场景**: 用户要求"找出所有文档和代码没对齐的地方列成 list"，完成对账后用户指示记 memo 备核实。
- **Date**: 2026-09-05

## 原始对账结论（快照 2026-09-05，行号基于当日 HEAD）

### A. 硬性矛盾

1. `k3dge audit` 已实现（`src/k3dge/cli/main.py`），但 `docs/specs/cli/spec.md:12` 与 `docs/adr/0005-local-first-and-layer-cuts.md:44` 明令"不加 `k3dge audit`"；ADR-0005 `Amended-by: -` 从未解除。同一 spec §1 与 §2（`cmd_audit` 在接口块）自相矛盾。

### B. Spec §1 边界叙述滞后实现（check 不解析自然语言）

2. `docs/specs/engine/spec.md` §1 In-Scope 漏列模块：`markers / nextstep / audit_trigger / audit_checklist / audit_flow / bundle / store / worktree / pipeline_runner / search`（函数均在 §2）。
3. `docs/specs/cli/spec.md:10` 列 7 条命令，缺 `status / doc-audit / markers / bundle / audit / search / where / index / commit / mcp`。
4. `docs/specs/templates/spec.md:11` 与 `:36` 说 rules 00–03，实际 assets 与 `.agent/rules` 均为 00–09（TC-TPL-03 字节锁绑 09 份）。

### C. 文档 ↔ 文档漂移

5. `docs/architecture/overview.md:33` engine 描述缺 `milestone / version / TEMPLATE_DRIFT`（对照 `.agent/manifest.json:11`）。
6. `docs/guides/mcp-bridge.md` 能力表漏 5 个已注册 MCP 工具：`k3dge_status / k3dge_doc_list / k3dge_doc_where / k3dge_doc_grep / k3dge_submit_audit_report`。
7. `docs/guides/mcp-bridge.md:96` 标题"server 起不来（未修）"与正文 `:98`"已复活"矛盾。
8. `docs/reviews/archive/**` 12 份报告 `../tasks/2026-08-*` 死链（历史快照，非阻断）。

### 已收尾

- `docs/generated/docs-index.json` stale 系本次会话新增文档所致，已 `k3dge sync` 恢复绿。

## 核实方式建议

- A1：确认 `k3dge audit` 确属设计内 → 建议补 ADR 修订后再改 spec §1，否则判定为设计漂移。
- B2–B4：逐条对照 `src/k3dge/{engine,cli,templates}/` 现存文件与对应 spec §1。
- C5–C7：直接改正文或标注有意留。
- D 死链：若需修，走 seal 改写路径，不手工回改 append-only 报告。