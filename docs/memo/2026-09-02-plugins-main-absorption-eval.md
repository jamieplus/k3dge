# Memo: plugins-main → 四 harness 吸收评估（ledger v2，穷尽版）

- **类型**: 可落地（吸收待办清单；执行后逐项转 tasks/ADR）
- **念头**: 逐条盘点 `workspace/plugins-main`，判断哪些**模式**能被 k3dge/k3dit/k3lity/k3che 吸收，省得各仓自行摸索。
- **触发场景**: 用户要求逐条评估、落盘、再按批执行；并质疑 v1 扫描不全（确属实，v1 漏了 thermo-nuclear-review / interrogate / 多数 principle-* / 两个 TS .mdc / benny）。
- **纪律**（`rules/09`）: 洁净室（只搬模式/状态机/判据，零粘代码）、许可分级、只路由进既有 4 peer、1 行署名。
- **覆盖声明**: 首方组件 **111** 个文件（`SKILL.md`/agents/rules `.mdc`/hooks/automations），分布于 14 个首方插件；本 ledger 逐个处置。`third_party/` 19 个厂商连接器整体排除。`schemas/`+`scripts/`+`.cursor-plugin/` = 市场基建，排除。首方 = **MIT**。
- 图例：✅已吸收 / 🎯本轮候选 / 📥backlog / ❌拒绝(附因)。

## k3dit（审计透镜）

| 来源 | 吸收什么 | 状态 | rank |
|---|---|---|---|
| pr-review-canvas | 风险排序、Breaking/Race/Perf/Subtle callout、稠密逻辑 trace、缺输入即问 | ✅ ADR-0002 | — |
| cli-for-agent | CLI 对 agent 友好性 Pass3 子检查 | ✅ ADR-0002 | — |
| thermos `code-quality-review` | 可维护性透镜 + Approval Bar + 输出优先级 | ✅ ADR-0003 | — |
| **thermos `thermo-nuclear-review`** | 分支 diff 的**安全 + 正确性**深审（bugs/breaking/security）——补强 Pass1/Pass2，非 code-quality 那半 | 🎯 | P1 |
| **pstack `interrogate`** | 对抗式自审："challenge this / 找盲点"的**提问清单**（多模型 fan-out 那半不搬=编排） | 🎯 | P2 |
| **pstack `blast-radius`** | 审改动会打破 diff 之外的什么，**跑真代码证明那一条安全事实** | 🎯 | P1 |
| pstack `fix-root-causes` | 追症状到根因、reproduce first（喂 incidents） | 📥 | P2 |
| pstack `boundary-discipline` | 守卫集中在系统边界（CLI/网络/存储），不散落中部 | 📥 | P2 |
| pstack `foundational-thinking` / `model-the-domain` | 先定核心类型/数据结构与状态模型；分支多/跨文件重复形状→建模型 | 📥 | P2 |
| pstack `minimize-reader-load` | 数"问题到答案之间隔几层"+隐藏状态——与 ADR-0002 排序呼应 | 📥 | P2 |
| pstack `type-system-discipline` | 让非法状态不可表示（Pass3 契约） | 🎯 | P2 |
| pstack `exhaust-the-design-space` | 无先例的 UI/架构决策：先造 2–3 个候选再选（推理，非 arena 编排） | 📥 | P3 |
| pstack `migrate-callers-then-delete-legacy-apis` | 新 API 落地即迁调用方并删旧的，不留双路 | 📥 | P3 |
| pstack `outcome-oriented-execution` / `redesign-from-first-principles` | 迁移按目标架构收敛；把新需求当"第一天就如此设计"重构 | 📥 | P3 |
| pstack `subtract-before-you-add` / `laziness-protocol` | 先删死重/冗余再加；偏"删整类复杂度"（与 code-judo 重叠） | 📥 | P3 |
| pstack `encode-lessons-in-structure` | 重复的 instruction/correction → 沉进结构/规则（也触 k3che） | 📥 | P3 |
| pstack `show-me-your-work` | 决策 TSV 日志(what/why/evidence/result)——审计留痕格式（也喂 k3dge 证据链） | 🎯 | P2 |
| pstack `make-operations-idempotent` | 命令/生命周期步幂等抗重放（并入 ADR-0002 CLI 检查） | 📥 | P2 |
| pstack `sequence-verifiable-units` | 多步活拆成各自可验证的小单元（也与 seal/align 呼应） | 📥 | P3 |
| pstack `build-the-lever` / `experience-first` | 评审者复用的"杠杆"工具 / 产品体验取舍——偏元/产品 | 📥/❌ | P3 / 产品向暂不 |
| pstack `never-block-on-the-human` | 可逆事先斩后奏 | ❌ 与"先问人/不替人决定"冲突，记非目标 | — |

## k3lity（L2 质量：确定性可数 + 评分）

