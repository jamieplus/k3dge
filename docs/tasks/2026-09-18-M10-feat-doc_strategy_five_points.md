---
status: idea
milestone: M10
priority: P2
date: 2026-09-18
blocking: 2026-09-18-M10-docs-adr_doc_normalize_strategy 2026-09-18-M10-fix-pipelines_stages_dead_config
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

## 待定形（三个必须裁定的点）

1. **可机械修 vs 需判断的切线**。k3dit Doc Audit 透镜的四条软规则实测分类：
   ```
   可判定 + 可机械修（→ 进 DOC_FIX_RULES 或 .schema.json 硬闸）
     Consequences 三段齐 / frontmatter↔body 三头一致（已有 task_meta_dual_source 闸）
     文件名↔标题↔H1 / 指针与引用格式 / 脚注配对 / fence 闭合
     归档去向标记（Superseded-by、Legacy note）/ 索引重生 / aux 名
   不可判定（需读懂语义 → 留外部透镜，只在 seal 轮/里程碑审计用）
     「Context 无 timeline」「Decision 只写不变量与 non-goal」「无过程叙述」
   ```
   对第二类做「直接改」＝agent 自由改写散文：无声变异、无问责、规则变成被优化的靶（Goodhart）。**不得进 fix 动作。**
2. **Accepted ADR 正文不可自动改**。仓内不变量：append-only，只能 `Amended by`/`Superseded by`，就地修订须在 `Note:` 记显式授权 + 过闸口径（见 0008/0022 的 Note 段）。⇒ fix 范围必须显式排除 Accepted ADR 散文段。
3. **有意留的出口**。全变成静默改文件会丢掉「谁改的/为什么/哪条是有意留」（12 列的 `处置/验证/复审/验收` 是决策史）。需要就地标记（如 `<!-- k3dge:doc-fix-off <rule-id> -->`）或 LEFTOVERS 式登记，否则「修不动就删规则」会成默认退路。

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
