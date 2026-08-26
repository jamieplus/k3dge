# `.agent/` 按实测改为机器配置，不再冒充 Agent 发现面

- **Status**: done
- **Milestone**: M0
- **Priority**: P1
- **Date**: 2026-08-24

## 已确认意图
用户指出：号称给 Agent 用的 `.agent/`，Agent 却没能第一时间发现，说明目录没有按设计起作用。这是设计问题。

## 方案（ADR 0014，修正 0013）
发现面 = `AGENTS.md`。`.agent/` = 进程配置（manifest 仍不可省）。撤回「打开该目录即自说明」。

## 入口
- `docs/adr/0014-agent-dir-is-harness-config.md`
- `.agent/README.md`、`AGENTS.md`
