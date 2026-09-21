---
status: done
milestone: M10
priority: P2
date: 2026-09-16
---

# 重构：提取 MCP peer 管理出 cli/main.py

- **可检索摘要**: `cli/main.py` 1439 行混合 CLI 分派、MCP peer 管理、workspace 辅助、attest 逻辑。提取 11 个 MCP peer 函数到新模块 `cli/mcp_peers.py`，main.py 降至 1240 行（-199），职责分离。

## 意图

main.py 是 god file：52 个函数跨 4 类职责。MCP peer 管理（探测 sibling 仓、合并 .mcp.json、降级警告）是自成一体的子域，应独立成模块。

## 改动

### 新模块 `cli/mcp_peers.py`（222 行）

提取 11 个函数：

| 函数 | 职责 |
|---|---|
| `_peer_fallback_warn` | 降级高亮警告（红底黄字 + 纯文本双写） |
| `_peer_fallback` | 从 transport 链解析终端 fallback 描述符 |
| `_probe_peer_mcp` | 定位 sibling peer 的 MCP 模块与 PYTHONPATH |
| `_peer_mcp_entry` | 构造 .mcp.json server 条目 |
| `_ensure_peer_pythonpath` | 给已有条目补 PYTHONPATH |
| `_load_tomllib` | py3.11 tomllib / tomli fallback |
| `_mcp_servers` | 只读 .mcp.json mcpServers |
| `_sync_peers_into_mcp` | pipeline.toml peers 合并进 .mcp.json |
| `_warn_missing_peer_servers` | 警告已启用但缺失的 peer |
| `cmd_mcp_sync` | `k3dge mcp sync` 实现（原 `_cmd_mcp_sync`，去下划线＝公开） |
| `cmd_mcp_probe` | `k3dge mcp probe` 实现（原 `_cmd_mcp_probe`） |

### `cli/main.py`

- 删除上述 11 个函数体（-199 行）
- 顶部 import 收窄到实际用到的 4 个：`_load_tomllib`、`_warn_missing_peer_servers`、`cmd_mcp_probe`、`cmd_mcp_sync`
- `cmd_mcp` 分派器留在 main.py，改调新名（`_cmd_mcp_*` → `cmd_mcp_*`）

### 顺手清掉的死 import

初次提取时把 11 个符号全 import 进 main.py，但其中 7 个搬走后 main.py 已不再使用（`_peer_fallback_warn`/`_peer_fallback`/`_probe_peer_mcp`/`_peer_mcp_entry`/`_ensure_peer_pythonpath`/`_mcp_servers`/`_sync_peers_into_mcp`）。逐个计数确认后删除——避免制造新的路线残留。

## 边界与拆分（feat 类必填；规则 08）

- 事实归属：`cli/mcp_peers.py` 拥有 peer 探测/合并/降级语义；`cli/main.py` 只保留 argparse 分派；`.mcp.json` 读口仍归 `engine/mcp_json`（value-9 不变）
- 边界检查：mcp_peers 不 import main（单向依赖）；main 只 import 需要的 4 个符号
- 桩子先行：先建模块搬函数 → 改 import → 改分派器调用 → 收窄 import → 全量测试

## 验证

- `.venv/bin/python -c "import k3dge.cli.main"` OK
- 全量测试 395 passed（提取前后一致，零回归）
- `k3dge sync`：cli 域契约哈希已回写
- 顶层 import 检查：`os`/`re`/`json`/`hashlib` 仍在用，无失效 import

## Notes

- 行为零变化：纯搬迁 + 命名去下划线（`_cmd_mcp_*` → `cmd_mcp_*`，因其已成为跨模块公开 API）
- main.py 剩余可继续提取的子域：attest 系列（`_attest_*` 8 个函数）、doc 命令族。本票不做，避免一次改动面过大

## 结案

- 关闭提交：`ebaff64`（2026-09-18）
- 落地记录：见该提交 message 与本文正文（回填于 2026-09-19，事实取自 `git log --diff-filter=AR -1 -- <path>`）。
