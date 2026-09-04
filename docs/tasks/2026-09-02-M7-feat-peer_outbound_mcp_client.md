---
status: in-progress
milestone: M7
priority: P1
date: 2026-09-02
---

# k3dge 出向 MCP 客户端与 endpoint 唯一事实源

- **Status**: in-progress
- **Milestone**: M7
- **Priority**: P1
- **可检索摘要**: `pipeline_runner._run_mcp_best_effort()` 用 `shutil.which("k3dit")` 冒充全部 peer 的 mcp 传输，需换成真 stdio MCP 客户端，且连接配方只从 `.mcp.json` 取
- **Date**: 2026-09-02

## 已确认意图

k3dge 自己作为 MCP 客户端连 peers（`ADR-0006` §2.3），取代"agent 是编排者"的现状。

## 上下文/切入点

- 缺陷现场：`src/k3dge/engine/pipeline_runner.py:109 _discover_k3dit_cli()` / `:152 _run_mcp_best_effort()` —— 工具名 `k3lity_score` / `k3che_search` 会被译成 `k3dit k3lity_score` 执行，违反 `ADR-0006` 的「harness 身份不混用」。
- 依赖已在：`k3dge[mcp]` 即含客户端（实测 `mcp.client.stdio.stdio_client` + `ClientSession`，`StdioServerParameters` 字段 = `command/args/env/cwd/encoding*`）。
- 实测代价：per-call spawn 冷启动 + initialize + 一次 `call_tool` ≈ **0.81–1.01 s**（k3che，3/3 成功），5 Pass audit 量级可接受。
- 失败形态实测：server 启动即死 → 客户端只见 `ExceptionGroup → MCPError: Connection closed`，分不清"没装"与"崩了" ⇒ 本任务须把 peer 子进程 stderr 一并带回（`stdio_client(errlog=...)`）。
- endpoint 形状：`src/k3dge/templates/scaffold.py:141,147` 与 `src/k3dge/cli/main.py:510 _peer_mcp_entry()` 现写死裸 `"python"`（本机 `python` 不在 PATH，实测 `bash -lc 'which python'` 为空）；`docs/guides/mcp-bridge.md` 块 A/B 亦为该形状（改它 = public 文档形状变更，连带下游仓）。
- 契约面：`docs/specs/engine/spec.md:144` 已把 `run_action` 立为公开符号 ⇒ 改动需 `k3dge sync`。

## 验收

- `[peers.X.actions.Y] provider="mcp"` 只可能命中 X 自己的 server 或 X 自己的 CLI；跑一条 `k3lity` 的 mcp 传输绝不会执行 `k3dit` 进程（单测断言，用假 endpoint 注入）。
- `.mcp.json` 是 endpoint 唯一事实源：`pipeline.toml` 内不出现 `command`/`env`/`cwd`。**已按实现改口径**：传输级 `args`（peer 工具的默认参数，如 `k3che_search` 的 `query`）允许且已实现——它是流程参数不是 endpoint；`pipeline_schema` 只校验 `args` 必须是 table（已做）。**未做**：静态校验「mcp 传输的 peer 必须在 `.mcp.json` 有同名 server」（现在只在运行时报 peer not wired）。
- 新增 `k3dge mcp probe`（真 spawn + `initialize`/`tools/list`，逐 server 超时并回传 stderr）；**不接入 `check`**（`ADR-0006` §2.3 保留）。
- ~~test_seal_flow 仅覆盖 cli/skip~~ 已补 `mcp` 传输与降级用例（`tests/unit/engine/test_pipeline_runner.py` 13 例 + `test_seal_flow.py` 的动作级参数/落点建议 2 例）；**仍缺**：`escalated`（同席产物不放行 `seal`）用例，属 §2.4.3 未实现部分。

## 边界与拆分

- 事实归属：endpoint 事实 → `.mcp.json`；流程 → `pipeline.toml`；传输执行 → `engine/pipeline_runner.py`；放行判定 → `engine/milestone.py`。k3dge 只持编排状态。
- 边界检查：不得知道 peer 的轮次/席数/宿主形状；`run_action` 入参只有调用方领域事实（`docs/protocols/peer_contract.md` §0 边界清单）。
- 桩子先行：骨架由 `tests/fixtures/dummy_peer.py`（同契约 canned 工件）跑通，真 peer 缺席时链必须仍可测。

## Related

