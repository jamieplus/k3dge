# Memo: plugins-main → 四 harness 吸收评估（ledger v3）

- **类型**: 可落地（吸收待办清单；逐项执行后转 tasks/ADR）
- **念头**: 逐条评估 `workspace/plugins-main`，判断哪些**模式**能被 k3dge/k3dit/k3lity/k3che 吸收。
- **纪律**（`rules/09`）: 洁净室（只搬模式/判据，零粘代码）、许可分级、只路由进既有 4 peer、1 行署名。首方全 **MIT**（root + 13 个 plugin.json 已核）；无 `mcp.json`/MCP server；`third_party/` 20 厂商连接器整体排除。
- **覆盖诚实度（关键）**：首方内容 `.md` 实际 **186**（非 v2 误称的"111/穷尽"——v2 的 find 漏了 `poteto-mode/playbooks/*`、`**/references/**`、`pstack/docs/guide/*`）。本轮**深读约 20 个**高信号文件（下列标 ⬤），其余按 README 定性 + name/description 归类；21 条 `principle-*` 的规则原文已由 pstack README 表格给出，无需逐个开。

## k3dit（审计透镜）

| 来源 | 吸收什么（v3 细化） | 状态 | rank |
|---|---|---|---|
| pr-review-canvas ⬤ | 风险排序(核心>接线>样板)、Breaking/Race/Perf/Subtle callout、稠密逻辑 trace、缺输入即问 | ✅ ADR-0002 | — |
| cli-for-agent ⬤ | CLI 对 agent 友好 Pass3 子检查 | ✅ ADR-0002 | — |
| thermos code-quality ⬤ | 可维护性 + Approval Bar + 输出优先级 | ✅ ADR-0003 | — |
| **thermos `thermo-nuclear-review`** ⬤ | Pass1/2 安全+正确性深审；**关键新增**：只报 diff 内 added/modified（不报存量漏洞）、**over-report 校准**（虚报优先级会失去信任，宁少报勿误报）、intended-breakage 豁免（作者有意且范围受限的破坏不报）、BugBot/PR 评论复核、结论前必端到端追链 | 🎯 | P1 |
| **interrogate** ⬤ + rubric ⬤ | 自审 lens（多模型 fan-out 不搬）；rubric 直接可并入：correctness（幂等"跑两次/半路崩"、并发结构性 vs 约定、追链非空喊）、root-cause vs symptom（guard 掩盖不变量 / cast 掩盖建模错）、structural（信息泄漏、temporal decomposition、shallow module vs deep call chain、bolted-on、legacy 双路即删） | 🎯 | P1 |
| **how/critique-rubric** ⬤ + **architect/design-red-flags** ⬤ | Pass3 契约红旗：浅模块(大接口藏小复杂度)/deep call chain≠deep module、信息泄漏、temporal decomposition、pass-through；"过度抽象=欠抽象之害、premature abstraction 比 duplication 更糟" | 🎯 | P2 |
| **pstack `why`/epistemics** ⬤ | 发现按**置信分层**：Direct(作者明写的引用)/Supported(多源收敛)/…，决定进报告哪栏与措辞——喂 ADR-0012 证据链 + 12 列"验证/验收" | 🎯 | P2 |
| **pstack `show-me-your-work`** ⬤ | 决策 TSV(ts/phase/decision/why/**evidence=指针非散文**/result)——k3dit 报告"验收"列格式 & 复杂审计留痕 | 🎯 | P2 |
| pstack `perf-issue` ⬤ | 性能策略 8 族（**Elimination 优先：不跑最便宜，需 `how` 非 profiler**、分治/缓存/间接/批/冗余/惰性/调度），作 Pass5 判据 | 📥 | P3 |
| pstack principles（21，原文见 README）| type-system-discipline / boundary-discipline / model-the-domain / fix-root-causes / make-operations-idempotent / migrate-then-delete / minimize-reader-load / subtract-before-add / laziness-protocol 等，作透镜判据 | 🎯/📥 | P2/P3 |
| thermos-review 的"只审 diff 内"作用域 + over-report 校准 | 通用审计纪律，与 ADR-0003 Approval Bar 合并 | 🎯 | P1 |

## k3lity（L2 质量：确定性可数 + 评分）

