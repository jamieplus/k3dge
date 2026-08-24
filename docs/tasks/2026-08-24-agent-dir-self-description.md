# 把 `.agent/` 目录级初衷写回磁盘

- **Status**: done
- **Priority**: P1
- **Date**: 2026-08-24

## 已确认意图
用户问 `.agent` 的初衷；指出 k3dge 应能自说明，这段信息却丢失了。写回目录自身 + ADR，不靠聊天。

## 入口
- `.agent/README.md`
- `docs/adr/0013-agent-dir-is-self-description.md`
- init 资产 `src/k3dge/templates/assets/agent-readme.md`
