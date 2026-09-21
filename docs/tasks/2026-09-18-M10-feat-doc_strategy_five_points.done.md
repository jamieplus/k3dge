---
status: done
milestone: M10
priority: P2
date: 2026-09-18
---

# doc 策略五点落地：格式硬闸 / 新建重复覆盖确认（并入优先）/ seal 轮规约化（外部优先，降级 k3dge）/ 用现成 checks 编排

- **可检索摘要**: 用户裁定的 doc 策略五点：① 受管 doc 新建/修改过格式硬闸（**现状已有**：pre-commit 三层 + `docs/<type>/.schema.json`，触发条件＝有 staged docs）② 新建须确认与集存 doc 覆盖/重复，有则并入不新建（**机制存在但只接在 task 上**：`cache.search`→`[DUP-CHECK]` 仅 `cli/main.py:425`/`mcp.py:271`；docs 侧 `_related_doc_hints` 只装饰 doc-audit 票尾；「先并入后新建」在 ADR/AGENTS 里纯散文无闸）③ 规约化改写不每次提交做、放 seal 轮、外部 audit 优先、**降级才由 k3dge 按规约直接改**（现状：`manual` fallback 只打印协议指针给人，k3dge 不动手）④ ①② 归 k3dge，不涉外部 audit 模块（②的候选源 k3che 是 `kind="service"`，失败即 skip、永不进放行链）⑤ 用现成编排机制挂上，不新造流程（同构先例：`adr_gate.reconcile_supersedes` 挂 `sync/generator.py:200`、`task done`）。

## Intent

把「文档内容合规」从**不可达的审计**（报告 + 票，实测透镜从未到达操作者）换成**可达的动作**（按闭集规约直接改，diff 即证据）。耐久机制从「票卡 seal」换成「闸卡 seal」。

## 现状核对（逐点，带位置）

| 点 | 现状 | 缺口 |
|---|---|---|
| ① 格式硬闸 | `scripts/pre-commit`：层1 doc-gate（每个 `docs/<type>` 须有 README+AUTHORING）→ 层2 schema gate（staged 字节级：`.schema.json` + `pure_schema`/`pure_refs`：结构、名实一致、悬空 ADR/报告指针、脚注、fence、冲突标记）→ 层3 `k3dge check`（仅 code/spec/agent 变更时） | 无 `.schema.json` 的类型**无闸**（`_load_type_schema` 返回 None＝no gate）；新建/修改不分流 |
| ② 重复覆盖确认 | `cache.search`(k3che) → `[DUP-CHECK]` 提示，**仅 `task create`**；`_similar_task_hints` 自述「只提示，不判定：是不是真重复由看的人决定（规则 08：观测≠裁决）」 | doc 新建无入口；「并入」无动作无痕迹（可复用 `Superseded-by` + `reconcile_supersedes`：自动标记旧文 + 移入 `obsolete/`，已幂等）；k3che 不可达时无 k3dge 兜底候选源（`doc list`/`doc grep`/`docs/generated/docs-index.json` 均在） |
| ③ seal 轮规约化 | 外部：`[peers.k3dit.actions.audit]` `mcp → manual(protocol=docs/protocols/audit_default.md)`；k3dit 有 doc 专用透镜（`is_doc_scope` → `lens_count=1` + `report_path` 约定 + `report_scaffold`） | 时机错位（现行 ADR 定的是每次变更后置非阻断）；`manual` 降级＝**打印协议指针给人**，不是 k3dge 自己改；主链（棘轮 submit→Hall→collect）是里程碑作用域，**没有 doc 的门**，只能借 k3dit 自标 `LEGACY manual 档` 的直名 |
| ④ 归属 | ① 已是纯 stdlib 零 peer | ② 依赖 k3che（service 角色，非 audit 模块）——需在 ADR 里写明判定权归 k3dge/agent，k3che 只供候选 |
| ⑤ 编排 | **活的**声明面：`gates.py:25 DEFAULTS["checks"][<kind>]{preconditions,actions}` + 执行器注册表（`seal_flow.py registry` / `seal.py:182 gate_fns` / `align.py:44 _reg`），未知 id ⇒ 拒绝 | **死的那套**：`[pipelines.*].stages` 只有 `pipeline_schema.py:95` 校验、无执行者（见 `pipelines_stages_dead_config` 票）——不先收口就会长出第三套硬编码 |

## 已裁定（用户，2026-09-19）——原"三个待裁定切线"作废

