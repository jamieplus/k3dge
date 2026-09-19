---
status: done
milestone: M10
priority: P1
date: 2026-09-18
---

# ADR 修正案：doc 规约化策略重划（C1-C5：0022 §2.2 时机/产物、0005 §2.7 同形同路、耐久改闸、先并入后新建配闸）

- **可检索摘要**: 用户裁定的新 doc 策略（① 受管 doc 新建/修改过格式硬闸 ② 新建须确认与集存 doc 覆盖/重复，有则并入不新建 ③ 规约化改写不每次提交做、放 seal 轮、外部 audit 优先、降级才由 k3dge 自己按规约直接改 ④ ①② 归 k3dge 不涉外部 audit ⑤ 用现成编排机制挂上，不新造流程）与现行 ADR 有 5 处冲突：ADR-0022 §2.2（每次变更 + 报告 + 里程碑票 + 耐久靠票）、ADR-0005 §2.7:73（代码/文档审计同形同路、无独立 doc 路径）、ADR-0005 §2.7:74-75 与 ADR-0001:69（k3dge 只验形式 never merit）、耐久机制缺口、「先并入后新建」纯散文无闸。修法：`Amended-by` 追加（Accepted 不得就地改写），并显式划出「可判定形式规约 → k3dge 直接改；需语义判断 → 外部透镜」这条新线。

## Intent

策略以用户观点为准；ADR 是事实源，冲突必须落成修正案而不是留在对话里（AGENTS.md §13：chat memory 不是证据）。

## 冲突清单（逐条带原文位置）

| ID | 位置 | 原文要点 | 冲突 | 修法 |
|---|---|---|---|---|
| C1 | `docs/adr/0022-task-maps-to-audit-report.md` §2.2（Accepted） | doc-audit 在 check 之后、**每次文档变更**、非阻断；只出两样＝报告 + 里程碑 task；**耐久 = task 归里程碑** | 新策略：**seal 轮**做**规约化改写**，不以审计/报告/票形式出现 | `Amended-by` 追加：时机改 seal 轮；产物改「确定性规约化动作」；不可机检的语义项留里程碑审计 |
| C2 | `docs/adr/0005-local-first-and-layer-cuts.md` §2.7:73（原 0020 harness 职责划分，已物理删除并入本条） | 「代码审计与文档审计**同形同路**…**无独立 doc-audit prompt/transport**」 | doc 规约化拆成 k3dge 内部动作＝承认 doc 有独立路径 | 同条 `Amended-by`：划新线（形式规约 vs 语义判断） |
| C3 | ADR-0005 §2.7:74-75 + `docs/adr/0001-k3dge-architecture-baseline.md:69` | 「doc review ≠ idea scoring：k3dge **只验『报告存在』，不判优劣**」；「`.schema.json` 结构 only，**never merit**」；「只验结构事实，不判决策内容（归 k3dit）」 | k3dge 自己动手改文档内容，表面越过「不判优劣」 | 修正案必须论证：**闭集命名规则 + 幂等 + 每条一测的规约化＝形式层，非 merit**；merit 仍归外部。这条线不写清，C3 是真违规 |
| C4 | ADR-0022 §2.2「耐久 = task 归里程碑」 | 票卡 seal 是唯一耐久机制 | 不再开票 ⇒ 耐久无着落 | 换成**闸**：`[checks.seal].preconditions` 加 `docs_normalized`（detector 零偏差才过）。比票更强——票能被无意义关掉，实证：`docs/tasks/2026-09-14-M10-audit-doc_audit_adr_guides_memo_4.done.md` 绑到待修=0 的代码审计报告 `2026-09-14-M10-audit.md`，其「关闭理由」自述为**过期空壳** |
| C5 | `AGENTS.md` §12 + `docs/adr/AUTHORING.md` | 「先并同类 ADR（先并入，后新建）」 | **纯散文、无机检**；而 §12 末行（2026-09-18 新增）要求「新增可机检规则 → 同轮配闸」 | 配 detector：新建受管 doc 时无重复确认痕迹 ⇒ 提示/拒绝（细则归 `2026-09-18-M10-feat-doc_strategy_five_points`） |

## 不必改的支持性裁定

- **ADR-0008 §2**（`Landed-by: src/k3dge/engine/nextstep.py`）：「触发式维护 + 渐进披露：`[NEXT]` 只推最小下一步 + 指针」——新策略要的「硬闸之后的 [NEXT] 主动动作」正是此形状，无需修正。
- **ADR-0006 sidecar**：work 与 check 不可同席。确定性规约化**不是判定**（闭集规则、幂等、可复跑），不触发该约束；但修正案里要写明这句，否则「k3dge 自己改自己审」会被读成粘合。

## 边界与拆分（规则 08）

