---
Status: Accepted
# Append-only after Accepted. Revise via `Amended by` / `Superseded by` below — do
# NOT rewrite this decision's prose in place, and never reuse a number (see README).
Supersedes: -
Amended-by: -
Date: 2026-08-24
Deciders: Core Maintainer
---

# ADR-0010: `.agent/rules` 是协议切片，不是第二份协议

> **Related**: ADR-0011（`.agent/` 角色）、ADR-0019（协议装载废弃）

## 1. 上下文 (Context)
`.agent/` 里三样东西地位不同：`manifest.json` 是 `k3dge check/sync` 的事实源；`docs.toml` 只给 `generate-docs`；`rules/*.md` 没有自动加载消费者。Grok / Codex / Claude Code / Cursor 自动加载 `AGENTS.md`（或各自的 `.grok/.claude/.cursor/rules/`），**不扫** `.agent/rules/`。

结果：Agent 只读 `AGENTS.md` 时不会打开 rules。init 若写出空标题、漏 Rule 02，自举仓与下游分叉。切片与 `AGENTS.md` 重叠时若没有「谁赢」，会漂。

成对物（AGENTS.md vs `.agent/rules/`）动前必须有 ADR（ADR-0002）。本条是那张卡。

## 2. 决策 (Decision)

1. **活协议只有一份**：仓库根 `AGENTS.md`（ADR-0008 的 §12 触发表在这里）。`k3dge check` 不读 rules，也不该读。
2. **`.agent/rules/*.md` 是切片**，给只扫 `.agent/rules/` 的工具，以及 Rule 02 这份**不进门禁的简化规程**（质量闸仍属并列 quality harness，ADR-0006）。不是第二套指令。
3. **冲突时 `AGENTS.md` 赢**，同一任务改 rule 文件对齐。禁止只改一边。
4. **init 必须写出完整 00–03**，内容与 `src/k3dge/templates/assets/rules/` 及本仓 `.agent/rules/` 相同（含 `02-simplification.md`）。禁止再写空标题。`_write_if_missing` 仍不覆盖已有文件。
5. Agent 何时读 02：用户要求简化 / 删死代码 / 拆冗余，或里程碑 C2 勾了深层嵌套坏味道 → 先按 02 举证再动（写入 AGENTS.md §12）。00/01/03 不要求已加载 AGENTS.md 的 Agent 再读一遍。

## 3. 产生后果 (Consequences)

- **正**：k3dit `k3dge-init` 后有完整 Rule 02，overview 指针不再断；协议单一；成对物有据。
- **负**：AGENTS.md 与四份 rule 仍可能手工漂。用 `test_template_sync` 锁「assets/rules ↔ `.agent/rules`」和「assets/agents.md ↔ AGENTS.md」。
- **何时重开**：若主流 Agent harness 开始默认扫描 `.agent/rules/`，再考虑是否把 §12 表下沉到 rules、AGENTS.md 改成索引。在那之前不要把 AGENTS.md 拆空。
