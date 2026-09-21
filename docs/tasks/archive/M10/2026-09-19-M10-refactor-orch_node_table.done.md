---
status: done
milestone: M10
priority: P2
date: 2026-09-19
---

# 编排骨架收敛·节点表：pipeline.toml [checks.*] 单一声明面 + 五属性 + ctx + 单执行器（下游可配）

- **可检索摘要**: 把散落 4 处的编排声明收成**一张节点表**（落 `.agent/pipeline.toml` 的 `[checks.*]`），5 个执行器收成 1 个，3 个渲染器收成 1 个（两投影）。节点声明字段：`id / kind(projection|fact) / needs / produces / on_error(stop|rollback|continue) / entry(cli|mcp|hook|internal) / severity / fact+options+pointers / verifier / judge`。四条线不是四套机制，而是同一张表的不同字段组合：A 用 kind+needs/produces+on_error，B 用 severity+fact/options，C 用 entry(+verifier)，**D 不进表**。用户裁定：**编排骨架下游可配**。

## Intent

顶层设计＝内容/流程解耦 + 自动化处理方式收敛（去硬编码）。骨架是 k3dge 的本体，但分支杂乱、关联线未收敛（用户语）。本票落"骨架"本身。

## 已裁定（用户，2026-09-19）

1. 节点表落 `pipeline.toml`（`[checks.*]` 搬进去）；不再维持第二个配置文件（`.agent/gates.toml` 本轮已删，不复活）。
2. **编排骨架下游可配**：下游仓能改顺序、关步骤、换判据引用。
3. 收敛顺序：B（`orch_converge_gate_facts`）→ ③（`pipelines_stages_dead_config`）→ 本票 → `sync` 收编；`task done` **有意留**（原子性 + 回填依赖，收益最小风险最大，届时记 LEFTOVERS）。
4. C 线归约为 A 的入口特例（自主单位调用声明式接口）；不建"交付面契约表"。残渣只留一条约束：**不经接口的交付（直接改盘上事实）必须有验证器**，验证器就是 B 线的闸。
5. D 线（自主↔自主）不进表：k3dge 只做状态可见 / 事实供给 / 幂等步进，**不得编排**（不变量落 ADR-0026，见 `adr0026_d_line_and_downstream` 票）。

## 现状（2026-09-19 更新，散落度实测）

**已做（前两步的产物，本票不再重复）**：

| 项 | 落点 | commit |
| --- | --- | --- |
| 声明面收进 `pipeline.toml` 一处（`[checks.*]` + `[gates.*]`），`gates.DEFAULTS` 为代码内缺省 | `gates.REL` + `pipeline.toml`/资产模板 | `15f37e0` |
| 旧两处声明退休 + 迁移守卫（`.agent/gates.toml` 与 `[pipelines.*]` 存在即红一次） | `pipeline_schema` | `a9601a0` / `15f37e0` |
| 外部步接通且**执行器真读**（`[checks.audit].stages_produce/stages_verify`，删 `milestone_audit` 硬编码 `streams`） | `gates.stages()` + `run_audit_flow` | `a9601a0` |
| 未知 id 拒绝 + 声明的 ref 解析不到 ⇒ `PIPELINE_UNRESOLVED_STAGE`（不让声明空转） | `pipeline_schema` | `a9601a0` |
| 下游可配实测（改声明即换实现；坏配置回落缺省） | `test_gates` / `test_seal_flow` / `test_pipeline_schema` | 同上 |

**仍散落（本票要做）**：

```
执行器 3 处（未合一）：seal_flow.registry / seal.gate_fns / align._reg
                       —— 各自按声明跑内部动作，但注册表与失败语义各写各的
硬编码链 2 处（未收编）：sync 链（generator.py）/ task done 链（task_write.py）
                        —— task done 按裁定**有意留**
节点属性：只有 preconditions / actions / stages_*；缺 kind(projection|fact) /
          needs-produces(ctx) / on_error(stop|rollback|continue)
渲染器：闸红侧已单源（gate_facts.render + Violation.format）；[NEXT] 侧仍是
        nextstep.render_cli/render_mcp 各自调 —— 两投影同形由测试守，未合一实现
```

## 方案

