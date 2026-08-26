# 统一 MCP 与 CLI 的错误 JSON 形状，合并 `_find_workspace`

- **Status**: done
- **Milestone**: M0
- **Priority**: P2
- **Date**: 2026-08-24
- **来源**：[docs/reviews/2026-08-24-8dim-vibe-audit.md](../reviews/2026-08-24-8dim-vibe-audit.md) S-09 / S-10
- **相关**：[`2026-08-24-mcp-force-full-and-cli-spec.md`](2026-08-24-mcp-force-full-and-cli-spec.md)（A-02/A-09，可同 PR）

## 可检索摘要
MCP 三种错误形态并存：`get_manifest_resource` 用 JSON `{"error","path"}`，`get_domain_spec_resource` 用 Markdown `# Error:`，工具用 `{"ok": false}` 或 `{"error": "Invalid action"}`。CLI `--json` 固定 `{passed, changed_files, modified_domains, violations}`。Agent 无法用同一解析器消费。另外 `cli.main._find_workspace` 与 `cli.mcp._find_workspace` 重复；MCP 在传入 `workspace_path` 时不要求目录含 `.agent`/`.git`，任意路径都能当 workspace（本地 stdio 已在审计中有意留 S-13，合并函数时不要悄悄加上网络级鉴权，除非用户改口）。

## 上下文/切入点
- `src/k3dge/cli/mcp.py` 资源与工具的 return
- `src/k3dge/cli/main.py` `_to_json` / `_find_workspace`
- 契约：`docs/specs/cli/spec.md` 公共接口（改返回值形态若反映到签名注释则需 `k3dge sync`；Python 签名本身是 `-> str`，哈希可能不变）

## 方案
1. 错误统一为 JSON：`{"ok": false, "error": "<code>", "message": "...", "path": optional}`。Markdown 资源可保留人类可读，但加前缀 JSON 块或全部改 JSON（MCP resource 常是 text，需在 spec 写死一种）。
2. `k3dge_check` 的 JSON 与 CLI `--json` 字段对齐，`render_output` 可保留为附加字段。
3. 抽出共用 `_find_workspace`；显式 `workspace_path` 仍可覆盖，但若既无 `.agent` 也无 `.git` 则返回明确错误 JSON，而不是对任意目录跑 seal（这是对 S-13 有意留的收紧，实施前确认：若仍坚持本地信任，只合并函数、不加探测失败）。

## 触发条件
用户确认错误形态（全 JSON vs 资源保持 Markdown）以及是否收紧显式路径后开工。
