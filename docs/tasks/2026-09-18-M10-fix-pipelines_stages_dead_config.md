---
status: idea
milestone: M10
priority: P1
date: 2026-09-18
blocking: 2026-09-19-M10-refactor-orch_converge_gate_facts
---

# pipelines.on_seal_enter/on_pre_seal 无执行者：AGENTS.md §12 声称的 seal hook 机制不存在（接通或废声明，只留一套声明面）

- **可检索摘要**: `.agent/pipeline.toml` 声明 `[pipelines.on_seal_enter] stages=["k3dit.actions.audit"]` 与 `[pipelines.on_pre_seal] stages=["k3dit.actions.verify"]`，`AGENTS.md` §12「`seal` hook」行明写它们驱动必做审计与 verify；实测全仓只有 `engine/pipeline_schema.py:95 _validate_pipelines` **校验其形状**，无任何执行器读取——真正的调用是硬编码 action ref（`engine/milestone_audit.py:213 streams = {"audit": ("k3dit.actions.audit","k3dit.actions.verify")}`）。即文档声称的机制缺「到达」环（AGENTS.md §13），且仓内并存两套声明式编排版（活的 `gates.py DEFAULTS["checks"]` vs 死的 `pipelines.*`），新增编排会撞上第三套。

## Intent

编排声明面只留一套，且**声明的必须有执行者**（rules/10：散文描述不存在的机制＝症状；§13：产物 + 消费者 + 到达三环齐）。

## 证据（实测 2026-09-19）

```
声明（.agent/pipeline.toml:88-98）
  [pipelines.on_seal_enter] stages = ["k3dit.actions.audit"]
  [pipelines.on_pre_seal]   stages = ["k3dit.actions.verify"]

消费者搜索（grep -rn "pipelines" src/ tests/ scripts/ --include=*.py）
  pipeline_schema.py:43,95,97-99,145   ← 仅形状校验（PIPELINE_SCHEMA_INVALID）
  evaluator.py:540,547                 ← 仅把校验结果转 Violation
  tests/unit/engine/test_pipeline_schema.py:55,182 ← 仅测校验
  cli/mcp.py:599                       ← 注释里提一句
  ⇒ 无执行器

实际调用点（硬编码 action ref）
  milestone_audit.py:213  streams = {"audit": ("k3dit.actions.audit", "k3dit.actions.verify")}
  milestone_audit.py:227  run_action(workspace, produce_action, ...)
  seal_flow.py            for aid in gates.actions(workspace, "seal")   ← 读的是 gates 那套

文档声称（AGENTS.md §12「`seal` hook」行）
  「pipeline.toml pipelines.on_seal_enter → k3dit.actions.audit(一份必做)；
    pipelines.on_pre_seal → k3dit.actions.verify」
```

对照：**活的**那套声明面确实被消费——`gates.py:25 DEFAULTS["checks"]`（seal: 7 preconditions + 4 actions；align: 1+1）→ 执行器注册表 `seal_flow.py registry` / `seal.py:182 gate_fns` / `align.py:44 _reg`，未知 id ⇒ 拒绝（「不让声明空转」）。同构先例：`adr_gate.reconcile_supersedes` 挂 `sync/generator.py:200`（幂等，`test_adr_gate.py:68`）。

## 待定形（本票阻塞点，二选一）

| 方案 | 内容 | 代价 |
|---|---|---|
| **(a) 接通 B** | `milestone_audit`/`seal_flow` 改为读 `[pipelines.<hook>].stages` 派发（stages 里就是 action ref，`run_action` 已能跑），删 `streams` 硬编码 | 要定义 hook 名闭集与未知 hook 的处理；`gates.checks.actions` 与 `pipelines.stages` 的分工要写清（前者＝k3dge 内部动作 id，后者＝外部 peer action ref） |
| **(b) 废 B** | 删 `[pipelines.*]` 声明 + `_validate_pipelines`，改 `AGENTS.md` §12 指向 `gates.checks`；外部 action ref 仍由代码按角色解析（`resolve_role`） | 失去「换 hook 顺序/加 stage 不改代码」的可配面；AGENTS.md §12 与 pipeline.toml 注释都要改 |

**定形已裁定（用户，2026-09-19）：取 (a) 接通，且并入统一节点表**——`[pipelines.on_seal_enter]` / `[pipelines.on_pre_seal]` 迁为 `[checks.seal].stages_enter` / `stages_pre`（节点表见 `2026-09-19-M10-refactor-orch_node_table`），执行器改读声明，删 `milestone_audit.py:213` 的硬编码 `streams`。理由：`stages` 已是 action ref 列表，`run_action` + 角色解析（`resolve_role`/`resolve_action`）已就绪，接通成本低于废除成本；且骨架声明要求"只留一套声明面"。

**附带裁定**：编排骨架**下游可配** ⇒ 声明缺失/解析失败必须回落代码内缺省（`gates.DEFAULTS` 原则：闸不因配置坏而失效），未知 id 一律拒绝不静默跳过。

本票是收敛顺序的**第二步**（B 线文案单源之后、节点表全量之前）：它只把 `[pipelines.*]` 这一处死声明接通/迁移，不顺带落 `needs/produces/on_error` 等节点属性（那是 `orch_node_table`）。

## 边界与拆分（规则 08）

- 事实归属：**hook → stages 的声明归 `pipeline.toml`**；**内部动作 id 归 `gates.checks`**；**派发执行归 `pipeline_runner`/`seal_flow`**。三者不得互知内部（派发器不知道 stage 语义，只按 ref 跑传输链）。
- 边界检查：接通后 `milestone_audit` 不得再出现具体 harness 名（仍走角色，ADR-0006 §2.3.8 action-level）。
- 桩子先行：先加「stages 声明但无执行者 ⇒ 红」的守卫测试（把本票的病灶变成闸），再改执行器；否则修完还会漂回来。

## Notes

- 与 `2026-09-18-M10-docs-adr_doc_normalize_strategy`（C1-C5）正交：那票划策略归属，本票修编排声明面（C6）。
- 与 `2026-09-18-M10-feat-doc_strategy_five_points` 有依赖：新动作要挂哪套声明面，取决于本票定形。