- **不存在"可机械修 vs 需判断"的切线问题**：确定性修复的对象是**硬闸检出项**（已枚举的闭集码），对它们只有一问——进程能修还是不能修。软规则（Context 无 timeline / Decision 只写不变量 / 无过程叙述）**不在 doc fix 里**，属外部透镜，seal 轮过。
- **规约化的形状 = 阻断闸 + 投喂事实源**（B 线）：闸拦住并指路，投喂的事实源把调查范围限定住；投喂必须是**已有投影**（docs-index / adr_index / markers 账 / 12 列报告 / events.jsonl），不新造调查通道。
- **新建受管文档的排查闸已落**（commit `a04242c`）：`DOC_NEW_UNSCREENED` 阻断、只拦第一次、回执 `.protocol-ack/doc-screen/`（ephemeral）、`k3dge doc screen <path> [--into]`。判定权归 agent（进程判不了语义覆盖/子项关系）。**撤回**原方案的 `Screened:` frontmatter 字段（过度设计）。
- **耐久机制**：从"票卡 seal"改为"闸卡 seal"（`[checks.seal].preconditions += docs_normalized`，detector 零偏差才过）。
- **C 线归约**：自主→自动不是独立机制，是"自主单位调用 A 线声明式入口"；不经接口的交付（直接改盘上事实）必须有验证器，验证器就是 B 线的闸。**残渣待补**：`.ack` 的 `--into` 目标存在性无校验。
- **编排挂法**：`doc_normalize` / `docs_normalized` 就是统一节点表里的一个 action / 一个 precondition（见 `orch_node_table`），不新造流程机制。

## 原切线分析（存档，判据已被上面取代）

1. ~~可机械修 vs 需判断的切线~~。k3dit Doc Audit 透镜的四条软规则实测分类：
   ```
   可判定 + 可机械修（→ 进 DOC_FIX_RULES 或 .schema.json 硬闸）
     Consequences 三段齐 / frontmatter↔body 三头一致（已有 task_meta_dual_source 闸）
     文件名↔标题↔H1 / 指针与引用格式 / 脚注配对 / fence 闭合
     归档去向标记（Superseded-by、Legacy note）/ 索引重生 / aux 名
   不可判定（需读懂语义 → 留外部透镜，只在 seal 轮/里程碑审计用）
     「Context 无 timeline」「Decision 只写不变量与 non-goal」「无过程叙述」
   ```
   对第二类做「直接改」＝agent 自由改写散文：无声变异、无问责、规则变成被优化的靶（Goodhart）。**不得进 fix 动作。**
2. **Accepted ADR 正文不可自动改**（仍成立；格式面改动不记 Amended-by，内容面改动才记——用户裁定 2026-09-19）。仓内不变量：append-only，只能 `Amended by`/`Superseded by`，就地修订须在 `Note:` 记显式授权 + 过闸口径（见 0008/0022 的 Note 段）。⇒ fix 范围必须显式排除 Accepted ADR 散文段。
3. **有意留的出口**（仍成立）。全变成静默改文件会丢掉「谁改的/为什么/哪条是有意留」（12 列的 `处置/验证/复审/验收` 是决策史）。需要就地标记（如 `<!-- k3dge:doc-fix-off <rule-id> -->`）或 LEFTOVERS 式登记，否则「修不动就删规则」会成默认退路。

## 方案骨架（用现成机制，不新造）

```
规则表（唯一源，闭集）  DOC_FIX_RULES = {id: (detector, fixer)}
  每条：可判定 / 幂等（跑两遍第二遍零 diff）/ 有测试 / 支持 --dry-run
命令                    k3dge doc fix [--dry-run] [--rule <id>]
编排（⑤）               [checks.seal].preconditions += "docs_normalized"   ← 耐久改闸（C4）
                        [checks.seal].actions       += "doc_normalize"      ← seal 轮执行
                        执行器分支：先 run_action(外部 doc 透镜)；降级 ⇒ 跑 DOC_FIX_RULES
提示（ADR-0008 §2）     [NEXT] state=doc_fix：陈述式事实 + 成对选项（走已落地的
                        STATE_OPTIONS/ask_text 单源，不另写文案）
重复确认（②）           doc 新建入口挂 cache.search 出候选（观测）+ agent 裁定并入/新建；
                        并入复用 Superseded-by → reconcile_supersedes（挂 sync，幂等）
退休                    engine/doc_audit.py 的 k3dit 路由 + 建票 + 报告绑定（那条路未走通：
                        payload 被丢弃、票绑错报告、09-14 票自述「过期空壳」）
```

## 边界与拆分（规则 08）

