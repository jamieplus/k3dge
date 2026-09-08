# Peer Contract — k3dge ↔ 外部 harness 接口协议 (v0.6)

> **事实源**: k3dge 与 peers（audit / quality / cache）之间的编排接口机器契约。k3dge 只验信封与形式，不验内容。本页改动＝契约变更：`k3dge sync` + 下游四仓跟随。相关决策：`ADR-0006` §2.3（方向/角色/动作级）、`ADR-0017`（12 列报告）、`ADR-0005`（本地优先）。

## 0. 定位与角色模型

- 协议层 = MCP stdio；每仓一个 server；endpoint 登记表 = `.mcp.json`（唯一，不得在 `pipeline.toml` 重复 `command/args/env/cwd`）。
- k3dge 只认三个**角色**：`audit / quality / cache`。`[roles.<role>] bind = "<server>"` 一行完成角色→具体 harness 绑定；**k3dge 代码不出现具体 harness 名**。
- 角色分**两类**，契约按类分化（v0.3；把 cache 硬套 gate 模型是 v0.2 的分类错误）：

| | gate 类（audit / quality） | service 类（cache） |
| --- | --- | --- |
| 定位 | 编排对象：派活→收工件→验→计数→进放行链 | 查询服务：同步一问一答；失败＝能力暂缺，**永不阻断流程**（现消费者：① k3dge doc-audit 相关文档前路由；② `k3dge status` 观测行——`.k3che/` 存在才探活，观测永不进判定；③ `task create` 相似检查（语料含 tasks/archive；只提示不裁决）。证据/台账不归 k3che，见 §7 v0.5 修正） |
| 输入 | 审计线（§3：一单一线一 checkout，锁点 L=基线） | 无送检——它**持续只读**消费仓文件（同机信任域），尽力而为的新鲜度 |
| 输出 | 工件 `report/findings`，落 `docs/reviews/`，有计数语义 | `hits` + 命中率，**不是门禁工件，不进放行链** |
| provenance/baseline | 必须（不符即拒收） | 不适用（没有"某次审计的输入快照"可言） |
| 时序 | `submit/collect` 两态，等待活在协议外（§1） | 同步单次调用（§1 的 `call` 简式） |
| 失败终态 | 降级 → `escalated` → 人确认 | `skip` 即正确终态（`mcp → skip` 合法）；同样要 `WARN[DOWNGRADE]` 如实可见 |
| 绑定声明 | `[roles.audit] bind = "…" kind = "gate"`（默认） | `[roles.cache] bind = "…" kind = "service"` |接口与协议对得上即可换实现（含桩：`bind = "dummy"`）。
- 边界清单（硬约束）：
  - k3dge **永不知道**：跑几轮、几席、什么模型、内部怎么分工；
  - peer **永不知道**：k3dge 的闸判据、seal 条件、里程碑状态；
  - 交换只有两样：事实进（审计线交件 + 调用方领域事实），工件出（信封包裹的三种工件）。

## 1. 调用流程：gate 类 submit / collect 两态异步；service 类同步 call

**service 类（cache）＝简式**：一次 `call_tool(tool, {query, …}) → {ok, kind:"hits", payload}`，无 submit/collect、无 job、无基线；超时/失败 ⇒ `skip` 降级（`WARN[DOWNGRADE]` 后继续，不改任何流程结论）。以下 §1.1–§1.3 仅适用于 **gate 类**。

### 1.1 gate：submit / collect

```
role.submit(baseline, scope, milestone_id, branch, wt_dir)
                                         → {ok, kind:"job", payload:{job_id}}    ≤10s，只做校验+入队
role.collect(job_id)                     → {ok, kind:<工件>, payload:{…}}        完成
                                         → {ok:false, error:"PENDING", retry_after:N}
                                         → {ok:false, error:"EXPIRED|NOT_FOUND|INTERNAL|…"}
```

- 协议调用必须短；**长等待活在协议外**：k3dge 把 `job_id` 落进编排状态（`.agent/audit_checklist.json`），`[NEXT]` 置 `awaiting_audit`，何时 collect 由外层决定。
- `job_id` 不透明：job 执行状态在 peer 内部，k3dge 不问、不解释、不据此重试。
- `collect` 幂等可重试；`EXPIRED / NOT_FOUND` ⇒ 重新 submit ⇒ **审计线重新 advance 锁新基线** ⇒ 旧报告对新基线自动作废。

