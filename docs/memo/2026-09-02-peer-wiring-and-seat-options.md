# Memo: peer 接线与审计席位的选项账（研究用，不作决策）

- **类型**: 暂无法落地（等维护者研究后再定）
- **念头**: 出向链路已通，整套 harness 剩下的唯一未决是"审计席位到底要多硬"——以及为什么我之前会把它摊成 30 个选项
- **触发场景**: 2026-09-02 会话，维护者要求"先记下方案和选项，我要研究一下"
- **Date**: 2026-09-02

> **本文件不作决策。** §1 是已定项（只给结论与落点，防被重新发明）；§2 是待研究项（真未决的只有 1 题 + 2 个搁置）；§3 是废案（每条写"当初为何被想到 / 为何否"，防再提）；§4 是可复跑现状快照。
> 元问题也记在这：一次会话产出 10 组约 30 个带字母的选项，本身就是失败模式——把每个不确定点摊成菜单，而不是先收敛再问，等于把对齐成本转嫁给维护者。§2.4 有对策条目。

## 1. 已定（只留指针，不再复述结论）

这些结论的**权威正文在 ADR 与各仓代码/测试里**；本节只当索引用，避免与 `ADR-0006` / `ADR-0023` 形成双源。要看理由去落点，不要在这里改。

| # | 主题 | 唯一权威落点 |
| --- | --- | --- |
| 1 | peers 的 server 在 `mcp` 2.x 假死 → 双路径 import 吸收 | `../k3dit`、`../k3lity` 的 `src/*/mcp.py` + 各仓 `docs/tasks/2026-09-02-fix-mcp2_server_dead.md`；立案原文 `../k3che/docs/reviews/2026-09-01-peer-bringup.md:15` |
| 2 | SDK 无上界会复发 | 四份 `pyproject.toml` 的 `mcp>=1.0,<3` |
| 3 | k3dge 当 MCP 客户端 / `check` 纯静态 | `ADR-0006` §2.3.2–§2.3.4；实现 `src/k3dge/engine/pipeline_runner.py`；诊断 `k3dge mcp probe` |
| 4 | endpoint 与流程分居 | `ADR-0006` §2.3.3（`.mcp.json` ↔ `pipeline.toml`） |
| 5 | 传输身份不借道 | `ADR-0006` §2.2；回归测试 `tests/unit/engine/test_pipeline_runner.py::PeerIsolation` |
| 6 | 降级不设开关、必须不可静默 | `ADR-0006` §2.4 |
| 7 | 调动作不调步骤 | `ADR-0006` §2.3.8；入口 `../k3dit/src/k3dit/mcp.py:155`；留痕 `../k3dit/docs/tasks/2026-09-02-feat-audit_flow_tool.md` |
| 8 | k3che 语料排除结构件 | `../k3che/src/k3che/index.py:13` + `../k3che/docs/tasks/2026-09-02-fix-authoring_in_corpus.md` |
| 9 | ADR 生命周期（含就地修订授权与 `Note:` 痕迹） | `docs/adr/AUTHORING.md`（+ 模板副本，PAIRS 逐字节同构） |
| 10 | 编号历史表已删、不复用号靠句子守 | `ADR-0023` §2.3 + `docs/adr/README.md` 正文规则行 |
| 11 | `status`/`task list` 两处假绿缺陷与自查 | `docs/incidents/INC-20260902-CON-exit-and-trail-blindspot.md` |
| 12 | k3che 接通框架内第一消费者＋命中率落盘（此前 per-call spawn 下 total 恒 ≤1） | `../k3che/docs/tasks/2026-09-03-feat-hits_persist_and_first_consumer.md`；消费者 `milestone._attach_k3che_hints`（service 语义：失败=无提示，绝不=无审计）；§7 预筛照旧不依赖 k3che |
| 13 | k3che 第二消费者（status 观测行，观测不判定）＋索引 RLock（反证：去锁 3/3 复崩） | `../k3che/docs/tasks/2026-09-03-fix-index_locks.md`；`cli/status.cache_observability`＋6 例测试 |
| 14 | k3che 第三消费者＝第一个"真被需要"的：`task create` 相似检查（语料含 archive，只提示不裁决） | `docs/tasks/2026-09-03-M7-feat-task_dup_check_via_cache.md`；首跑即翻出 archive 同域缺陷簇，并暴露 ADR 标题提取被 front-matter 注释骗的副缺陷（待授权） |
| 15 | **audit 真链首跑通**（submit→claim→席位实检→complete→collect→落盘回流；席位=手工 CLI，零 mock） | `../k3dit/docs/tasks/2026-09-04-feat-audit_job_protocol.md`；下一步＝生产状态机换轨（`milestone audit`→两态） |
| 16 | **findings 交换介质定稿为钉语法 v1（棘轮：一单一快照，单内审↔修交替；报告=结项 join 渲染）**，k3dge 半边已落 | 契约 §1.4/§8；`engine/markers.py`＋`k3dge markers`＋`[NEXT]` 口径扩为 open 三态；k3dit 半边（发号/账本正文/合成报告）等其仓授权。首跑自曝：未锚定行首时解析器最先"发现"的 2 处全是我仓文档示例——锚定规则由此而来 |
| 17 | k3dit 棘轮半边落账（发号/vanished 裁决/结构化正文/结项 join；rounds 模块 44 测全绿） | `../k3dit/docs/tasks/2026-09-04-feat-ratchet_rounds.md`；k3dge 轨 A（milestone audit 换轨 rounds）为下一步 |