- 事实归属：规则表归 `src/k3dge/engine/`（detector/fixer 同处）；何时跑归 `gates.checks` 声明；文案归 `nextstep.STATE_OPTIONS`；策略边界归 ADR（`adr_doc_normalize_strategy` 票）。
- 边界检查：`doc fix` 不得读审计模块内部（报告格式/待修计数/席位状态）；外部透镜降级只经 `run_action` 的传输链，不在 fix 里判 peer 死活。
- 桩子先行：先落 `DOC_FIX_RULES` 空表 + `k3dge doc fix --dry-run`（零规则也须幂等、零 diff）+ `docs_normalized` 闸（空表⇒恒绿），再逐条下沉规则；每条规则同轮配 detector 测试（§12 末行：新增可机检规则须同轮配闸）。
- **不进 pre-commit 自动改 staged 内容**（钩子改暂存区＝作者看不见自己被改了什么）；只做 `[NEXT]` 建议动作 + seal 轮闸。

## Notes

- 依赖：`blocking:` 两票——ADR 修正案（策略边界）+ `pipelines.*` 死配置（编排声明面收口）。
- k3dit 的 Doc Audit 透镜**不废**：它是「不可判定那半」的清单来源，逐条评估后能下沉的下沉，剩下的留 seal 轮/里程碑审计（rules/09 吸收路径）。
- 实证依据（为什么现路不可留）：`docs/reviews/2026-09-10-doc-audit-docs.md` 是唯一真走通的一次（7 条发现全已修 + 独立回填 + `INC-20260910-CON-audit-merge-doc-drift`），且是**绕开 `k3dge doc-audit` 命令**由席位跑的；命令自身产出的两张票里 09-14 那张自述「过期空壳…无可执行内容」。

## 依赖更新（2026-09-19）

- `blocking:` 去掉 `adr_doc_normalize_strategy`（已关：C1-C6 逐条落地，见该票结案表）。
  它当初卡的是"策略边界"，现已落进 ADR-0022 §2.2 🅰1 / ADR-0005 §2.7 🅰1。
- 仍挂在 `orch_node_table` 上：本票的 ③（`docs_normalized` + `doc_normalize`）要挂进统一节点表，
  而那张表正在补五属性与 ctx。
- 票内「方案骨架」里的 `DOC_FIX_RULES` 应改名对齐现状：确定性可修清单的**唯一源**已是
  `gate_facts` 的 `fix=deterministic`（实测 10 个：`DOC_INDEX_STALE`/`CONTRACT_DRIFT`/
  `CONTRACT_HASH_MISSING`/`VERSION_MISMATCH`/`ADR_SUPERSEDE_UNRECONCILED`/`MD_CRLF`/
  `MD_ENCODING`/`MD_NO_FINAL_NEWLINE`/`MD_TRAILING_WS`/`TASK_BODY_META_REDUNDANT`），
  不再另建一张规则表（避免第二源）。

## 解锁（2026-09-19）

`orch_node_table` 已关（`nodes.run_phase` 单执行器 + `[nodes.*]` 声明 + ctx 传值已落）⇒
本票的 ③ 现在有了落点：`docs_normalized` 作 `[checks.seal].preconditions` 的新节点、
`doc_normalize` 作 `[checks.seal].actions` 的新节点，各在 `[nodes.*]` 声明 `kind`/`on_error`
（规约化改写写盘 ⇒ `kind=fact` 还是 `projection` 取决于是否幂等——**先定形再落**）。

`blocking:` 已清空（原指向的票已关；task_dag 的观测面会把它报成"指向已关票"）。

## 进度（2026-09-19）：③ 的 k3dge 侧已落（`doc_fix` + `docs_normalized` 闸 + [NEXT] 主动动作）

| 项 | 落点 | 实测 |
| --- | --- | --- |
| 确定性修复器 | `engine/doc_fix.py`：闭集 4 条文件级规则（`MD_TRAILING_WS` / `MD_CRLF` / `MD_NO_FINAL_NEWLINE` / `TASK_BODY_META_REDUNDANT`）+ `scan()` / `apply(dry_run)` | 幂等（再跑零改动）；`--dry-run` 不写盘；扫描面排除 aux/archive/generated/obsolete |
| 与声明表对齐 | 守卫测试：`FIXABLE_RULES` 每条都必须在 `gate_facts` 里声明为 `deterministic`（两处状态机不得分叉） | — |
| **分类修正** | `MD_ENCODING` 由 `deterministic` 改判 **judgment** | 理由：源编码判断不了，猜错会损坏文件（latin-1 解码永不失败 ⇒ 重编码成 UTF-8 会改义） |
| 耐久闸 | `[checks.seal].preconditions += "docs_normalized"`（三处：代码缺省 / `pipeline.toml` / 资产模板）+ `[nodes.docs_normalized]` 声明 + `seal._docs_normalized_error` | 造一处行尾空白 ⇒ 闸红且 `gate_id=docs_normalized`、提示 `k3dge doc fix`；修完 ⇒ 过 |
| 主动动作 | `k3dge doc fix [--dry-run]` + `[NEXT] state=doc_fix`（priority 2） | 提示实测：`fact: docs/ 有 1 处**可确定修**的规约偏差（MD_TRAILING_WS）…`，3 个成对选项 |

