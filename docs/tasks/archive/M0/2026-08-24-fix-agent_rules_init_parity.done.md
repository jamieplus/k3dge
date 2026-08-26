# `.agent/rules` 与 init 对齐，不再当第二份协议

- **Status**: done
- **Milestone**: M0
- **Priority**: P1
- **Date**: 2026-08-24

## 已确认意图
用户指出 Agent 从未提 `.agent/rules`，问是否说明没设计问题；确认后允许改。

## 背景
`manifest.json` 是门禁事实源，一直在用。`rules/*.md` 无消费者：Grok 不扫该目录，AGENTS.md §3 也不读。init 写空 Rule 00、漏 Rule 02，与自举仓分叉。Rule 00/01/03 与 AGENTS.md 重复且无「谁赢」。

## 方案（ADR 0012）
- AGENTS.md 为活协议；rules 为切片；冲突 AGENTS.md 赢。
- init 从 `templates/assets/rules/` 写出完整 00–03（含 02）。
- §12：简化/删死代码 → 读 02。
- 测试锁 assets ↔ 本仓 `.agent/rules`。

## 入口
- `src/k3dge/templates/scaffold.py`
- `.agent/rules/`
- `AGENTS.md` / `src/k3dge/templates/assets/agents.md`
- `docs/adr/0012-agent-rules-are-protocol-slices.md`