### 2.1 审计席位的落地强度 —— **已按分治定案（2026-09-03）**

> 结论：席位强度**不是 k3dge 的决策**。k3dge 只做编排与验壳（信封/基线/12 列/计数），
> 「几席、要不要 clean session、要不要人复核」整体移交 audit harness（k3dit）内部，
> 由它在自己仓里实现并对报告 `审计人`/`透镜来源` 负责。k3dge 侧的防线＝`WARN[DOWNGRADE]`
> ＋人 `attest` 才放行。契约＝`docs/protocols/peer_contract.md`；骨架（submit/collect 两态 +
> `engine/bundle.py` 送检包 + `tests/fixtures/dummy_peer.py`）已实现并全测
> （`engine/audit_flow.py`；整链用例 `tests/unit/engine/test_audit_flow.py`）。
> 下面 S/S-lite/(α)(β)(γ) 保留作历史记录——它们都把席位留在了 k3dge 侧，已被否。



先拆"外部"这个词——它可执行的只有三层，第三层机器拿不到：

| 层 | 含义 | 能不能机验 | 现状 |
| --- | --- | --- | --- |
| **规则外部** | 透镜文本、12 列表头、报告校验器不在工作 agent 手里 | 能（进程/仓不同） | ✅ 已到手（1–3 号已定项） |
| **上下文外部** | 判断者没看过改代码那轮的推理与承诺 | **能**（新会话 + 可核 token） | ⬜ 未做，就是本题 |
| **利益外部** | 判断者不因"活干完了"而受益 | **不能**（换底座也只是减弱） | ⬜ 只能靠人 attest 兜 |

本轮就有一个**活标本**（支持"至少要做上下文外部 + 事后核查"，也说明规则挡不住善意自欺）：我给 `k3dge status` 修 NameError 后直接 `task done`，而该 task 验收第二条（JSON/MCP 出口带 `next`）**当时并未实现** —— 是 `k3dge task done` 之后我自己复核才发现，随后补做（`docs/tasks/2026-09-02-M7-fix-status_nameerror_next.done.md` 的回填段记了全过程）。要点：
- 没有外部席位时，这类"标早了"只能靠**同一个席位事后自愿复查**，而这正是旧 memo 判死的"认知级软隔离"；
- 可机验的替代（不依赖自觉）：`task done` 时把该 task 的验收条目原文与当轮 diff/测试清单一起落到报告，让**另一个席位**逐条打勾 —— 属 §五.2/§五.5 的实现细节，待你定粒度。

**先读旧账（重要）**：`docs/memo/2026-08-27-h8m2k-a1-harness-hard-isolation.md` 已论证过一轮「审计必须由 harness 在**环境与状态机层面**强制隔离，不能靠 agent 在同一上下文内自我约束」，并给了 4 支柱。本节不是新想法，是那张表的落地缺口——而且它和昨天刚立的 `ADR-0006` §2.3.8 **互相打架**，这是留给维护者的头号议题：