### 定形记录（本票 ③ 的两处"先定形"结论）

1. **规约化是前置闸 + 主动动作，不是 seal 的动作环里的自动改**。理由（比 ADR-0022 🅰1.3 的原措辞更严）：
   若在 seal 的动作环里改文档，那是在**审计闭环之后**动手 ⇒ 刚闭环的审计证据（审的是旧文档）失效。
   故必须在封板前做完，由 `[NEXT]` 引导的 `k3dge doc fix` 完成，seal 只验"做没做"。
   ADR-0022 §2.2 里"放 seal 轮"应读作**封板前必须做完**（该 ADR 的措辞是否需要一句澄清，另行裁定）。
2. **"外部透镜优先"不适用于本步**：外部透镜**判**（出报告），不做改写。故本步只做 k3dge 的闭集
   确定性修；语义类偏差（要读懂内容的）留给同轮的外部透镜判 —— 与 ADR-0005 §2.7 🅰1.1「可判定的
   形式规约归 k3dge、语义质量归外部透镜」一致。

### 收尾（2026-09-19）：退休 `run_doc_audit` + `.ack --into` 校验（剩余两项已落）

**退休 doc-audit 的报告+票路径**（ADR-0022 §2.2 🅰1.1 的落地）：

| 面 | 处置 |
| --- | --- |
| `engine/doc_audit.py` | **删整个模块**（`run_doc_audit` / `_ensure_doc_audit_task` / `_attach_k3che_hints` / `_related_doc_hints` / `_changed_docs` 均为该路径专用） |
| `_similar_task_hints`（task DUP-CHECK 在用） | **迁出**到 `engine/task_write.py`（它属 task 创建域，不属 doc-audit） |
| `_new_archive_without_note`（ADR-0023 §2.2 归档去向标记，warn 级） | **迁到** `pure_refs.find_unguarded_archives()`，由 **pre-commit 消费**（口径改显式传本轮 staged 列表）+ `gate_facts` 新码 `ARCHIVE_NO_DEST`(warn)。**不静默丢能力** |
| CLI | 删 `cmd_doc_audit` 与 `doc-audit` 子命令；`[NEXT]` 的 `doc_audit` 提示与 `STATE_OPTIONS["doc_audit"]` 一并撤 |
| 文档面 | `AGENTS.md §12` 该行改述为三层（提交闸 / `doc_fix` 主动动作 / 里程碑审计）；`rules/04` 的 doc-audit 段重写；`audit_default.md` 的"触发"句改指里程碑审计（其 scope 含 `docs`）；`peer_contract` 的 k3che 消费者去掉已退休那项（各两份 PAIRS 同步） |
| 规格 | `k3dge sync` 重生后 `docs/specs/{cli,engine}/spec.md` 已无 `cmd_doc_audit` / `run_doc_audit` |

**`.ack --into` 校验**：新增 `pure_refs.screen_target_exists()`；CLI 在写回执前校验，
目标不存在则拒记并退 1（此前可写 `merged-into docs/adr/9999-nope.md` 而无人发现）。

### 途中两次自伤（记录，防再犯）

1. **切片删函数删错范围**：删 `_emit_doc_audit_hint` 时用 `index(下一个 def)` 定位，
   而那个 def 在文件很远的后方 ⇒ 连带删掉 `cmd_check` / `_read_submit_input` / `_lifecycle_next`
   （98 行）。已回滚重做，改成"删到**下一个顶层 def**"的辅助函数。
2. **宽 `except Exception: pass` 掩盖真错**：退休那段时删掉了 `get_current_milestone` 的 import
   （它当时在被删的 doc_audit 块里），新代码 `NameError` 被 `_collect_hints` 的兜底 try 吞掉，
   表现是"提示消失但无任何报错"。已补 import；教训：**观测件的兜底不得静默**。
