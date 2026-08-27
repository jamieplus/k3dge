# Domains Reference

> Auto-generated from `.agent/manifest.json` — do not edit.
> For cross-domain consistency rules see `docs/architecture/overview.md`.

| Domain | Source | Spec | Description |
| --- | --- | --- | --- |
| cli | `src/k3dge/cli` | `docs/specs/cli/spec.md` | 本仓终端/CI + 对外 harness（DSH/Codex/Claude Code/OpenCode）的 MCP 注入 |
| engine | `src/k3dge/engine` | `docs/specs/engine/spec.md` | 门禁核心：diff / manifest / spec_schema / contract / evaluator / milestone / version / TEMPLATE_DRIFT |
| sync | `src/k3dge/sync` | `docs/specs/sync/spec.md` | spec 接口块与契约哈希回写；docs/generated 机器文档 |
| templates | `src/k3dge/templates` | `docs/specs/templates/spec.md` | 脚手架生成器（k3dge-init.sh） |