| 旧支柱 | 它要求什么 | 与 §2.3.8 的冲突 |
| --- | --- | --- |
| Zero-Context Fork | 写完捕 diff → **终结 session** → 开 clean session，只注入「diff + **单轮** focus」 | 隔离粒度是**一轮一席**。§2.3.8 说"调用方不得传轮次"。两者不能同时满足：一席跑 5 轮 ⇒ 5 轮之间的 CoT 惯性回来了（旧 memo 正是要治它）；一席一轮 ⇒ 调用方必须知道有几轮（违 §2.3.8） |
| Capability Gating | auditor 在**能力层被剥夺写权限**（只读） | 我下面的 S 只有**事后核查**（git 快照越界即废）。事前剥夺更强，但取决于宿主能不能给"只读工具集"（`pi` 有 `--no-approve` / `--session-id`，未核到只读白名单） |
| 旧 memo 称「`k3dit_run_audit 1..5` 已 Gate SUCCESS」 | 当时由调用方逐轮取指令 | ① 那是在出向客户端存在之前，"跑通"其实是宿主 agent 逐轮自取；② 现已被 flow 入口取代 ⇒ **旧 memo 两句需加注**（我没擅自改旧账） |

调和这冲突的三条路（待研究子问题 5）：

- **(α) k3dit 自己派席**：flow 工具内部为每轮起 clean session。彻底解决外溢，但 k3dit 要 spawn 外部 agent + 写文件 ⇒ 直接推翻它「零副作用、只出指令」的架构承诺（也逼它依赖宿主 CLI）。
- **(β) 遍历 bundle，不发明轮次（我倾向）**：k3dge 拿 `lens_count` 后**对返回项逐个派席**，传给席位的是那一项的 `lens/focus/instruction` 文本，不传也不存 `pass_number` 语义。§2.3.8 由此精确化为：*「k3dge 可遍历 peer 返回的项，不得自行发明、记忆或依赖步骤编号」*——轮数仍由 k3dit 决定，隔离粒度仍是"一轮一席"。代价：一次审计 = N 次 agent 冷跑（5×分钟级）。
- **(γ) 单席跑完整 bundle**：最省（=下面 S 的原写法），但明确放弃"轮间隔离"，等于只拿到旧 memo 的一半。

**候选 S（派席）**：produce 阶段新增一档，插在 `mcp` 与 `manual` 之间。粒度按 (β) 或 (γ) 二选一。

```
1  run_action("k3dit.actions.audit")            → k3dit 回 lens bundle + scaffold（已可用）
2  k3dge 生成 seat_token(uuid) → logs/k3dge.log + audit_checklist（常量 CHECK_LIST_PATH=
     .agent/audit_checklist.json；本轮未跑 audit，文件当前不存在，属派席时要写的目标）
3  spawn: pi -p --no-approve --session-id <seat_token> [--model <别的底座>]
     prompt = bundle 的 5 轮指令 + git diff <base>..HEAD + scaffold
              约束：只准写 report_path 一个文件；每条发现带可复跑命令；
                   `审计人` 必须回显 k3dit+fresh-seat(<seat_token>)
4  四项确定性机验：a) 报告存在且 12 列合法  b) `审计人` 内 token == 本次 spawn
                  c) spawn 前后 git 快照 diff 只允许落在 docs/reviews/**（动了 src ⇒ 违规）
                  d) `## 回填` 齐（已有闸）