### 1.4 工单模型＝棘轮（ratchet）：一单 = 一快照（2026-09-04 定稿）

- 一工单一快照；单内**审↔修可交替多程**（快照复用，不逐步重打包）；出场一次 patch-back 进基版。串行是环境事实（工单皆经 k3dge 发起），不是规则。
- **交换介质 = 审计标记**（§8），不是报告表格：审席标注/裁决、修席改码＋翻转标记（顺手修须以 `fixnote` 登记，未复核不得关单）；补丁基线不符/冲突 ⇒ rebase 到最新基版、第三方改动重挂、**人工确认影响**，触碰发现面则同单续一程复核。
- 结项：账本清零 ⇒ 对端转 `pending_report`（**机器不自签**）；审计席跑 `audit-report` 机械渲染草稿（账本⋈终态，纯 join）、**复核后署名交回**（`sign-report`：形检＋覆盖账本全部条目）⇒ 工单 `done`，随 collect 回流；k3dge 落位自己的 `docs/reviews/` 并把 worktree 分支 **merge 回主干**（P1：默认自动；脏树/冲突 ⇒ 停并升级人工，见 §3）。各仓 docs 只住自己的开发文档，对端永不写他仓。
- 同 ID `disputed` 往返 ≤3，超限工单 `escalated` 人工裁决。

## 2. 信封与错误分类（provenance/baseline 仅 gate 类必需）

```jsonc
// 成功
{"ok": true, "kind": "report|findings|hits",
 "payload": { /* 见 §4 */ },
 "provenance": {"seat": "<格式自由，必须非空>", "generated_at": "<ISO-8601>",
                "baseline": "<审计线锁点 L 的 commit oid>", "lens_version": "<audit harness 发布的规则版本>"}}
// 失败
{"ok": false, "error": "<封闭枚举>", "message": "<peer 自述，人话>", "detail": { /* 可选 */ }}
```

- 错误码封闭枚举（机验）：`NO_TARGET / BAD_ARGS / BAD_BUNDLE / PENDING / EXPIRED / NOT_FOUND / FORMAT / INTERNAL`。其中 `EXPIRED` 与 `NO_TARGET` 为**预留未实现**（v3：claim 即续期、租约制废；定位失败由 `NOT_FOUND/INTERNAL` 表达）。
- **报原因，不探内部**：`error` + `message` 由 k3dge 原样透传进 `WARN[DOWNGRADE]` 与 `logs/k3dge.log`；k3dge 不越过信封猜测对方内部，不做依赖内部知识的重试。
- 机验面：信封合法性、`kind` 枚举、**gate 类**另验 `provenance` 三字段、工件格式（§4）＝硬闸；内容质量与 `seat` 诚实性＝k3dit/人。
- service 类无 provenance 要求；其 `hits` 的排序质量属 k3che 内部事，好坏由命中率统计观察，不进门禁。

## 3. 审计线（Audit Line）＝gate 类唯一输入形式（service 类不适用，见 §0 分类表）

送检＝在消费仓 `.git` 里为这一单长出一条线（`k3dit/<单>`，自锁点 L 拉起）＋一个 checkout（worktree）。对象格式、树布局与主干天然一致；袋/独立库/打包器全部退役（`ADR-0026` 重设计）。递件分三截，文件怎么递、谁碰 git 写死如下——

