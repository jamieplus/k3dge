---
status: done
milestone: M7
priority: P0
date: 2026-09-02
---

# k3dge 自身 MCP server 在 mcp 2.x 下无法启动（resource 严格校验）

- **Status**: done
- **本轮决定**: 维护者指示**搁置**（当前实现不了且不阻断出向链路）；`docs/guides/mcp-bridge.md` 已加「入向现状」节先把事实写清。F1/F2/F3 待后续授权，不占本轮。
- **Milestone**: M7
- **Priority**: P0
- **可检索摘要**: `mcp` 2.x 的 `MCPServer` 严格校验 resource handler 参数，`spec://manifest` 带 `workspace_path` 被拒；给 `cli/mcp.py` 补双路径 import shim 会让收集阶段就 `ValueError`，而不补则 server 从未真起来（现状靠 Dummy 装饰器空转假绿）
- **Date**: 2026-09-02

## 已确认意图

k3dge 的 MCP 面分入向/出向（`ADR-0006` §2.3）。入向 server 现在**在真装 `mcp` 的环境里起不来**，而它的测试全绿 —— 这是 P0：外部 harness 按 `docs/guides/mcp-bridge.md` 接上后拿到的是一个空壳，门禁事实读不到。

## 上下文/切入点

- 实测（各仓自带 `.venv`，`mcp` 2.1.0 / 2.1.1，均无 `mcp.server.fastmcp` 模块）：补 shim 后 k3dit / k3lity / k3che 三仓 server 均 `ALIVE`（`initialize` + `tools/list` + 真调一次工具），**只有 k3dge 仍 DEAD**：
  ```
  ValueError: Resource 'spec://manifest' has no URI template variables,
  but the handler declares parameters {'workspace_path'}.
  Add matching {...} variables to the URI template ...
  ```
- 抛出点：`mcp/server/_fastmcp.py:224 add_resource` → `_resolve_resource_write_path`；触发者 `src/k3dge/cli/mcp.py:57-58`
  `@mcp.resource("spec://manifest")` + `def get_manifest_resource(workspace_path: Optional[str] = None)`；
  `:70-71` 的 `spec://domain/{domain}` 因带模板变量而通过，但它的第二个参数 `workspace_path` 同样多余，**同一改法必须一起看**。
- 契约现状：`docs/guides/mcp-bridge.md` 能力清单把 `spec://manifest` 记为 **无参数**（只写「实时读盘」）；`docs/specs/cli/spec.md` 的契约块收录该符号。⇒ 参数从未被文档承诺，是实现自己加的。
- 测试为何没挡住：未补 shim 时 `FastMCP is None` → `_DummyMCP.resource()` 返回恒等装饰器 → `tests/unit/cli/test_mcp.py` 直接调函数、绕过 server 注册，全套照常绿（实测：不带 shim `182 passed, 1 skipped, 94 subtests passed`；带 shim 同一份测试**收集期报错**）。
- 我本轮的处理：**已回退 `src/k3dge/cli/mcp.py` 的 shim**（`git checkout`），让仓保持绿；回退后 `pytest -q` = `182 passed, 1 skipped, 94 subtests passed`，`k3dge check` 绿。代价：k3dge 入向 server 仍 DEAD，本任务是其唯一载体。

## 候选改法（择一，均需 `k3dge sync`）

- **F1（推荐）resource 去参数**：`get_manifest_resource()` 不留 `workspace_path`，需要显式指定工作区的走新增工具 `k3dge_read_manifest(workspace_path?)`。与已发布文档一致（能力清单本就记为无参数），改动面最小；`spec://domain/{domain}` 的多余参数同批处理。
- **F2 URI 模板化**：改注册为 `spec://manifest/{workspace_path}`。破坏 guide 已写死的 URI 与外部 harness 现有配置，且默认路径要传空串 —— 不推荐。
- **F3 不修本仓、只修 peers**：k3dge 继续留在 `_DummyMCP`（入向面等于不存在），把出向客户端优先级提上来。
  代价：任何按 `docs/guides/mcp-bridge.md` 接入的外部 harness 拿到的是空壳（实测 `initialize` 即 `Connection closed`），
  且 `k3dge_check`/`k3dge_sync` 等 13 个工具对外不可用。**不推荐**，仅作为「本轮不做」的显式选项存在。
- 无论哪种：`main()` 前须真构造一次 server 并 `tools/list`+`resources/list`，把"注册期即崩"变成 CI 可见（见 `docs/tasks/2026-09-02-M7-feat-peer_outbound_mcp_client.md` 的 `k3dge mcp probe`）。

## 验收

- `src/k3dge/cli/mcp.py` 带双路径 import shim（与 k3dit / k3lity / k3che 同构）。
- k3dge server 在 `mcp` 2.x 下 `ALIVE`：`initialize` → `resources/list` 含 `spec://manifest` 与 `spec://domain/{domain}` → 真调 `k3dge_check` 返回合法 JSON。
- `tests/unit/cli/test_mcp.py` 增加一条真注册用例（断言 `type(mcp.mcp).__name__ != "_DummyMCP"`，与 peers 的 `2026-09-02-M7-test_mcp_dummy_blindspot.md` 同形）。
- `pytest -q` 全绿（当前基线 182 passed / 1 skipped / 94 subtests）+ `k3dge check --force-full --with-tests` 绿。
- 若选 F1：`docs/guides/mcp-bridge.md` 能力清单与 `docs/specs/cli/spec.md` 接口块同步，`k3dge sync` 回写契约哈希。

## Related

- 决策源：`docs/tasks/2026-09-02-M7-docs-adr0006_inplace_revise.done.md`
- 吸收来源：`../k3che/docs/reviews/2026-09-01-peer-bringup.md` K3C-BRING-01/02
