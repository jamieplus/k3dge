---
status: done
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

## 落地（2026-09-19）

| 位置 | 改法 |
| --- | --- |
| `gates.DEFAULTS["checks"]["audit"]` | 新增 `stages_produce = ["audit.actions.audit"]` / `stages_verify = ["audit.actions.verify"]`；`gates.stages(ws, kind, phase)` + `gates.all_stage_refs(ws)` |
| `milestone_audit.run_audit_flow` | 删硬编码 `streams`，改读声明；`stages_verify` 为空 ⇒ 跳过二次核对（不拿空 ref 去跑） |
| `.agent/pipeline.toml` + 资产模板 | 删 `[pipelines.on_seal_enter]` / `[pipelines.on_pre_seal]`，留一段说明指向 `[checks.*]`（PAIRS 字节锁，两份同改） |
| `pipeline_schema._validate_pipelines` | 改为**迁移守卫**：下游还留着 `[pipelines.*]` ⇒ 显式红一次逼迁移，不静默失效 |
| `pipeline_schema._validate_declared_stages` | 新增：声明的 stage ref 解析不到 transports ⇒ `PIPELINE_UNRESOLVED_STAGE`（"不让声明空转"的机检半边） |
| `resolve_role` / `resolve_action` | **下沉到闸核层** `pipeline_schema`，`pipeline_runner` 反向 import 并 re-export |
| AGENTS.md §12 / rules/04 / protocols 两份 | 去掉「`pipelines.on_seal_enter` → …」的失准表述，改指 `[checks.audit].stages_*` |

### 偏离票面文字一处（记录）

票里写"迁为 `[checks.seal].stages_enter/stages_pre`"，实际落 **`[checks.audit].stages_produce/stages_verify`**。理由：这两步的消费者是**审计流本身**（`k3dge milestone audit` 也能单独调，不经 seal），挂 `seal` 会谎报归属；且 `stages_produce/stages_verify` 与 `run_audit_flow` 的 produce/verify 两相同名，不用另建映射。

### 途中撞到的架构闸（真红，已按规则修）

`_validate_declared_stages` 要解析 action ref，最初从 `pipeline_runner` import `resolve_action` ⇒ `test_gate_imports` 红：**闸核不得 import 生命周期**（T-02）。按既有方向（`pipeline_runner` 已从 `pipeline_schema` 取 `_VALID_PROVIDERS`）把 `resolve_role`/`resolve_action` 这两个纯配置读取函数下沉到闸核层，runner 反向 import 并 re-export（既有 `pipeline_runner.resolve_action` 引用不破）。

### 另一次自伤（记录，防再犯）

用下标切片改 `pipeline_schema.py` 时把文件前缀（docstring + imports）整段替掉，`from __future__` 落到第 59 行 ⇒ SyntaxError。回滚该文件后改用精确锚点编辑。**教训：跨函数搬迁不要用 `index()` 切片，用显式锚点或 AST。**

## 验收（实测）

```
gates.stages(ws,"audit","produce") == ["audit.actions.audit"]
gates.all_stage_refs(ws)           == ["audit.actions.audit","audit.actions.verify"]
validate_pipeline_config(本仓)      == []
test_downstream_can_rebind_stages   改 .agent/gates.toml 即换实现（下游可配，声明面唯一）
test_audit_flow_calls_the_declared_ref
                                    run_audit_flow 真调声明里的 ref（dummy.actions.lens），
                                    不再出现 k3dit.actions.audit；verify 声明为空 ⇒ 跳过
test_retired_pipelines_section_is_flagged  下游留旧段 ⇒ PIPELINE_SCHEMA_INVALID(retired)
test_unresolved_stage               只声明一条腿 ⇒ PIPELINE_UNRESOLVED_STAGE 且指名 verify
test_declared_stages_resolve_via_role_binding  角色名经 bind 解析 ⇒ 绿
test_no_pipelines_section_left_in_repo_config  仓内与模板都无 [pipelines.*] 段

567 passed；k3dge sync 回写 engine 契约哈希；check 绿
```