```
[checks.<op>]                      # op ∈ seal | align | sync | doc | …
preconditions = [id…]              # 全绿才继续（既有语义保留）
actions       = [id…]              # 内部动作 id → 注册表；未知 id ⇒ 拒绝（既有语义保留）
stages_enter  = [peer.action…]     # 外部 peer 步（③ 接通后即此）
stages_pre    = [peer.action…]
on_error      = "stop"             # stop | rollback | continue

[[nodes.<id>]]                     # 节点属性（内容）
kind     = "projection"            # projection（可幂等重算）| fact（写一次即历史）
needs    = ["task_path"]           # 只声明键名，不声明结构（否则表开始描述实现）
produces = ["done_path"]
on_rerun = "append"                # 仅 kind=fact 需要：append | reject
entry    = "cli"                   # cli | mcp | hook | internal（C 线）
verifier = "TASK_STATUS_MISMATCH"  # 不经接口的交付由哪个 code 验（C 线残渣）
severity = "block"                 # B 线
judge    = "schema:adr"            # schema:<type> | fn:<id> | lens:<role>
fact / options / pointers          # B 线文案（与 STATE_OPTIONS 同形，最终合一）
```
执行器：按 `needs/produces` 拓扑排序（声明序作为并列时的稳定序）；未知 id 拒绝；失败按 `on_error`；`kind=fact` 且 `on_rerun=reject` 的节点重跑即红。
渲染器：一份实现两投影（进程＝code+事实字段；判断主体＝fact+options+pointers，陈述式）。

## 下游可配的三条硬约束（裁定 2 的落地条件）

1. **代码内缺省必须完整**：`gates.DEFAULTS` 的原则不变——声明缺失/解析失败 ⇒ 回落缺省，**闸不因配置坏而失效**。下游删掉整个 `[checks.*]` 也必须能跑。
2. **未知 id 一律拒绝**（既有语义），不许静默跳过：下游写错 id 要立刻红，而不是"声明空转"。
3. **`pipeline.toml` 与 `assets/pipeline.toml.template` 是 PAIRS 字节锁**：本仓改声明必须同轮改模板；下游拿到的是 init 时的副本，可自由改（不受锁）。⇒ 表的字段一旦发布就是**下游契约**，加字段可以（有缺省），改语义/删字段要走 ADR。

## 边界与拆分（规则 08）

- 事实归属：**走哪些步/什么顺序/失败怎么办/档位/文案** 归声明表；**每步怎么判** 归 `judge` 指向的内容（`.schema.json` / 代码函数 / 外部透镜）；**执行与投影** 归单执行器 + 单渲染器。三者互不知道内部。
- 边界检查：执行器不知道节点语义（只按 id 取注册表项）；声明不含逻辑/表达式（沿用 `gates.py` 原则）；节点表不得引用 peer 内部轮次（ADR-0006 §2.3.8 action-level）。
- 桩子先行：先定表 schema + 校验（`pipeline_schema` 扩 `[checks]`/`[[nodes]]`）+ 执行器骨架，用 `seal` 一条线跑通（它已有注册表，迁移成本最低、回归网最厚）；再迁 `align`、`sync`。每步 `pytest` + `check` 绿。
- 有意留：`task done` 链不迁（裁定 3），届时在 `docs/reviews/LEFTOVERS.md` 记一条，写明"不是没看见，是判过"。

## 验收（2026-09-19 更新：删掉已达成项）

已达成的两条（原第 1、2 条）已由 `a9601a0` / `15f37e0` 完成，不再作为本票判据：
`[pipelines.*]` 与 `.agent/gates.toml` 均已废且各有迁移守卫；`milestone_audit` 的硬编码
`streams` 已删、改读声明。

本票剩余验收：

- 执行器**只剩一个**：`seal_flow.registry` / `seal.gate_fns` / `align._reg` 三处合并为一份
  （同一动作表 + 同一失败语义入口）；
- 节点五属性可声明且被真读：`kind`（projection 可幂等重算 / fact 写一次即历史）、
  `needs`/`produces`（ctx 键，用于拓扑序而非手写顺序）、`on_error`
  （stop / rollback / continue —— 现在三种语义都存在于仓里但无处声明）；
- `kind=fact` 的节点须声明 `on_rerun`（append-only / 拒绝重跑）；`kind=projection` 默认幂等；
- `sync` 链收编进声明面，且**投影重生**与**事实源写入**（`reconcile_supersedes` 改 ADR
  frontmatter + 移文件）在声明里分型 —— 前者可随便重跑，后者不可；
- 下游可配仍成立（坏配置回落缺省、未知 id 拒绝），且新增字段都带缺省；
- 全量 pytest 绿；`k3dge sync` 回写契约哈希；`k3dge check` 绿。