| 来源 | 吸收什么 | 状态 | rank |
|---|---|---|---|
| thermos（可数半） | 文件行数超阈 → `结构` | ✅ c3860a3 | — |
| **agent-compatibility** | 四维评分 startup/validation/docs-reliability + `det×0.7+workflow×0.3`（现 `_score` 只 4 个存在性判据，太浅） | 🎯 | P1 |
| **cursor-team-kit `control-cli`/`control-ui`** | 无外部服务驱动/检查/剖析 CLI(TUI)+UI(CDP)——填 k3lity `probe`（现是 stub） | 🎯 | P1 |
| **cursor-team-kit `no-inline-imports.mdc` / `typescript-exhaustive-switch.mdc`** | 具体 TS 规则：禁内联 import；判别式 union/enum 的 switch 必 `never` 兜底 → 可 tsc/eslint 检 | 🎯 | P2 |
| cursor-team-kit `deslop` / pstack `unslop` | 去 AI slop（判据现很浅） | 🎯 | P2 |
| cursor-team-kit `verify-this` | 可证伪重述 + baseline/treatment + VERIFIED/NOT/INCONCLUSIVE（`verify` 已同形，对齐措辞） | 📥 | P3 |
| pstack `create/maintain-verification-skill` | 像用户那样驱动 app 验证 + feature map 保真 | 📥 | P3 |

## k3che（记忆/上下文）

| 来源 | 吸收什么 | 状态 | rank |
|---|---|---|---|
| continual-learning `agents-memory-updater` | 对话高信号增量→AGENTS.md + 增量 transcript 索引（只 bullet） | 🎯 | P2 |
| pstack `recall` | 从对话/活状态/共享记录重建工作上下文 | 📥 | P2 |
| pstack `reflect` | 并行审当前对话→learning 落到具体 skill 编辑（写侧需人审） | 📥 | P3 |
| cursor-team-kit `workflow-from-chats` | 从对话提炼**持久偏好**→rules/skills | 📥 | P3 |
| pstack `guard-the-context-window` | 上下文将满的处置；但"route bulk to subagents"=编排 → 只取其"防大输出/重复读"那半 | 📥 | P3 |

## k3dge（一致性/结构/生命周期）

| 来源 | 吸收什么 | 状态 | rank |
|---|---|---|---|
| pstack `technical-writing` | Diátaxis + Google 句法 + STE + Global English（已 Diátaxis/ADR-0002，补风格细则） | 🎯 | P2 |
| pstack `show-me-your-work` | 决策留痕→ 封板 closure / reviews 证据格式（ADR-0012） | 📥 | P3 |
| create-plugin `plugin-quality-gates.mdc` / `review-plugin-submission` | "声明路径须对上真实文件/元数据一致"——k3dge 目录+manifest 校验已覆盖 | ❌ 已实现，无需搬 | — |
| pstack `prove-it-works` | 宣布完成前验真产物——seal 的 `audit_closed` 已体现 | ❌ 已覆盖 | — |

## 一律排除（附因，防再翻）
- **编排/自迭代**: `orchestrate`、`ralph-loop`(含 hooks)、pstack `swarm`/`arena`、thermos 顶层 orchestrator/`*-subagent`、`interrogate` 的多模型 fan-out、`guard-context-window` 的 subagent 路由部分 → 各 peer **不编排**（sidecar ADR-0006）。
- **CI/git/PR/issue 运维**: cursor-team-kit `check-compiler-errors`/`fix-ci`/`loop-on-ci`/`run-smoke-tests`/`new-branch-and-pr`/`fix-merge-conflicts`/`get-pr-comments`/`ci-watcher`/`weekly-review`/`what-did-i-get-done`；pstack `benny`（`setup-benny`/`triage-issue-reports`/`reproduce-and-fix-issues`，Slack+tracker+PR）→ 流水线/工单工作流，非一致/审计/质量/记忆四域（其"跑一次拿证据"内核已被 k3lity verify/probe 覆盖）。
- **Cursor 宿主/市场专有**: `cursor-sdk`、`docs-canvas`/`pr-review-canvas` 的 Canvas/HTML **渲染壳**（只取组织模式）、`create-plugin` 脚手架、`schemas/`、`scripts/validate-plugins.mjs`、`.cursor-plugin/marketplace.json`。
- **`third_party/` 全 19**（github/gmail/salesforce/playwright/zoom…）：许可各异、纯连接器，不评估。
- **人物/UX/无关**: pstack `bro`/`poteto-mode`/`automate-me`/`no-comments`/`setup-pstack`、`teaching/*`（学习路径）、`pstack `comment-sicko``（persona）。
- **商标资产**: 各 `assets/*.png`、`.json` manifest → de-brand 禁入库。

## 执行计划（每 peer 一批：目标仓 改 + 1 ADR(Draft) + 测试，不自批 Accepted）
- **P1**: k3lity `score`(←agent-compat) · k3lity `probe`(←control-cli/ui) · k3dit Pass1/2(←thermo-nuclear-review) · k3dit Pass4(←blast-radius)
- **P2**: k3lity TS .mdc 规则 + deslop 扩 · k3dit 其余 principle-* + interrogate 自审 + show-me-your-work 留痕 · k3che continual-learning/recall · k3dge technical-writing
- **P3**: 上面 📥 里的判断类细则（多与已吸重叠，按需再收）