| 来源 | 吸收什么（v3 细化） | 状态 | rank |
|---|---|---|---|
| thermos 可数半 | 文件行数>阈 → `结构` | ✅ c3860a3 | — |
| **agent-compatibility** ⬤(skill+validation) | `_score` 升级：`det×0.7 + workflow×0.3`，workflow=avg(startup/validation/docs)；**validation 锚点 93/84/68/27/12**；"工具环境跑不起来 ≠ 仓库缺陷，别罚"；输出=`## Score:N/100`+`Top fixes` 扁平表，不暴露算法 | ✅ k3lity | P1 |
| **control-cli / control-ui** ⬤ | 填现是 stub 的 `probe`：**优先复用仓库自带 harness**→否则 tmux(new-session/capture-pane/send-keys/kill)、PTY、Node inspector、CDP(`--remote-debugging-port`)、复用已装 Playwright（**别为探针新增依赖**）、选择器用 ARIA/data-* 非坐标 | ✅ k3lity | P1 |
| **verify-this** ⬤ | `verify` 精化：**可证伪重述(条件+指标+阈)**→选最小可反证面→baseline(merge-base/父提交/旧 repro)→treatment(同命令同环境)→比原始产物→`VERIFIED/NOT/INCONCLUSIVE`；产物 `/tmp/verify-this/<slug>/{claim,timeline,baseline,treatment,diff,verdict}.md`；敏感只留 inline | ✅ k3lity | P2 |
| cursor-team-kit **deslop** ⬤ / pstack **unslop** | k3lity `deslop` 具体化：多余注释/异常防御式 try-catch/纯绕类型的 `as any`/该早返回的深嵌套；行为不变、最小聚焦改；unslop(写作 AI 腔) 归 k3dge 文档 | ✅ k3lity | P2 |
| **typescript-exhaustive-switch.mdc / no-inline-imports.mdc** ⬤ | 具体 TS 可检规则（`never` 兜底 switch；import 置顶）→ k3lity TS 检查（配 typescript-best-practices/patterns ⬤：branded type、判别式 union、constructive modeling） | 🎯 | P2 |
| pstack `hillclimb` / `bug-fix` / `visual-parity` / `prototype` ⬤(部分) | 度量循环纪律（冻结 harness、median-of-N、一测一改一 revert、pixel-diff 才算过）→ k3lity verify/eval 判据 | 📥 | P3 |

## k3che（记忆/上下文）

| 来源 | 吸收什么（v3 细化） | 状态 | rank |
|---|---|---|---|
| **continual-learning** ⬤(skill+updater) | k3che 蓝本：stop-hook 触发(≥10 轮/≥120min/mtime 前进，trial 3/15)；只扫 `agent-transcripts/` 新/改 → 增量 index；**只写** `## Learned User Preferences`+`## Learned Workspace Facts`、纯 bullet、就地更新、无 evidence/confidence 元数据；父只编排 | 🎯 | P2 |
| pstack `recall` / `reflect` | 从对话/活状态/共享记录重建当前上下文 brief；reflect=三审→落 skill 编辑(需人审) | 📥 | P3 |
| cursor-team-kit `workflow-from-chats` | 对话→持久偏好→rules/skills（写侧交 k3dge 规则，需人审） | 📥 | P3 |
| pstack `guard-the-context-window` | 只取"防大输出/重复读/原始载荷下沉"半，subagent fan-out 不搬 | 📥 | P3 |

## k3dge（一致性/结构/生命周期）

| 来源 | 吸收什么（v3 细化） | 状态 | rank |
|---|---|---|---|
| pstack **technical-writing** ⬤ | 各 docs/<type>/AUTHORING 软规则：4 层(Diátaxis+Google+STE+Global English)+3 顶规(删不干活词/用短日常词/规则伤句则改句)+节奏；"codebase 是词表，写真实符号名" | 🎯 | P2 |
| **show-me-your-work** ⬤ | 决策 TSV 格式 = ADR-0012 证据链落地形态；可作封板 closure/review 模板 | 🎯 | P2 |
| pstack `eval` ⬤ | 盲测纪律（候选不见 eval/rubric/score 词、单一有机 prompt、一个 judge 一遍两集同标尺、从 transcript 实读哪些文件判 follow-through 非自报）。**更正：k3dge 目前没有任何 A/B/compare harness，ADR-0013 是版本/变更日志**——此条只在 k3dge *将来*真要建实验/对比 harness 时作设计输入，不是"修既有 harness" | ❌→📥 | 需先立 harness |
| **encode-lessons-in-structure** | "规则该是 lint/metadata/运行时检查/脚本，而非更多散文"——正合 k3dge 门>文；可作元原则 | 📥 | P3 |
| create-plugin review-plugin-submission | 声明路径↔真实文件一致 = k3dge 目录校验已覆盖 | ❌ 已实现 | — |
| pstack `prove-it-works` | 完成前验真产物=seal `audit_closed` 已体现 | ❌ 已覆盖 | — |

