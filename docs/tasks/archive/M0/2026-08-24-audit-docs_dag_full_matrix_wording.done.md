# 修正架构 DAG 与 ADR 0004 的 Full Matrix 措辞

- **Status**: done
- **Milestone**: M0
- **Priority**: P1
- **Date**: 2026-08-24
- **来源**：[docs/reviews/2026-08-24-5pass-audit.md](../reviews/2026-08-24-5pass-audit.md) A-08

## 可检索摘要
两处文档与实现相反，Agent 会按文档做错误的门禁假设。(1) `docs/architecture/overview.md` 依赖图画 `templates → engine`，`src/k3dge/templates/scaffold.py` 不导入 engine。(2) ADR 0004 写 Macro Gate 是「`k3dge check --with-tests` 的全量触发」；实现上 `--with-tests` 只跑 git 触及域的 selective L2（overview 自身 L2 行也这么写），真正的 Full Matrix 在 `k3dge milestone align`。

## 上下文/切入点
- DAG：`docs/architecture/overview.md` §2 mermaid（`cli → engine` / `cli → sync` / `sync → engine` / `templates → engine`）
- 实现 import：`cli.main`/`cli.mcp` → engine；`cli.main.cmd_sync` → sync；`sync.generator` → engine；templates 无 engine
- ADR：`docs/adr/0004-milestone-lifecycle-governance.md` §2.1 Micro/Macro Gate 三条
- 指南同样误写：`docs/guides/mcp-bridge.md`「`force_full` 触发全量门禁」（由 MCP 任务负责改正，本文只改 architecture + ADR）

## 方案
1. 从 overview mermaid 删除 `templates → engine`，或改成无依赖的独立节点并在正文写明「脚手架零运行时依赖」。
2. ADR 0004：Macro Gate 改为「`k3dge milestone align` 对 `manifest.domains` 全量结构+契约+矩阵测试」；明确 `k3dge check --with-tests` = selective L2，不是 Full Matrix。ADR 是已采纳记录，用「修正」小节追加，不要改写原 Decision 而不留痕迹。
3. 不动 `docs/reference/*`（投影，非判据）。

## 触发条件
用户确认后开工。纯文档，不改契约哈希。