- `docs/tasks/2026-09-02-M7-docs-adr0006_inplace_revise.done.md`（决策源）
- `docs/tasks/2026-09-02-M7-docs-align_rules_overview_outbound.md`（人读面同步）

## 进度 2026-09-02（本轮落地部分）

已实现并实测（`src/k3dge/engine/pipeline_runner.py` 重写 + `k3dge mcp probe`）：

- **真 stdio 客户端**：`call_mcp_tool()` = spawn → `initialize` → `tools/list` → `tools/call`，`asyncio.wait_for` 限时，返回 `(ok, text, tools, peer_stderr)`。
- **endpoint 唯一源**：`load_mcp_endpoints()` 只读 `.mcp.json[mcpServers.<peer>]`；`pipeline.toml` 不再需要也不能带 `command`。
- **身份隔离**：`run_action` 用 `action_ref` 首段当 peer 名取 endpoint；删掉 `_discover_k3dit_cli`（旧代码把 `k3lity_score` 译成 `k3dit k3lity_score` 跑）。回归测试 `PeerIsolation`（含 `fake.assert_not_called()`）。
- **解释器落地出声**：`resolve_endpoint_command()` 在 `python` 不在 PATH 时回退 `<workspace>/.venv/bin/python`，注记 `(fallback: ...)` 随消息打印，**不改写用户的 `.mcp.json`**。
- **降级不可静默**：`WARN[DOWNGRADE] action=… from=… to=… reason=…` → stderr + `logs/k3dge.log`；`reason` 带 peer 自己的报错文本与 stderr 尾行（旧文案只有一句 `no MCP client available`，什么都没说出）。顺带修了 `logs/k3dge.log` **被整体覆写**的缺陷（原 `_log_harness_skip` 用 `write_text`，审计痕迹一条剩不下），改追加，测试断言旧行仍在。
- **业务失败=传输失败**：`tools/call` 的 `is_error` 视为失败并降级（SDK 2.x 模型 snake_case，1.x 是 `isError`，两处都读）。
- **参数流向**：`args`（写在 `pipeline.toml` 传输里）+ `run_action(arguments=...)`（调用方）+ 默认 `workspace_path=<消费仓>`；测试 `ArgumentsFlow`。
- **诊断命令**：`k3dge mcp probe [--json] [--timeout N]`，逐个 server 真握手；**不接入 `check`**（§2.3.2 纯静态硬闸）。

实测（本机、非 mock）：

```
$ k3dge mcp probe
  [DEAD ] k3dge    :: MCPError: Connection closed | stderr: RuntimeError: mcp package not installed…   ← 入向，见 F1/F2/F3
  [ALIVE] k3dit    tools=['k3dit_check_report','k3dit_run_audit','k3dit_run_doc_audit']
  [ALIVE] k3che    tools=['k3che_search','k3che_stats']
  [ALIVE] k3lity   tools=['k3lity_check_report','k3lity_score']

# run_action(...) 真调：k3lity.actions.quality → provider=mcp 返回质量 findings
#                       k3che.search          → provider=mcp 返回 hit_rate 检索命中
# k3dit.actions.audit   → provider 落 manual，WARN[DOWNGRADE] reason=k3dit 自己的
#                          「2 validation errors … pass_number Field required」
```

闸：`k3dge sync` 回写 `engine` 契约（`run_action` 加 `arguments`，新增 5 个公开函数）、`k3dge check` ✅、`pytest -q` **195 passed / 1 skipped / 94 subtests**（新增 `tests/unit/engine/test_pipeline_runner.py` 11 例）。

## 同日第二批（动作级入口已到位）

- k3dit 侧新增 `k3dit_run_audit_flow(target_scope, workspace_path, milestone_id, ...)`：一次调用回 5 轮透镜 + 12 列 scaffold，`pass_number` 退回内部原语。留痕与验证：`../k3dit/docs/tasks/2026-09-02-feat-audit_flow_tool.md`（33 passed）。
- 本仓接线：`.agent/pipeline.toml` + 模板副本（PAIRS 同改）的 `k3dit.actions.audit` 指向 flow 工具；`run_audit_flow` 只传 `target_scope` / `milestone_id`（**不传轮次**），verify 阶段把**已找到的报告路径**交给 `k3dit_check_report` / `k3lity_check_report`；doc-audit 传 `target_scope="docs"` 走文档透镜。
- `TransportResult` 加 `payload`（未截断原文），`detail` 留人类可读预览；拒绝信息里引用 peer 建议的落点与本会话降级记录。
- `pipeline_schema` 新增：传输里的 `args` 必须是 table（防手抄错成字符串）。
- 实测：`run_action("k3dit.actions.audit", arguments={"target_scope":"milestone M7","milestone_id":"M7"})` → `provider=mcp lens_count=5 downgrades=0 report_path=docs/reviews/2026-09-03-M7-milestone-m7.md（k3dit 的建议落点，盘上尚无此文件）`。
- 本仓 `pytest -q` **202 passed / 1 skipped / 94 subtests**（新增 flow 参数、payload、schema、三出口同构用例）。