- 事实归属：**策略边界（谁改/谁判/何时）归 ADR**；规则表与 detector 归 `src/`（另一票）；触发文案归 `nextstep.STATE_OPTIONS`（单一源，本轮已落）。
- 边界检查：修正案只划归属，不写实现步骤数/内部状态（不让 ADR 知道模块内部）。
- 桩子先行：先落 ADR 修正案（契约冻结），再按 `doc_strategy_five_points` 票实现；实现票 `blocking:` 指本票。

## Notes

- Accepted ADR **append-only**：只能 `Amended by` / `Superseded by`，就地修订须在 frontmatter `Note:` 记「经 Core Maintainer 显式授权 + 过闸口径」（仓内既有惯例，见 0008/0022 的 Note 段）。
- 相关但独立：`2026-09-18-M10-fix-pipelines_stages_dead_config`（C6：AGENTS.md §12 声称的 `pipelines.on_seal_enter/on_pre_seal` 无执行者）——那是编排声明面的问题，不属本票的策略边界。
- 现行 doc-audit 实现（`engine/doc_audit.py`）在本策略下的去留由实现票裁定；本票只改 ADR。
- **2026-09-19 拆出两票**（避免本票面过宽）：编号系统本身 → `2026-09-19-M10-docs-adr_number_cutline`（C5 的"复用无闸"在那票解决）；D 线不变量 + 骨架下游可配 → `2026-09-19-M10-docs-adr0026_d_line_and_downstream`。本票保留 C1-C4（doc 策略的 ADR 冲突）。
- C6（`[pipelines.*]` 无执行者）归 `2026-09-18-M10-fix-pipelines_stages_dead_config`，已裁定取"接通并入节点表"。

## 结案（2026-09-19）：C1-C5 全部落地，逐条对账

| ID | 修法 | 落点（commit） | 状态 |
| --- | --- | --- | --- |
| C1 | ADR-0022 §2.2 时机/产物重划：每次变更+报告+票 → 提交时硬闸 / 新建首次排查 / seal 轮规约化 | `f749e27`（🅰1 + 内联 footnote 🅰1.1/🅰1.3） | ✅ |
| C2 | ADR-0005 §2.7「同形同路」划新线：可判定形式规约归 k3dge 确定性执行，语义质量仍归外部透镜（不推翻同形同路本身） | `f749e27`（🅰1.1 footnote） | ✅ |
| C3 | 论证「闭集规则 + 幂等 + 每条一测的规约化＝形式层，非 merit」；唯一源＝`gate_facts` 的 `fix` 字段（实测 10 确定性可修 : 32 需判断） | `3c64208`（fix 维度）+ `f749e27`（🅰1.3 明写"形式规约不是 merit"） | ✅ |
| C4 | 耐久从"票归里程碑"改为"闸"（`docs_normalized` precondition）；实证：09-14 那张票自述"过期空壳…无可执行内容"且 report 绑到待修=0 的报告 ⇒ 关票不需任何实际工作 | `f749e27`（🅰1.4）——**决策已落，闸的实现归 `doc_strategy_five_points`** | ✅ 决策 / ⏳ 实现 |
| C5 | 「先并入，后新建」配闸：新建受管文档首次排查闸 `DOC_NEW_UNSCREENED`（阻断一次，判定归 agent）+ 编号侧 `ADR_NUMBER_REUSE` / `ADR_REF_RETIRED` | `a04242c`（排查闸）、`48b3301`（编号两码） | ✅ |
| C6 | `[pipelines.*]` 无执行者 → 接通并迁 `[checks.audit].stages_*` | `a9601a0`（独立票 `pipelines_stages_dead_config`） | ✅ |

### 附带修正（本票触发查出、已修）

- ADR-0004 / ADR-0022 的 `Landed-by` 指向本轮删掉的门面 `engine/milestone.py` ⇒ `adr_landed` 曾报 2 条不可解析（会卡 seal）。已改指叶子（`seal_flow.py` / `task_write.py`），属引用面修正、决策未变，故不进 `Amended-by`（`8f75c04`）。
- ADR frontmatter 的 `#` 散文注释被 `doc_catalog._TITLE_RE` 当成 H1 ⇒ 12/14 条 ADR 的索引标题变成注释首行。已修（frontmatter 只放数据）+ 4 条回归守卫（`8f75c04`）。

### 本票不做（归属别处）

- `docs_normalized` 闸与 `doc_normalize` 动作的**实现** → `2026-09-18-M10-feat-doc_strategy_five_points`
- 节点表（`needs/produces/on_error/kind` + ctx + 单执行器）→ `2026-09-19-M10-refactor-orch_node_table`
- `run_doc_audit` 的退休（删路由/建票/报告绑定）→ 同 `doc_strategy_five_points`
