# k3dge audit triage 违 ADR 0005，不得冒充审计 harness

- **Status**: done
- **Milestone**: M1
- **Priority**: P1
- **Date**: 2026-08-25

## 已确认意图
ADR 0005：不加 `k3dge audit`。cli 现有 `cmd_audit` / `audit triage`，把 reviews 表行扫成 tasks。透镜仍应在 k3dit/memo，不在 k3dge 包。

## 方案
二选一并落 ADR 修正或删命令：(a) 删 `audit` 子命令，分拣改走文档协议；(b) 改 ADR 0005，写明本命令只做 reviews→tasks 机械分拣、零透镜。若留命令，cli spec In Scope 补一行 + 矩阵 TC（或与 P4-06 一并由 spec 声明薄路由）。

## 入口
- `src/k3dge/cli/main.py` `cmd_audit`
- `docs/adr/0005-local-first-and-layer-cuts.md`
- `docs/specs/cli/spec.md`

## 来源
[docs/reviews/2026-08-25-pass2-architecture-dag.md](../reviews/2026-08-25-pass2-architecture-dag.md) P2-PUR-06