5  任一不满足 → WARN[DOWNGRADE]，不得写"审过了"
```

缺口（对齐旧支柱表）：本流程只做**事后**越界核查，未实现 Capability Gating 的**事前**只读剥夺；宿主是否支持待核（子问题 5 附项）。代价与失败面：一次审计多一次 agent 冷跑（分钟级 + token）；`pi`/`opencode` 不在场或无 auth ⇒ 该档 fail，链继续降级（不会假装审过）；需新增 `provider = "agent"` 档位（改 `_VALID_PROVIDERS` + schema + 文档 + ADR）与 `k3dge milestone seal --attest "<原话>"`。
本机前提已核实：`pi --print / --session-id / --no-approve / --model` 存在（`pi --help`），`opencode` 在 PATH。

**候选 S-lite**：不 spawn，只做 §S 第 4 步的 b/c/d 三项机验 + `--attest`。
效果边界要写清：它挡得住"我悄悄自审"，**挡不住"我认真自审"**。

**候选 不做**：保持今天——链能真调透镜，但报告仍由干活席位执笔，`seal` 前靠人看高亮。

四个可单独回答的子问题：

1. 同一维护者授权链下、底座模型同源的子会话，算不算"上下文外部"够了？还是要求 `--model` 跨供应商？
2. seat_token 由谁校验：k3dge（会碰"不产内容"边界？）还是 k3dit（它现在只出形式、不判内容，加席位校验=扩职责）？
3. `writable` 白名单默认值：只 `docs/reviews/**`，还是含被审对象的只读权限？子会话有没有 `git` 读权限的必要边界？
4. attest 粒度：每次 `seal` 都要，还是每里程碑一次并写进 `## 收摊` 清单？
5. **席位粒度**：上面 (α)/(β)/(γ) 选哪条？选 (β) 就要同时改 `ADR-0006` §2.3.8 的措辞（「可遍历返回项，不得发明步骤编号」），并接受一次审计 = N 次冷跑的成本。

### 2.2 搁置 D5：`.mcp.json` 的 `command` 形状

现状：四处仍写裸 `"python"`（本机 PATH 无此名），k3dge 客户端"出声回退"到 `<workspace>/.venv/bin/python`。
风险：每个消费者各自回退 ⇒ 同一份配置在不同宿主下解释不同。
未做的原因：改它 = 动 `templates/scaffold.py` + `cli/main.py:_peer_mcp_entry()` + `docs/guides/mcp-bridge.md` 块 A/B，块 A/B 是"照抄不许改形状"的 public 文档形状，且下游 4 仓各自的 `.mcp.json` 要一起迁。

### 2.3 搁置 D7：k3che 的 cli 传输面

`ADR-0006` §2.3.5 已立不变量"peer 双传输（mcp + cli）"，但 k3che 无 `cli.py`、无 `k3che` 脚本，链只有 `mcp → skip` ⇒ 无 MCP 的宿主里 cache 能力完全不可达。
最小实现（`src/k3che/cli.py` **待建**，现在没有这个文件）：`search` / `stats`，委托既有 `k3che.cache`）+ `[project.scripts] k3che` + 两份 pipeline 插 `cli` 档。载体 `docs/tasks/2026-09-02-M7-feat-k3che_cli_transport.md`。

### 2.4 元问题：选项通胀的对策（要研究的是"闸"而不是"检讨"）

本轮产出 10 组 ≈30 个带字母选项，其中 3 组是假选项（见 §3）。可落地的对策候选：
- agent 侧：一题只交一个推荐 + 一个反选项，其余先收敛再问（写进 `.agent/rules/`? 属软规则，k3dit 判）
- 闸侧：`k3dge check` 对"同一 task 里出现 ≥N 个候选方案且无结论"能否报 WARN（属结构闸？语义闸？）
- 落点未定：这条本身待研究，先记在 memo，不进 ADR

## 3. 废案（防重新发明）

| 废案 | 当初为何被想到 | 为何否 |
| --- | --- | --- |
| M1（在 0006 末尾追加修正案）/ M2（新开 ADR-0023 收编） | 想守住 append-only | 被维护者新规则取代：未跑通的决策允许就地替换正文 + `Note:` 留痕，两套机制都不必启用 |
| S0（用现成 `cli` 档跑 `k3dge audit-seat`） | 零 schema 改动、最省事 | 违 `ADR-0006` §2.2：`k3dit` 的传输去执行 **k3dge 自己**的命令，正是刚删掉的冒名路径的镜像版本 |
| 审计路径三选一 (a)(b)(c) | 把两个正交轴排成一张单选表 | (b) 讲"谁执笔"、(c) 讲"从哪跑"；真组合只有 4 种，其中"外部席位 × milestone audit"= 现在的 S |
| `mcp>=2.1,<3`（抬下界） | k3che 那份 review 曾提到 2.1 才有 `MCPServer` | 双路径已同时覆盖 1.x/2.x；抬界只让 1.x 环境当场装不上，收益是少一条分支 |
| 让 peers 复用 k3dge 的 `is_doc_aux`（提公开符号） | 结构件名单三份副本想收敛成一份 | peers 会依赖 k3dge，与"地位对等、可被别的 harness 使用"相抵；改为本仓一份 + k3che 一份，漂移风险显式留档 |
| 把特权条款写进 `docs/adr/README.md` | 提高可见度、少人误删 | 特权像 sudo，投递点越少越不易被顺手用；README 只留默认路径与指针 |

## 4. 现状快照（2026-09-02 收摊时，可复跑）

```
$ k3dge mcp probe                 →  k3dit / k3lity / k3che ALIVE；k3dge DEAD（入向，已搁置，§2 无本题）
$ run_action("k3dit.actions.audit", arguments={target_scope:"milestone M7", milestone_id:"M7"})
    provider=mcp  lens_count=5  mode=code-audit  downgrades=0
    report_path=docs/reviews/2026-09-03-M7-milestone-m7.md（k3dit 的建议落点，盘上尚无此文件）   ← k3dit 给的**建议**落点，盘上还没有这个文件
$ run_action("k3lity.actions.quality") / ("k3che.search")   → provider=mcp，零降级
闸：k3dge 201 passed / check ✅；k3dit 33 / k3lity 17 / k3che 36 passed；PAIRS 全等
```

未提交（本轮所有改动都在工作树）：k3dge 约 55 项、k3dit（含他人在途 WIP，勿裹提）、k3lity 4 项、k3che 4 项。

## 5. 相关

- 本轮自查成账：`docs/incidents/INC-20260902-CON-exit-and-trail-blindspot.md`（四个现存破损 + 过度标记的现场证据；§2.1 的活标本即出自该报告）
- 决策正文：`docs/adr/0006-mcp-foreign-harness-injection.md`（`Status: Draft`，理由见其 `Note:`）
- 生命周期与 `Note:` 格式：`docs/adr/AUTHORING.md`
- 出向实现与剩余项：`docs/tasks/2026-09-02-M7-feat-peer_outbound_mcp_client.md`
- 接口契约：`docs/protocols/peer_contract.md`（信封/错误码/送检包/工件/时序）；设计纪律 `.agent/rules/08-design-discipline.md` ＋ `AGENTS.md` 不变量 5
- 入向搁置：`docs/tasks/2026-09-02-M7-fix-k3dge_mcp2_resource_strict.md`
- 人读面待同步（rules/07 + overview 两张图）：`docs/tasks/2026-09-02-M7-docs-align_rules_overview_outbound.md`
- 本轮文档审计义务（未闭）：`docs/tasks/2026-09-02-M7-audit-doc_audit_adr_4.md`

## 化石追加（v3 施工期史实，09-04）

- **否决留痕**：v2 的 tar 袋（自研 zip 编目）连同独立租约心跳被 ADR-0025 取代。真因不是性能：`file://` 指库在演示当场泄漏整仓历史（含 `.git`），"位置当身份"是病根。bundle 单文件的结构性隔离（封闭袋即宇宙）才是正解；旧 libgit 环境的 tar 回退通道保留，ref 格式不变。
- **守卫第一次生效是防到自己**：`merge_back` 脏守卫把编排自己落盘的报告/工单/state 判成"人的未提交改动"。修法＝进程件白名单＋**双向前缀**（porcelain 会把未跟踪目录折成 `docs/`，单向匹配漏放）。
- **派生物必须隐身**：`.k3dge/` 自动写进被审仓本地 `info/exclude`；陈旧 worktree 登记由 `ensure` 自愈（`worktree prune`＋重试）。审计证据不得污染案发现场的 status。
- **错误码不许过头**：`EXPIRED`/`NO_TARGET` 自 v0.6 起由"声明有"降为"预留未实现"（审计 L-1 处置）。

## 封板夜补（M7 seal 前，09-05）

- **未采用**：自动拉席做首跑审计席（`seat pi` 当时仅一次性模型——先人工后组件的次序被真案验证：组件版出来后首案照跑）；「调阈值让 quality 过闸」被质量席自己判为不当（有意留+登记票）；k3lity 草稿直写案卷区被事故否决（`--out /tmp` 断源）。
- **兑现**：ADR-0025 全链两案落地（审计 10 判 + 质量 8 判/94 材料）；「账本=唯一权威副本」在案卷互踩夜完成救援演示。
