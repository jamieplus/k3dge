# MCP Bridge — 零漂移门禁桥接器

> MCP 是 **对外 Agent harness 的注入面**（DSH、Codex、Claude Code、OpenCode 等），不是本仓第二套人机 UI。把 `engine` 事实源以 stdio JSON-RPC 2.0 交给那些工具，零私有重实现门禁（ADR-0006）。
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

## 出向：k3dge 作为客户端连 peers（ADR-0006 §2.3）

上面整篇都是**入向**（别人调 k3dge）。k3dge 也会反过来当 MCP 客户端，用 stdio 拉起 peers 自己发布的 server（`milestone audit` / `seal` / `doc-audit` 三条流程）。两条铁律：

| 铁律 | 事实源 | 落点 |
| --- | --- | --- |
| endpoint（`command`/`args`/`env`/`cwd`）只写在 `.mcp.json` | `.mcp.json` 的 `mcpServers.<peer>` | `engine/pipeline_runner.load_mcp_endpoints` |
| 流程（哪个 stage、调哪个 `tool`、`args`、fallback 链、超时）只写在 `pipeline.toml` | `.agent/pipeline.toml` 的 `[peers.*.actions.*]` | `engine/pipeline_runner.run_action` |

- **身份不借道**：`action_ref` 的第一段就是 peer 名，也是 `.mcp.json` 的键。名为 X 的动作只会连 X 的 server；早期那版「用 `shutil.which` 把某一个 bind 冒充所有 peer 的 mcp 传输」已删除，单测 `PeerIsolation` 守住它。
- **解释器落地会出声**：`.mcp.json` 里写 `"command": "python"`，而本机 PATH 无 `python` 时，客户端回退到 `<workspace>/.venv/bin/python` 并把这件事打在同一条消息里（`resolve_endpoint_command` 的 `(fallback: ...)` 注记），不改写你的配置文件。要把真相写进配置：`command` 用绝对解释器路径 + 显式 `cwd`。
- **`cwd` 默认 = 消费仓**，所以 `env.PYTHONPATH` 的相对值（如 `../k3che/src`）与外部 harness 读同一份文件时解析一致。
- **降级不可静默**（§2.4）：从 `mcp` 掉到 `cli`/`manual` 必打 `WARN[DOWNGRADE] action=… from=… to=… reason=…`，reason 带 peer 自己的报错与 stderr 尾行，并追加进 `logs/k3dge.log`；落到 `manual` 时提示语里明写「不是独立审计」。`manual` 不需要事先申请，但你必须在总结里高亮它。
- **工具的业务失败＝传输失败**：`tools/call` 返回 `is_error`（SDK 2.x 模型是 snake_case，1.x 是 `isError`，两处都读）时按失败处理并降级，绝不记成「lens 可用」。

自检命令（只诊断，不进 `check`）：

```bash
k3dge mcp probe            # 逐个 server 真握手：ALIVE/DEAD + tools 列表 + 失败原因
k3dge mcp probe --json     # 同上的机读形态；全活 exit 0，有死 exit 1
```

> `k3dge check` 不调它（§2.3.2：`check` 是纯静态硬闸，永不调用 agent/透镜/peer 帮忙验证）。

## 能力清单

| MCP 原语 | 名称 | 委托事实源 | 说明 |
| --- | --- | --- | --- |
| Resource | `spec://manifest` | `.agent/manifest.json` | 实时读盘，UTF-8 字符串返回 |
| Resource | `spec://domain/{domain}` | `docs/specs/<domain>/spec.md` | 单域契约事实源 |
| Tool | `k3dge_check` | `ConsistencyEngine.evaluate()` | `with_tests` = selective L2；`force_full` = 校验全部 `manifest.domains`（L0/L1），与 git diff 解耦，不隐含跑测试 |
| Tool | `k3dge_status` | `cli.status.workspace_status` | 合成工作区状态：domains / drift / pipeline / 未完成任务 |
| Tool | `k3dge_verify_domain_contract` | `contract.verify_contract()` | 单域 `expected_hash` / `actual_hash` / `current_interface` |
| Tool | `k3dge_sync` | `sync.generator.sync_all` | 回写 spec 接口块与哈希 |
| Tool | `k3dge_version` | `version.show/bump` | 与 CLI `version` 同语义 |
| Tool | `k3dge_task_list` | `milestone.list_tasks` | 顶层 `docs/tasks/*.md` 索引（title/status/milestone/priority），不含正文、不含 archive |
| Tool | `k3dge_task_create` | `milestone.create_task` | 写入 living task 文件 |
| Tool | `k3dge_task_done` | `milestone.mark_task_done` | 优先 `list` 返回的 path |
| Tool | `k3dge_doc_list` | `doc_catalog.list_docs` | 文档目录薄索引（path/id/title/status/tokens），不回正文 |
| Tool | `k3dge_doc_where` | `doc_catalog.where_doc` | 文档 id 解析为目录卡片（只回 path） |
| Tool | `k3dge_doc_grep` | `doc_catalog.grep_docs` | 扫托管文档正文，只回 path（可选 line），不回 snippet |
| Tool | `k3dge_milestone_control` | `milestone.(status|align|seal)` | `status` 查任务、`align` Full Matrix 回归、`seal` 三闸机原子归档 |
| Tool | `k3dge_submit_audit_report` | `milestone.persist_external_audit_report` | 外来审计报告机械落盘为在档报告 |
| Prompt | `k3dge_5pass_audit_prompt` | 优先 `../k3dit/docs/guides/audit-method.md`，否则 `docs/protocols/audit_default.md` | 只指路；同一审计入口，按 `target_scope` 路由代码 5-Pass / 文档 Doc Audit（ADR-0005）；不在 k3dge 内维护透镜 |
| Tool | `k3dge_adr_index` | `engine.doc_catalog.analyze_adr_coverage` | ADR 集合自洽事实（重叠/指针 findings，非判断）；文档审计透镜原料 |

## 入向现状：server 已复活（2026-09-05，mcp 2.x 严格资源校验已修）

2026-09-05 起本仓 server 复活：mcp 2.x 严格校验「resource URI 无模板变量 ⇒ handler 零参数」，修复形为 **resource 处理函数去 `workspace_path`、workspace 一律按 server CWD 解析**（宿主按项目目录起 server，定位靠 CWD 不靠猜参）。`spec://domain/{domain}` 保留模板变量。历史三选项见 `docs/tasks/archive/M7/2026-09-02-M7-fix-k3dge_mcp2_resource_strict.done.md`（该票随 M7 封板归档，其"已修"判定当时不成立——M7 closure 补记二已认错）。

## 路径解析

`_find_workspace(workspace_path?)` 优先使用显式 `workspace_path`（文件自动取 `parent`，目录直接保留），未传入时自 `cwd` 向上探测 `.agent` / `.git` 标记，统一处理 `workspace_path` 为 `str | Path | None`。

## 相关

* 实现：`src/k3dge/cli/mcp.py`
<!-- k3dit:fixnote doc-1 指针改指现存模块：milestone.py 门面已随 drop_milestone_facade 拆入下列件 -->
* 契约：`src/k3dge/engine/contract.py`（`include_doc` 与哈希正交）、`src/k3dge/engine/seal_flow.py`（`run_seal_flow` 三相位：预审 → 审计 → 审核后自动）、`src/k3dge/engine/seal.py`（封板前置清单与归档）
* 验证：`k3dge check --force-full --with-tests` / `pytest -q`