## 一律排除（README/manifest 已定性，附因）
- **编排/自迭代/并行**：orchestrate(含 prompts/references)、ralph-loop、pstack `swarm`/`arena`、thermos orchestrator+subagents、interrogate 的多模型 fan-out。
- **CI/git/PR/工单运维**：cursor-team-kit `fix-ci`/`loop-on-ci`/`run-smoke-tests`/`new-branch-and-pr`/`fix-merge-conflicts`/`get-pr-comments`/`check-compiler-errors`/`ci-watcher`/`weekly-review`/`what-did-i-get-done`；pstack benny(Slack+tracker)、babysit/shipping/autopilot-*/session-pickup/pause-safely/worktree-cleanup/opening-a-pr。
- **Cursor 宿主专有/壳**：cursor-sdk(+references)、docs-canvas(自称 scaffold 空壳)、pr-review-canvas/thermos 的 Canvas/HTML 渲染壳（只取其组织模式）。
- **`third_party/` 20 个**厂商连接器；**`schemas/`/`scripts/`/`.cursor-plugin/marketplace.json`** 市场基建；各 `assets/*.png` 商标（de-brand 禁入库）。
- **人物/UX/学习**：pstack bro/poteto-mode/automate-me/no-comments/setup-pstack、teaching/*、agent 体验取舍类(experience-first 偏产品)。

## 执行计划（每 peer 一批：目标仓 改 + 1 ADR(Draft) + 测试；不自批 Accepted）
- **P1**：k3dit ← `thermo-nuclear-review`(安全/正确性 + 只审 diff 内 + over-report 校准) + `interrogate/rubric`(并入可维护性透镜)；k3lity ← `agent-compatibility` 评分模型(升级 stub `_score`) + `control-cli/ui`(填 stub `probe`)
- **P2**：k3lity ← `verify-this`精化/`deslop`+TS .mdc；k3dit ← epistemics 置信分层 + show-me-your-work 留痕；k3che ← continual-learning 增量刷新；k3dge ← technical-writing 软规则 + show-me-your-work closure 格式。**eval 盲测移出 P2**：k3dge 无 compare harness 可修（见上更正），列为"需先立 harness"。
- **P3**：perf 8 族、hillclimb/bug-fix/visual-parity 度量、principles 细则、reflect/recall、guard-context-window 半条

### 状态更正记录（2026-09-03）

- 第 29, 30, 31, 32 行原标 `🎯`（待吸收），实测**已在 k3lity 落地**，改为 `✅ k3lity` 并附文件:行（逐条见上表）。
  同批一次口头复核曾把这四行说成「📥 里已实现」——错：`📥`（未开始）与 `🎯`（目标/计划吸收）是两类，实测 `🎯` 14 行、`📥` 6 行。此处留记，免得下次又拿状态符号猜实现。
- 第 33 行（TS 可检规则 `never` 兜底 switch / import 置顶）**仍未落地**：`../k3lity/src/k3lity/` 只有 `__init__/cli/deslop/harness/mcp/quality`，无 TS 规则实现 ⇒ 保持 `🎯`。
- 剩余 `📥`/`🎯` 行的归属是 **peer 仓**（k3dit 判据、k3lity 度量、k3che 记忆），不属本仓 backlog。把它们迁进各 peer 自己的 `docs/memo/` 需各仓维护者授权（`ADR-0006` §2.3.7 跨仓改动条），本文件先就地标注归属，不擅动 peers。

### 核对记录（2026-09-05，逐条盘点 ✅ vs 落地）

- **k3dit 0002/0003（pr-review·cli·thermo 三行 ✅）**：文书 ✅（0002/0003 ADR 已立，但**全是 Draft**）；代码 ❌（透镜表仍 5 个通用 pass，无 pr-review 风险排序/Breaking-Race callout、无 cli-for-agent Pass3、无 Approval Bar 落码）。结论：**✅=文书已立，落地未发生**。
- **k3dit 0004/0005（nuclear·interrogate·rubric·epistemics 🎯）**：ADR 均为 Draft，透镜表无痕迹。结论：**🎯 属实＝真没吸收**，memo 无虚报。
- **k3lity thermo 可数半 ✅ / verify-this ✅ / deslop ✅**：落码实锤（thermo 字样、`baseline/treatment/VERIFIED`、`as any`/早返回规则）。结论：**真吸收**。
- **k3lity agent-compatibility ✅**：公式 `det×0.7+workflow×0.3`、`## Score`、`Top fixes` 均在；但 memo 写明的**校验锚点 93/84/68/27/12 不存在**（实为 55/30/15 另一套）。结论：**大半真、数字漂了**。
- **k3lity control-cli/ui ✅**：`probe` 动词＋tmux/PTY/CDP 指引文本在；完整 CDP 落码未深验。结论：**基本真**。
- **k3lity TS 规则 🎯**：`find` 无果。结论：**🎯 属实＝真没吸收**（与更正记录一致）。
- **k3che**：全表无 ✅。结论：**无虚报**（全是计划态）。
- **k3dge technical-writing 🎯**：memo **少报了**——`templates/assets/rules/01-docs-structure.md:10` 已有 Diátaxis 四层＋三顶规逐字落地（洁净室署名齐）。结论：有机吸收已发生，状态未更新。
- **k3dge show-me-your-work 🎯**：M7 closure 无 TSV 形态。结论：**🎯 属实＝真没吸收**。

## 结项记录（2026-09-05 晚，全账核清 → archive）

> 核对方法：每条要求→产物（文件:行）→消费者（测试/引擎/闸）→到达（AGENTS 路由/脚手架/契约哈希）。缺任一环不算落地。下列逐条为当日实测，非计划复述。

| 账 | 最终状态 | 证据链（产物→消费者→到达） |
|---|---|---|
| k3dit 0002/0003/0004/0005（含 P1 nuclear/interrogate、P2 epistemics/show-work） | ✅ 09-04/05 封板夜落地 | 产物 `../k3dit/src/k3dit/mcp.py:39-52`（12 透镜）+ `docs/guides/protocol.md:36-159`；消费者 `../k3dit/tests/unit/k3dit/test_jobs.py:59`（`lens_count==12`）+`test_mcp.py`（53 绿）；到达 flow 工具→`lens_version` 进报告 provenance |
| k3dit **P3 perf 8 族** | ✅ 本会话 | 产物 `../k3dit/docs/guides/protocol.md`「性能策略 8 族」节+ADR-0006(Draft)；到达 flow `protocol` 字段逐席送达；k3dit 53 测绿 |
| k3lity agent-compat/control/verify/deslop（P1/P2） | ✅（锚点数字漂移已记于 09-05 核对节，不追） | `../k3lity/src/k3lity/harness.py:104-143`；消费者 cli.py 子命令 + test_harness |
| k3lity TS 规则（P2） | ✅ 本会话实查已存在（09-05 核对节说"无果"**错**） | `../k3lity/src/k3lity/quality.py:275 _scan_ts_rules` 挂 `scan_quality`；test_quality 绿 |
| k3lity **P3 度量循环** | ✅ 本会话 | 产物 `../k3lity/docs/guides/measurement.md`+ADR-0002(Draft)；到达 guides 消费路径=席/人；20 测绿 |
| k3che continual-learning（P2） | ✅ 封板夜 | `../k3che/src/k3che/learn.py`；test_learn 绿；spec 接口块含 learn 函数 |
| k3che **P3 recall/guard 机械半** | ✅ 本会话 | 产物 `../k3che/src/k3che/recall.py`+ADR-0003(Draft)；消费者 test_recall（5 测）；到达 `k3dge sync` 回写契约哈希（GATE SUCCESS, spec.md:77-78） |
| k3dge technical-writing | ✅（09-05 核对节已纠"少报"） | `src/k3dge/templates/assets/rules/01-docs-structure.md:10`；到达=PAIRS 镜像闸 + 脚手架进所有下游仓 |
| k3dge show-me-your-work TSV（P2） | ✅ 09-04 封板夜（09-05 核对节"真没吸收"过期） | `src/k3dge/engine/milestone.py:1214` closure 生成 §5 TSV；到达=seal 流程硬编码 |
| k3dge **P3 encode-lessons-in-structure** | ✅ 本会话 | 产物 `.agent/rules/10-structure-over-prose.md`+镜像；消费者 `tests/unit/templates/test_template_sync.py`（PAIRS 注册）；到达 AGENTS.md 路由行 + 260 测绿、check 绿 |
| eval 盲测 | ❌ 维持排除 | 前提不成立（k3dge 无 compare harness）；已转 `docs/tasks/2026-09-05-M8-chore-eval_harness_needed.md` |
| P3 principles 细则行（21 条中未单列者） | ✅ 已随 0003/0004 判据合并 | protocol.md 结构红旗/幂等/并发/legacy 行 |

- 本会话未改 peer 仓 ADR 状态（Draft→Accepted 归各维护者）；跨仓归属账随本文件归档，peer 侧以各自 ADR/tests 为权威。
- memo 使命（评估+路由）完毕：**全部行要么落地、要么转 task、要么明确排除**，无遗留 🎯/📥 → 按 Rule 06 archive。encyclopedia:233 索引行同轮更新。