- **① k3dge → Hall（递审）**：交件句柄全是字符串——`baseline`（=L，线头 commit oid，即基线；tree 可由 commit 导出）、`branch`、`wt_dir`（已 checkout 的现场目录）、`scope`（送检范围说明——Hall 物化参数，不是内容边界）。内容不过 JSON-RPC、不过对端账本。**Hall 是这个 `.git` 的唯一客户**：checkout、commit、advance 提版全经 k3dge 进程动词；席拿不到仓路径。
- **② Hall → 席（窗口桌面）**：Hall 从 L（或已 advance 的最新版）checkout 一份，按 scope 裁剪成**审计纯净版**（只含本窗要看的目录；**不带指向仓的 `.git`**），分发给各判读窗（文档→代码→价值，窗序固定——`ADR-0027` §2.2）。席只在这棵目录里按同一套标记规范钉或改，写完交差。Hall 把各窗产出 **merge 成当前版本**（判读 merge，只合判断物，不管代码对错——那是窗的事），经 `k3dge audit advance` 提一版（混排全收，进程代 commit，作者 `k3dge-process`——机械件，非席位署名；`git update-ref` CAS，非快进即拒；**提版即重钉**：在办单 baseline=新线头，报告按最新基线签；`--by` 记调用方身份落账）；再把当前版本交**修席窗**改，改完提一版；再交**复核窗**验收——验收过则本轮结束，不过则**打回修席**（只回修席，不跳窗、不插队）。判读窗**不改版本、只出版本**。
- **③ Hall → k3dge（收口）**：`collect` 仍是信封：12 列＋`provenance.baseline` == 在办单基线（最新线头）。合主干用的不是袋，是线上最终 commit L′：k3dge 对消费仓做 ff，ff 不成则 `rebase --onto <主干头> <base> <线>` 重演再 ff（线提交全是机械件；冲突 ⇒ abort 复原＋升级人工，不自作主张）。闸过合主干后删现场删线（线仅在已并入时删；未并入保留原位供幂等重试与崩溃恢复）。废单＝删分支，主干从未脏。
- **隔离归属**：审计线不污染主干＝ref + 本地 `info/exclude` + 闸过删线；窗隔离＝Hall 物化拷贝 + CLI 原生 root/deny（`ADR-0027` W1）。数据最小化重心从"打包脱敏"移到"物化裁剪"（同信任域，`ADR-0006` S-13；scrub/target/ 前缀/签名骨架随打包器一并退役）。
- **基线** = 最新线头 commit oid（submit 锁 L，advance 重钉；L 只是首钉）；报告 `provenance.baseline` 必须与在办单基线一致，不一致 ⇒ `FORMAT` ⇒ 拒收。主干在线之后再走 ⇒ closure 合并按 §1.4（ff→重演，冲突升人工）。
- **呈现由进程供给**：`complete_round` 的 present 以 worktree 机械抽取（§8）为准（送达递增 `present_seq`，对端凭 seq 判新旧）；席位口述仅作交叉核对，口径不符 ⇒ 该轮 `FORMAT` 拒。
- **Hall 查询动词（不进席）**：`audit show`（读本地账：baseline/branch/merge_ok/advances/present_seq＋本地降级尾——`status` 查的是对端）；`audit materialize`（按 oid 只读物化，无 `.git`、不碰线）。
- **待接（与 H2 实现同批）**：契约上下文（cache 角色召回本改动相关 ADR/Specs）由 Hall 物化时拼进窗口目录（随 scope 尽力而为；无 H3 时线照样成立）。在此之前该线不预焊。

## 4. 工件（输出，三种）

| kind | payload | 机验 | 产出方 |
| --- | --- | --- | --- |
| `report` | 12 列表格 markdown ＋ 元信息行（审计人/透镜来源/基线/范围） | `ADR-0017` `*_check_report` ＋ 待修/有意留/已修 计数自洽 | audit 席 |
| `findings` | `[{id,severity,type,desc,path,line}]` ＋ summary 计数 | 字段齐、枚举合法 | quality |
| `hits` | `[{path,title,score}]` ＋ `hit_rate` | 结构齐（**service 类：观测指标，不参与放行判定**） | cache |

k3dge 对通过信封的字节**机械落盘**（`docs/reviews/`，记 hash，绝不补写或改写内容），然后只数计数、决定放行。

## 5. 兼容与桩

- 骨架期：`bind = "dummy"`（`tests/fixtures/dummy_peer.py`，同契约、canned 工件：一份 `待修=2`、一份 `待修=0`）。真 peer 在各自仓内替换，**k3dge 一行不改**。
- 过渡：legacy `k3dit.actions.*` / `k3lity.actions.*` 调用名映射到 `audit.* / quality.*`；角色绑定全量落地后废弃。

## 7. 审计复用（CAS）与锁——预筛只作用于人工入口（v0.3.1；锁 v0.6）

- **锁与租约（v3）**：`claim_round` 即续租（无独立心跳/续期 RPC）；快照推进与分支更新一律 `git update-ref <ref> <new> <old>` CAS（进程内 jobs 锁）。

