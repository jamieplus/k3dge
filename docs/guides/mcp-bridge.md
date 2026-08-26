# MCP Bridge — 零漂移门禁桥接器

> MCP 是 **对外 Agent harness 的注入面**（DSH、Codex、Claude Code、OpenCode 等），不是本仓第二套人机 UI。把 `engine` 事实源以 stdio JSON-RPC 2.0 交给那些工具，零私有重实现门禁（ADR 0006）。
>
> k3dge **不会**自动改那些工具的配置。用户说「帮我配 MCP」或「接入某某 harness」时，Agent **必须**只走下面剧本，禁止另起一套 JSON 或猜测未列出的路径。
>
> k3dge 源更新之后怎么升下游仓：见 [`downstream.md`](downstream.md)。判定核用 pip 重装；再跑 init **不会**覆盖已有 `AGENTS.md`。

## 固定配置剧本（Agent 照抄，不许改形状）

1. 确认 harness 名称（DSH / Codex / Claude Code / OpenCode / 其它）。未列出的：先问用户配置文件路径，再把**同一段** server 定义写进去。
2. 本仓检出用块 A（自举 `pip install -e ".[dev]"` 已含 mcp）。下游仓用块 B（init 已 `pip install -e "${K3DGE_SOURCE}[mcp]"`）。不要混 `PYTHONPATH` 和全局安装。
3. 只增加名为 `k3dge` 的这一条 server。不要加无关 env、不要包一层自己的 wrapper、不要在对方 harness 里重写 hash。
4. 告诉用户重启该 harness。不要声称已经「自动连上」除非用户确认工具里能看到 `k3dge_check`。

**块 A — 本仓检出**

```json
{
  "mcpServers": {
    "k3dge": {
      "command": "python",
      "args": ["-m", "k3dge.cli.mcp"],
      "env": { "PYTHONPATH": "src" }
    }
  }
}
```

**块 B — 已安装 `k3dge[mcp]`**

```json
{
  "mcpServers": {
    "k3dge": {
      "command": "python",
      "args": ["-m", "k3dge.cli.mcp"]
    }
  }
}
```

写入位置（仅这些；不知道就问，不要编）：

| Harness | 文件 |
| --- | --- |
| Claude Code | 项目根 `.mcp.json`（`mcpServers` 与块 A/B 同形） |
| Claude Desktop | 该产品文档中的 `mcpServers` JSON（块 A/B 原样作为 `mcpServers` 的内容） |
| Cursor | 项目 `.cursor/mcp.json` 或 Cursor 的 MCP 设置，server 块仍是 A/B |
| Codex | 用户给出的 Codex MCP 配置文件；把 A/B 译成该文件已有的 TOML/JSON 语法，**字段仍是 command / args / env** |
| OpenCode / DSH | 用户给出路径；server 定义仍是 A/B |

依赖：`mcp>=1.0`。自举在 `.[dev]` 里；下游 init 装 `[mcp]`。缺包时先 `pip install -e ".[dev]"` 或 `-e "${K3DGE_SOURCE}[mcp]"`，不要改用别的传输。

## 能力清单

| MCP 原语 | 名称 | 委托事实源 | 说明 |
| --- | --- | --- | --- |
| Resource | `spec://manifest` | `.agent/manifest.json` | 实时读盘，UTF-8 字符串返回 |
| Resource | `spec://domain/{domain}` | `docs/specs/<domain>/spec.md` | 单域契约事实源 |
| Tool | `k3dge_check` | `ConsistencyEngine.evaluate()` | `with_tests` = selective L2；`force_full` = 校验全部 `manifest.domains`（L0/L1），与 git diff 解耦，不隐含跑测试 |
| Tool | `k3dge_verify_domain_contract` | `contract.verify_contract()` | 单域 `expected_hash` / `actual_hash` / `current_interface` |
| Tool | `k3dge_sync` | `sync.generator.sync_all` | 回写 spec 接口块与哈希 |
| Tool | `k3dge_version` | `version.show/bump` | 与 CLI `version` 同语义 |
| Tool | `k3dge_task_list` | `milestone.list_tasks` | 顶层 `docs/tasks/*.md` 索引（title/status/milestone/priority），不含正文、不含 archive |
| Tool | `k3dge_task_create` | `milestone.create_task` | 写入 living task 文件 |
| Tool | `k3dge_task_done` | `milestone.mark_task_done` | 优先 `list` 返回的 path |
| Tool | `k3dge_milestone_control` | `milestone.(status|align|seal)` | `status` 查任务、`align` Full Matrix 回归、`seal` 三闸机原子归档 |
| Prompt | `k3dge_5pass_audit_prompt` | 优先 `k3dit/docs/guides/protocol.md`，不存在时 `docs/memo/2026-08-24-audit-harness-independence.md` | 只指路，不在 k3dge 内维护透镜；MCP 仅注入事实源 |

## 路径解析

`_find_workspace(workspace_path?)` 优先使用显式 `workspace_path`（文件自动取 `parent`，目录直接保留），未传入时自 `cwd` 向上探测 `.agent` / `.git` 标记，统一处理 `workspace_path` 为 `str | Path | None`。

## 相关

* 实现：`src/k3dge/cli/mcp.py`
* 契约：`src/k3dge/engine/contract.py`（`include_doc` 与哈希正交）、`src/k3dge/engine/milestone.py`（三闸机）
* 验证：`k3dge check --force-full --with-tests` / `pytest -q`