## 进度 2026-09-03（骨架已绿：桩子先行完成）

已落地并全测（214 passed 内）：

- `engine/bundle.py`：送检包（目标源＋AST 签名骨架＋脱敏＋噪音排除＋确定性打包）；`cas://sha256:` 内容寻址，超量不内联（`MAX_INLINE_BYTES`）；配置 `.agent/bundle.toml`（ignore/max_bytes/scrub_keys/mode）。
- `engine/audit_flow.py`：submit/collect 两态编排（等待活在协议外；`job_id` 不透明；信封三验：kind / `provenance.baseline`==送检包哈希 / 12 列表头；机械落盘对端字节；基线不符＝拒收不静默）。
- `pipeline_runner`：角色解析 `[roles.*] bind`（代码路径不出现具体 harness 名）；`TransportResult.payload` 未截断通道；**取消隐式 `workspace_path` 注入**（入参只有调用方显式给出的领域事实）。
- `tests/fixtures/dummy_peer.py`：同契约桩（job 持久化跨 spawn；`DUMMY_PENDING` 控待修行数）；`[roles.audit] bind` 已进真配置（`.agent/pipeline.toml` + 模板，PAIRS 同构）。
- 硬闸：`PIPELINE_PEER_UNWIRED`（mcp 传输的 server 必须在 `.mcp.json` 登记；`roles.bind` 指向未登记 server 即红）＋ 传输不得泄漏 endpoint 字段（`command/env/cwd`）；任务「边界与拆分」节存在性闸（`TASK_SECTION_MISSING`，仅 `-feat-`）。

## 仍未做（保持 in-progress 的原因）

1. **audit 需要「动作级」入口**（`ADR-0006` §2.3.8）：一次 `run_action` = 「审这份目标」，而不是 k3dge 循环传 `pass_number=1..5`——5 轮是 k3dit 的私有实现。本轮已实现并保留 `arguments` 通道（含 `pipeline.toml` 里的传输级 `args` 与默认 `workspace_path`），主需求转为请 k3dit 提供 `k3dit_run_audit_flow`：`../k3dit/docs/tasks/2026-09-02-feat-audit_flow_tool.md`。在此之前，`k3dit.actions.audit` 会持续以 `WARN[DOWNGRADE] mcp->manual reason=…pass_number Field required` 落 manual（原因可见，不是假成功）。
2. **结果落盘契约**：peer 返回的 findings JSON 与 12 列报告的对应关系（谁写表、谁填 `处置`）未定；定了才能把 `mcp` 的结果直接变成盘上产物，而不是只停在 `TransportResult.detail`。
3. **`escalated` 的人确认环节**：§2.4.3 的"审计链整体落 manual 且人未确认作数 ⇒ `seal` 不放行"还没进代码（现行为：链自动落 manual + 高亮警告）。
4. **`pipeline_schema` 静态校验**：`mcp` 传输要求的 peer 必须在 `.mcp.json` 里有同名 server（现在只在运行时报"peer not wired"）。
5. **CAS 预筛（契约 §7，v0.3.1）**：k3dge 侧＝人工入口三条件比对＋`--force`＋PRE-FILTER 痕迹；k3dit 侧＝发布 `lens_version`（跨仓，需其授权）；k3che 侧＝`cas_get/set` 台账（跨仓，需其授权；预筛不依赖它）。
6. **`.mcp.json` 形状**（维护者决定：文档先行，暂不改配置）：`command` 是否改写为绝对解释器 + 显式 `cwd`，涉及 `templates/scaffold.py` 与 guide 块 A/B 的 public 形状。

## Related（新增）

- 文档：`docs/guides/mcp-bridge.md` §出向 / §入向现状
- 人读面同步：`docs/tasks/2026-09-02-M7-docs-align_rules_overview_outbound.md`