- **自动入口**（`[NEXT] audit_suggested` 触发评估）：**不预筛、不短路**。checklist 求值（账齐/C2/体积）是零成本静态扫描；基线未变时条件仍满足就照问审计问题，没有错。短路它省不了成本，反而制造"缓存故障 ⇒ 免审"的通道——预筛只允许发生在人主动要求跑审计的地方。
- **人工入口**（`k3dge milestone audit <id>`）：预筛。三条件**全部**形式成立 ⇒ 告知"无审计需要执行"（附报告路径与键），提示 `--force`：
  1. 存在 `待修=0` 的闭环 12 列报告；
  2. 其 `provenance.baseline` == 线上基线（§3：L 的 commit oid）；
  3. 其 `provenance.lens_version` == k3dit 当前发布值（peer 只新增这一项义务；**无需新 RPC**）。
- **存储分层（v0.5 修正：k3che 从证据存储除名）**：预筛来源两级——① k3dit 案卷（其 store 即档案馆，OID 即索引，跨仓复用=同一部署多 consumer 天然命中）；② 消费仓本地 `docs/reviews/`（含 archive）。镜像/备份＝机构自身运维手段，不入协议；k3che 回归 token 经济（检索/观测/查重），不承载证据存储。CAS 层不可用 ⇒ 退化为仅本地检查；任何 CAS 故障**永不**扩大为跳过审计（`ADR-0006`：service 失败=skip，不进判定链）。
- **痕迹**：预筛命中/落空都写 `logs/k3dge.log` 一行 `PRE-FILTER action=audit verdict=closed|run key=<baseline>@<lens_version> src=<报告路径>`。"静默"只作用于打扰，不作用于痕迹。
- `--force`：跳过预筛直接全量。审计输出非确定，复用信任必须随时可破。
- 预筛不制造新状态：闭环与否仍由 `audit_closed()` 判；预筛省的是**重跑成本**，不是判定。seal 的 attest 不因复用继承（不变）。
- 角色归属（按 §0 表）：lens 版本归 k3dit 发布；blob 存取归 k3che（台账/镜像，只答"有没有"，不答"能不能用"）；三条件比对与流程分叉归 k3dge（纯形式校验，不解释对方内部）。

## 6. 违反契约时

- 信封不过 / 工件不过 / `baseline` 不符 ⇒ 该次传输记失败 ⇒ `WARN[DOWNGRADE] action=… reason=…` ⇒ 走 `pipeline.toml` 链上下一档；全败 ⇒ `escalated`，`seal` 不放行。**不存在"静默收下不合格工件"**。

## 8. 标记语法 v1（findings 的树侧介质；权威实现 `src/k3dge/engine/markers.py`）

```
k3dit:<kind> <ID>[@<scope>] [ <一句话 ≤80字符> ]
kind ∈ pending | leftover | disputed | fixnote      open := pending+disputed+fixnote（结项须清零）
scope ∈ line(缺省) | file(只准文件头部注释块) | repo(只准仓根 AUDIT.md 条目)
注释宿主： #（py/toml/yaml/sh…） //（js/ts/go/rust…） <!-- -->（md/html）
```

- **指针纪律**：树上只放 状态＋ID＋一句摘要；正文（严重度/类型/证据/how-to-fix）住 k3dit 账本，报告由二者 join 渲染。示例（占位符 `<ID>` 故意不可匹配，防本文自触发扫描）：`# k3dit:pending <ID>@line 未设超时`。
- **状态机**：`pending`→修好**删标**（git diff 即结案凭据）/ `leftover`（有意留，长期文献，给未来读码者）/ `disputed`（修席不认，审席裁决：删=p撤回、回 pending=坚持、转 leftover=认账）；`fixnote`（修席顺手修）→审席复核认可即删，否则升 `pending`。同 ID 往返 disputed ≤3。
- **ID 发放**：claim 时 k3dit 随包发号段（A 段审席发现 / F 段修席发现）；无源 ID＝违规（`k3dge markers --check` 可拦，CI 用）。
- **一发现一主锚**（leftover 例外随文件走）；多文件发现**只住 AUDIT.md**，不散钉。
- k3dge 消费面：`[NEXT] pending_findings` 计数口径＝open 三态（历史 pending-only 的扩展，leftover 仍不计时）；`k3dge markers [--json|--check]` 为人和 CI 提供同一视图。k3dit 复审＝diff 两快照的抽取结果，只裁 新增/仍在/消失 三类。
