---
status: idea
milestone: M10
priority: P2
date: 2026-09-19
---

# ADR-0026 追加：D 线不变量（k3dge 不编排自主↔自主）+ 骨架声明的下游可配边界

- **可检索摘要**: ADR-0026（投影契约，现 `Proposed`）只定了三维投影 + 三层拓扑，缺两块：① **D 线（自主→自主）的不变量**——实例存在（Hall 席位圈 `peer_contract §1.4`：判读落钉→修翻 fixnote→复核翻 fixed→Hall 拔→sign-report，机器不自签；`escalated` 转人工；Accepted ADR 就地修订需人工授权；并入判定需授权席位认可），但 k3dge 在其中**只能做三件事**：状态可见 / 事实供给 / 幂等步进，**不得编排**；② **骨架声明的下游可配边界**——用户裁定"编排骨架下游可配"，而 `pipeline.toml` 与 `assets/pipeline.toml.template` 是 PAIRS 字节锁、且由 init 灌进每个下游仓 ⇒ 节点表字段一旦发布即下游契约，需定"可改什么、缺省从哪来、坏配置怎么办、改语义走什么流程"。按 AUTHORING「先并入，后新建」追加进 0026，不新开 ADR。

## Intent

四条线（A 自动→自动 / B 自动→自主 / C 自主→自动 / D 自主→自主）里，D 是唯一"没有机制"的一条——这不是缺陷，是设计生效的样子（编排在 Hall/人那边）。但没有不变量守着，下一次就会有人在 k3dge 里给席位排步骤。同时骨架声明要变成下游可配面，必须有契约条款，否则本仓的编排骨架会被硬灌给每个下游仓。

## 要追加的两节（内容草案）

### §2.6 D 线：自主↔自主不由 k3dge 编排

```
判据（承 §2.1「可编排 ⇔ 归属与判断同属一个主体，且该主体就是编排者」）：
  D 线的归属与判断分属不同自主单位（审席/修席/复核席/人）⇒ 对 k3dge 恒不可编排。
k3dge 在 D 线里只做三件事（闭集）：
  ① 状态可见：[NEXT] ratchet_open / escalated；k3dge audit status|show
  ② 事实供给：present / materialize（worktree 机械抽取）、账本、钉、events.jsonl
  ③ 幂等步进：advance（一次调用推一步，进程不等人，绝不在闸里等席）
禁止：给席位排步骤、代签（承 ADR-0006 §2.3.6 机器不自签）、把 D 线状态塞进节点表。
实例（现存，均在 k3dge 之外编排）：Hall 席位圈（peer_contract §1.4）、escalated 转人工、
      Accepted ADR 就地修订需显式人工授权、并入既存 ADR 需该 ADR 授权席位认可。
```

### §2.7 骨架声明的下游可配边界

```
裁定（用户，2026-09-19）：编排骨架下游可配。
① 权威与缺省：仓内权威 = 下游自己的 .agent/pipeline.toml；代码内缺省必须完整
   （gates.DEFAULTS 原则：声明缺失/解析失败 ⇒ 回落缺省，**闸不因配置坏而失效**）。
② 未知 id 一律拒绝，不静默跳过（"不让声明空转"）。
③ 字节锁的边界：本仓 .agent/pipeline.toml ↔ assets/pipeline.toml.template 受 PAIRS 锁；
   下游拿到的是 init 时的副本，**可自由改、不受锁**。
④ 字段即契约：加字段可以（必须带缺省）；改字段语义 / 删字段 / 改档位默认值 ⇒ 走 ADR
   （下游的既有配置会静默变义）。
⑤ 不可配的部分（明写，避免"全可配"幻觉）：判据本体（.schema.json 的结构规则、
   evaluator 的检查函数）、投影形状（fact/options 的三维约束）、D 线不变量。
   下游可配的是"走哪些步、什么顺序、失败怎么办、档位、文案指针"。
```

## 边界与拆分（规则 08）

- 事实归属：**投影与可编排性的判据**归 ADR-0026；**节点表字段与执行语义**归 `orch_node_table` 票；**下游升级流程**归 `docs/guides/downstream.md`（本票只写不变量，不复述操作步骤）。
- 边界检查：ADR 只划归属与不变量，不写实现步骤数/内部状态（不让 ADR 知道模块内部）。
- 桩子先行：ADR-0026 现为 `Proposed` ⇒ 允许就地增补（append-only 只约束 Accepted 之后）；增补后由人/k3dit 判是否转 `Accepted`（`adrs_all_accepted` 是 seal 前置闸，不转则 M10 封不了板）。

## 验收

- ADR-0026 含 §2.6 / §2.7 两节，且 `Landed-by` 指针仍可解析；
- 「k3dge 不得编排 D 线」有可机检的落点或明确记为散文规则（按 §12 末行：新增可机检规则须同轮配闸，否则标有意留）；
- `docs/guides/downstream.md` 与 §2.7 不冲突（升级面只写操作，不复述契约）；
- `k3dge check` 绿；ADR 闸（`adrs_all_accepted` / `adr_landed`）状态如实汇报。

## Notes

- 与 `adr_number_cutline` 建议同轮落（都改 ADR 面，避免 0026 被就地改两次）。
- 与 `orch_node_table` 是"契约 vs 实现"关系：本票先定契约，那票按契约落表。
- 若 k3dit/人复核后认为 §2.6 应独立成条（D 线与投影契约不同类），按「先并入，后新建」重新判——本票默认并入。
