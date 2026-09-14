---
status: done
milestone: M9
priority: P3
date: 2026-09-02
---

# k3che 补 cli 传输面（mcp/cli 成对）

- **Status**: idea
- **Milestone**: M9
- **Priority**: P3
- **可检索摘要**: peers 中只有 k3che 没有 `cli.py` 与 `k3che` 控制台脚本，MCP 不可用时它无退路（`pipeline.toml` 里 `[peers.k3che]` 只有 `mcp→skip`），与 k3dit/k3lity 不成对
- **Date**: 2026-09-02

## 依据修订（2026-09-03，降级 P2→P3）

`peer_contract` v0.3 确立角色分两类后，本任务原依据（"违反 §2.3.5 peer 双传输不变量"）**不再成立**：cache 是 service 角色，`mcp→skip` 是正确终态，不阻断任何门禁链。剩余价值改述为：无 MCP 的宿主里 k3che 完全不可达——那是 **k3che 产品完善度**问题，不是 k3dge 闸要求。`ADR-0006` §2.3.5 已同步收窄为 gate 角色适用。

## 已确认意图

`ADR-0006` §2.5 立了不变量：**每个 peer 都要 mcp 面与 cli 面成对**——MCP 给外部 harness 与 k3dge 出向通道用，CLI 给本机终端/CI 与无 MCP 的 harness 用。k3che 缺后者。

## 上下文/切入点

- 现状：`../k3che/src/k3che/` 只有 `mcp.py/index.py/cache.py/observer.py/stats.py`，**无 `cli.py`**；`../k3che/pyproject.toml:12-13` 的 `[project.scripts]` 只有 `k3che-mcp`（k3dit/k3lity 各自都有 `<pkg>` + `<pkg>-mcp` 两条）。
- 后果实测：本机 `command -v k3dit k3lity k3che` 全为空 ⇒ 所有 peer 的 `cli` 传输都不可用；而 k3che 连"装了就能用"的 CLI 都不存在 ⇒ 在无 MCP 的 harness（如当前 agent 运行时）里 k3che 完全不可达，`[peers.k3che] transports = [mcp, skip]` 只能落 `skip`（`logs/k3dge.log` 记 `HARNESS_SKIP`）。
- 落点：新增 `../k3che/src/k3che/cli.py`（子命令 `search` / `stats`，直接委托既有 `k3che.cache` 公开 API，零新判定逻辑）+ `[project.scripts] k3che = "k3che.cli:main"`；k3che 自己的 `docs/specs/k3che/spec.md` 接口块随之 `k3dge sync`。
- 同时：`k3dge/templates/assets/pipeline.toml.template:49-52` 与本仓 `.agent/pipeline.toml` 的 `[peers.k3che]` 补 `{ provider = "cli", command = "k3che stats", timeout = 10 }`（PAIRS 逐字节耦合，两份同改）。

## 验收

- `pip install -e ../k3che` 后 `k3che search "<query>" --json` 与 MCP `k3che_search` 返回同一结构（同 schema，不含 snippet 为默认）。
- `[peers.k3che]` 的链变成 `mcp → cli → skip`，且 `mcp` 失败时 `cli` 真能被 `pipeline_runner._run_cli` 跑通（单测注入假 workspace + 已装脚本，或 mock `shutil.which`）。
- k3che 仓 `pytest -q` 全绿 + 其仓内 `k3dge check` 绿。

## 边界与拆分

- 事实归属：cli 面是 k3che 仓的事实；k3dge 只知道 `cli` 传输的 command 存在与退出码。
- 边界检查：k3che 的 cli 不得 import k3dge（地位对等，`ADR-0006` §2.2）；command 在 k3dge 的 pipeline 声明，实现在 k3che。
- 桩子先行：先在 k3dge 侧测试加 `cli` 传输 + 降级断言（mock command），再实现 k3che `cli.py`。

## Related

- `docs/tasks/2026-09-02-M7-feat-peer_outbound_mcp_client.md`（出向通道对 peer 的传输要求）

## 收尾（2026-09-13 拆出跨仓）
- 归 k3che 产品完善度 → k3che `feat-cli_transport`；k3dge 保持 `[peers.k3che]` `mcp→skip`（service 语义，Note 2026-09-03 已收窄）。
