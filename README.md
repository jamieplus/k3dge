# k3dge

> 仓库：<https://github.com/jamieplus/k3dge> · 交换协议权威源：[`docs/protocols/peer_contract.md`](https://github.com/jamieplus/k3dge/blob/main/docs/protocols/peer_contract.md)

Spec-gate harness：为 vibecoding agent 提供确定性的契约漂移检测与 git 硬门禁。

当前阶段是 **自举**（ADR 0007）：用本仓的 k3dge 开发本仓，并作为门禁去开发并列的 audit / quality / cache harness（ADR 0006）。不是 PyPI 产品。存在的目的是给后续项目收住 Agent 漂移、幻觉、修局部坏整体等（ADR 0011），不必穷举失败态。

核心思路：把对 agent 的口头约束（Soft Prompting）降维成文件系统事实（`spec.md` 契约哈希）
与 git hook 硬门禁，杜绝跨会话语义漂移。

## 初始化（Init）

一次性初始化环境——由人执行，或由 agent 按本 README 执行：

```bash
./k3dge-init.sh
```

自举安装：默认 `pip install -e ".[dev]"`（含 pytest、pre-commit、**mcp**；改完立刻用同一份代码，不走 PyPI）。

初始化**另一个空目录**（不要手建 docs/.agent）：进入该目录，跑 **k3dge 仓里的** init：

```bash
mkdir my-audit-harness && cd my-audit-harness
/path/to/k3dge/k3dge-init.sh
```

若已在目标仓跑拷贝来的 `./k3dge-init.sh`，设 `K3DGE_SOURCE=/path/to/k3dge`。

该步骤会：

1. `git init`（`.git` 不存在时）
2. 创建 `.venv`（Python 3.10+）
3. 可编辑安装：自举 `.[dev]`（含 mcp）；下游 `${K3DGE_SOURCE}[mcp]` + pre-commit、pytest
4. 生成 harness 目录结构（manifest / 第一域 / specs / AGENTS.md / 钩子脚本）
5. `k3dge sync`、挂载 pre-commit 与 commit-msg 钩子

完成后即可直接开发，无需每次 `source activate`，也无需再手动安装任何东西。

## 日常流程

```bash
k3dge check              # 运行一致性门禁（pre-commit 提交时也会自动跑；默认证触及域）
k3dge check --force-full --with-tests   # 与 CI / milestone align 同强度
k3dge sync               # 修改公开接口后，同步 spec 契约哈希与接口块
k3dge task list --json   # 顶层 tasks 索引（不含 archive、不含正文）
```

下游仓源更新后怎么升：见 `docs/guides/downstream.md`。无 Milestone 的 `done` 任务在 `docs/tasks/archive/untagged/`。

## Agent 协议

Agent 行为协议见 `AGENTS.md`（唯一协议源，本 README 不再复制）。
`.agent/` 是 k3dge 进程配置（`manifest.json` 给门禁）；Agent 不会靠逛隐藏目录发现它（ADR 0014）。

审计透镜不在 k3dge 包内。sibling audit harness 有 `../k3dit/docs/guides/protocol.md` 则读它；否则读 `docs/protocols/audit_default.md`。

## 布局

> 基础版本随仓库存在；工程收尾时由 `./scripts/generate-docs.sh`（agent 按 `.agent/docs.toml`）刷新下表。

域路由以 `.agent/manifest.json` 为唯一事实源：

<!-- k3dge:layout-start -->
| Domain | Source | Spec | Description |
| --- | --- | --- | --- |
| cli | `src/k3dge/cli` | `docs/specs/cli/spec.md` | 本仓终端/CI + 对外 harness（DSH/Codex/Claude Code/OpenCode）的 MCP 注入 |
| engine | `src/k3dge/engine` | `docs/specs/engine/spec.md` | 门禁核心：diff / manifest / spec_schema / contract / evaluator / milestone / version / TEMPLATE_DRIFT |
| sync | `src/k3dge/sync` | `docs/specs/sync/spec.md` | spec 接口块与契约哈希回写；`docs/generated/` 机器文档（Diátaxis Reference） |
| templates | `src/k3dge/templates` | `docs/specs/templates/spec.md` | 脚手架生成器（k3dge-init.sh） |
<!-- k3dge:layout-end -->

另见：`docs/specs/<domain>/spec.md`（各域契约事实源）。

## MCP Bridge

MCP（`k3dge.cli.mcp`）用来把本仓门禁 **注入** DSH、Codex、Claude Code、OpenCode 等外部 harness：那些工具只配 MCP server，不要自己再写一份 hash。人在本仓用的是 `k3dge` CLI，不是 MCP。

**开发期（本仓检出）**

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

**安装后（`pip install "k3dge[mcp]"`）**

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

能力：`k3dge_check`（门禁）/ `k3dge_verify_domain_contract`（单域契约）/ `k3dge_milestone_control`（`status|align|seal`）/ `spec://manifest` 与 `spec://domain/{domain}` 资源 / `k3dge_5pass_audit_prompt`（9 列注意力隔离）。详见 `docs/guides/mcp-bridge.md`。

## 日志

`k3dge check / sync` 自动追加 `logs/k3dge.log`（`[ISO8601] command status`）。