## Notes

- 依赖：`blocking:` 两票（B 线文案单源先落，③ 声明面先接通），否则本票会同时改三处形状。
- 与 `doc_strategy_five_points` 的交点：`doc_normalize` / `docs_normalized` 就是本表的一个节点 + 一个 precondition，不需要新机制。
- 风险登记：`pipeline.toml` 从"peer 配置"升为"骨架声明"，是下游继承面 ⇒ 字段稳定性按 ADR 管（见 `adr0026_d_line_and_downstream`）。

## 落地（2026-09-19）

| 项 | 落点 | 实测 |
| --- | --- | --- |
| 节点声明 | `engine/nodes.NODE_DEFAULTS`（唯一源）+ `.agent/pipeline.toml` 的 `[nodes.<id>]`（下游可覆盖） | `nodes.decl(ws,"archive")` ⇒ `{kind:fact, on_error:rollback, on_rerun:reject, produces:[archived_paths]}` |
| 五属性 | `kind`(projection\|fact) / `on_error`(stop\|rollback\|continue) / `on_rerun`(仅 fact，append\|reject) / `needs`·`produces`（ctx 键名） | `test_nodes`：缺省覆盖已知节点、fact 必声明 on_rerun、下游可覆盖、缺失回落缺省、自举"本仓声明==缺省" |
| ctx 传值 | 节点签名 `fn(ctx)`；`sync` 各步把结果**写回 ctx**，调用方读 ctx（`changed` / `docs_updated`）而非局部变量 | `test_ctx_is_passed_to_nodes`；`gates.sync_all` 返回值来自 ctx |
| **单执行器** | `nodes.run_phase(workspace, op, phase, registry, ctx)`：未知 id 拒绝、两相形状宽容（`(ok,out)` 与 `Optional[str]`）、失败经 `gates.rejection` 正规化、`on_error=continue` 不中断 | 三处旧循环（`seal.gate_fns` / `seal_flow.registry` / `align._reg` 的派发）已消失，**结构守卫**断言它们不再出现 |
| `sync` 链收编 | `[checks.sync].actions`（顺序＝声明序）；`sync_extractors`/`sync_domains`/`sync_manual_docs`/`sync_docs_index`＝**投影**，`reconcile_adrs`＝**事实源写入** | 实跑 `k3dge sync` 行为不变（契约回写 + 生成物重生）；`on_error=continue` 让 extractor 配置坏 / ADR reconcile 失败不挡其余步（与原逻辑一致） |
| 保留项 | `Violation` 侧、`task done` 链**有意留**（票内裁定）；`persist`/`emit` 的 run 语义见 `next_multi_decision` | — |

### 有意留（记此，不在本票做）

1. **`kind=fact` + `on_rerun=reject` 的"重跑即红"未加独立标记**。理由：`archive` 自身在已归档时会报「无任务可封」⇒ 拒绝语义已由动作实现；另建事件标记＝第二个事实存储，属新基建且无第二个消费者（规则 12）。`on_rerun` 现在的作用是**声明 + 守卫**（fact 必声明、下游可见），不是运行时拦截。
2. `preconditions` 的 `kind` 目前恒为 projection（前置闸只读判定，不写盘）；若将来出现"会写盘的前置闸"，按那时的事实补分类。
3. `needs` 只在 `archive` 等处声明了 `produces`；`needs` 尚未被消费（执行器不做拓扑排序——顺序仍按声明序）。理由：仓内链条无并发、无分支，拓扑排序当前无收益；等出现"声明序 ≠ 依赖序"的真实场景再引。

## 验收（实测）

```
619 passed；k3dge check 绿
tests/unit/engine/test_nodes.py（11 条）
  声明：缺省完整（fact 必带 on_rerun）/ 下游可覆盖 / 缺失回落 / 自举本仓声明==缺省
  执行器：preconditions 停在首个失败且 gate_id＝声明的 id / 未知 id 拒绝 /
          两种动作形状都能跑 / on_error=continue 不中断且消息并入输出 /
          on_error=stop 立即中止 / ctx 真被传入
  结构守卫：三处旧派发循环在源码里已消失（逼迫后续新编排也走单一执行器）
端到端：k3dge sync（收编后）行为不变；k3dge milestone align/seal 路径 test_milestone /
        test_seal_flow / test_evaluator 全绿
```
