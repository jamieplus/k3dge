# Peer Contract — k3dge ↔ 外部 harness 接口协议 (v0.6)

> **事实源**: k3dge 与 peers（audit / quality / cache）之间的编排接口机器契约。k3dge 只验信封与形式，不验内容。本页改动＝契约变更：`k3dge sync` + 下游四仓跟随。相关决策：`ADR-0006` §2.3（方向/角色/动作级）、`ADR-0017`（12 列报告）、`ADR-0005`（本地优先）。

## 0. 定位与角色模型

- 协议层 = MCP stdio；每仓一个 server；endpoint 登记表 = `.mcp.json`（唯一，不得在 `pipeline.toml` 重复 `command/args/env/cwd`）。
- k3dge 只认三个**角色**：`audit / quality / cache`。`[roles.<role>] bind = "<server>"` 一行完成角色→具体 harness 绑定；**k3dge 代码不出现具体 harness 名**。
- 角色分**两类**，契约按类分化（v0.3；把 cache 硬套 gate 模型是 v0.2 的分类错误）：

| | gate 类（audit / quality） | service 类（cache） |
| --- | --- | --- |
| 定位 | 编排对象：派活→收工件→验→计数→进放行链 | 查询服务：同步一问一答；失败＝能力暂缺，**永不阻断流程**（现消费者：① k3dge doc-audit 相关文档前路由；② `k3dge status` 观测行——`.k3che/` 存在才探活，观测永不进判定；③ `task create` 相似检查（语料含 tasks/archive；只提示不裁决）。证据/台账不归 k3che，见 §7 v0.5 修正） |
| 输入 | 送检包（§3：一次性、可复现、有基线） | 无送检包——它**持续只读**消费仓文件（同机信任域），尽力而为的新鲜度 |
| 输出 | 工件 `report/findings`，落 `docs/reviews/`，有计数语义 | `hits` + 命中率，**不是门禁工件，不进放行链** |
| provenance/baseline | 必须（不符即拒收） | 不适用（没有"某次审计的输入快照"可言） |
| 时序 | `submit/collect` 两态，等待活在协议外（§1） | 同步单次调用（§1 的 `call` 简式） |
| 失败终态 | 降级 → `escalated` → 人确认 | `skip` 即正确终态（`mcp → skip` 合法）；同样要 `WARN[DOWNGRADE]` 如实可见 |
| 绑定声明 | `[roles.audit] bind = "…" kind = "gate"`（默认） | `[roles.cache] bind = "…" kind = "service"` |接口与协议对得上即可换实现（含桩：`bind = "dummy"`）。
- 边界清单（硬约束）：
  - k3dge **永不知道**：跑几轮、几席、什么模型、内部怎么分工；
  - peer **永不知道**：k3dge 的闸判据、seal 条件、里程碑状态；
  - 交换只有两样：事实进（送检包 + 调用方领域事实），工件出（信封包裹的三种工件）。

## 1. 调用流程：gate 类 submit / collect 两态异步；service 类同步 call

**service 类（cache）＝简式**：一次 `call_tool(tool, {query, …}) → {ok, kind:"hits", payload}`，无 submit/collect、无 job、无基线；超时/失败 ⇒ `skip` 降级（`WARN[DOWNGRADE]` 后继续，不改任何流程结论）。以下 §1.1–§1.3 仅适用于 **gate 类**。

### 1.1 gate：submit / collect

```
role.submit(bundle, scope, milestone_id) → {ok, kind:"job", payload:{job_id}}    ≤10s，只做校验+入队
role.collect(job_id)                     → {ok, kind:<工件>, payload:{…}}        完成
                                         → {ok:false, error:"PENDING", retry_after:N}
                                         → {ok:false, error:"EXPIRED|NOT_FOUND|INTERNAL|…"}
```

- 协议调用必须短；**长等待活在协议外**：k3dge 把 `job_id` 落进编排状态（`.agent/audit_checklist.json`），`[NEXT]` 置 `awaiting_audit`，何时 collect 由外层决定。
- `job_id` 不透明：job 执行状态在 peer 内部，k3dge 不问、不解释、不据此重试。
- `collect` 幂等可重试；`EXPIRED / NOT_FOUND` ⇒ 重新 submit ⇒ **强制重建送检包** ⇒ 新 hash ⇒ 旧报告对新基线自动作废。

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
                "baseline": "sha256:<bundle 内容哈希>", "lens_version": "<audit harness 发布的规则版本>"}}
// 失败
{"ok": false, "error": "<封闭枚举>", "message": "<peer 自述，人话>", "detail": { /* 可选 */ }}
```

- 错误码封闭枚举（机验）：`NO_TARGET / BAD_ARGS / BAD_BUNDLE / PENDING / EXPIRED / NOT_FOUND / FORMAT / INTERNAL`。其中 `EXPIRED` 与 `NO_TARGET` 为**预留未实现**（v3：claim 即续期、租约制废；定位失败由 `NOT_FOUND/INTERNAL` 表达）。
- **报原因，不探内部**：`error` + `message` 由 k3dge 原样透传进 `WARN[DOWNGRADE]` 与 `logs/k3dge.log`；k3dge 不越过信封猜测对方内部，不做依赖内部知识的重试。
- 机验面：信封合法性、`kind` 枚举、**gate 类**另验 `provenance` 三字段、工件格式（§4）＝硬闸；内容质量与 `seat` 诚实性＝k3dit/人。
- service 类无 provenance 要求；其 `hits` 的排序质量属 k3che 内部事，好坏由命中率统计观察，不进门禁。

## 3. 送检包（Audit Bundle）＝gate 类唯一输入形式（service 类不适用，见 §0 分类表）

废除"传仓库路径"：传活路径＝暴露消费仓内部＋审计对象漂移。输入只能是打包好的送检包。

- **构成**：
  - `target/`：待审目标源文件全文；有 git 基线时附变更范围（diff 清单），**避免全量漫游**；
  - `signatures/`：目标文件依赖的本地模块经轻量 AST（std `ast`，tree-sitter 可选）抽成**签名骨架**——仅函数签名/类结构/类型注解的"头文件"，几 KB，消除对跨文件符号的幻觉；
  - `MANIFEST.json`：排序清单 + 每文件哈希 + 包哈希（确定性打包：排序、归一 mtime/uid/gid）。
- **打包器** = k3dge 模块 `engine/bundle.py`（送检范围归调用方所有）；配置 `.agent/bundle.toml`：`ignore`（`__pycache__` / `.DS_Store` / `node_modules` / `logs` 等噪音）、`max_bytes`、`scrub.keys`（指定 key 模式**在出门前**脱敏）、`include / exclude`、`mode = tree|diff`、`format`。
- **身份与位置分家（v3，ADR-0026）**：身份 = 送检包的 git-tree oid（`cas://sha256:<tree-oid>`，即基线）；位置 = **bundle 单文件**（同机路径）或其 URL（远程）——同一身份两种摆法，协议不分叉、不逐层回源。内容不过 JSON-RPC、不过对端账本：submit/claim 只传引用与**字符串句柄**（file/commit/config_digest）。
- **bundle 即宇宙**：每份包由进程从 store（`.k3dge/store.git`，专用裸库，sha256 对象格式）的 `refs/snap/<job>` 提交链现建（`git bundle create`；thin 缺段自动补 full）。席位 `git fetch <袋|url>` 一步得全部对象，**永不遍历客户端 store**——结构性隔离，不是礼貌约定。旧 git 无 sha256 支持 ⇒ 回退确定性 tar 袋，ref 格式不变。
- **工作现场 = 分支**：快照链是消费仓 `k3dit/<job>` 分支上的提交（进程代提交，作者 `k3dge-process`——机械件，非席位署名）；席位在 `.k3dge/wt/<job>` worktree 内读写，`k3dge audit advance` 推进（`git update-ref` CAS，非快进即拒）；closure 时 `merge_back` 回主干（ff 优先，真 merge 兜底，脏树/冲突 ⇒ abort 复原并升级人工）。派生目录自动写进被审仓本地 `info/exclude`。
- **取件/对比** = `k3dge bundle resolve <ref> [--extract 目录]` / `git ls-tree` 两快照对比（`store.diff`）；end-flow（seal）后 bundle 袋与 worktree 即焚（`prune`），store 与已合并分支史保留。\n- **泄漏准入不变量**：store 只装 scrub 后的派生树，永不写入被审仓 `.git`；孤儿对象随 `git gc` 原生过期。\n- **基线** = 包内容哈希；报告 `provenance.baseline` 必须与之一致，不一致 ⇒ `FORMAT` ⇒ 拒收。
- **主权（硬约束）**：对端账本只存工单元信息——句柄字符串、findings 正文、席与戳；**一字节客户端代码都不落对端盘**（备份/镜像＝机构运营手段，非协议义务）。打开袋的永远是席位侧。
- **呈现由进程供给**：`complete_round` 的 present 以 worktree 机械抽取（§8）为准；席位口述仅作交叉核对，口径不符 ⇒ 该轮 `FORMAT` 拒。
- **待接（与 H2 实现同批）**：送审包应含**契约上下文**——由 cache 角色召回本改动相关的 ADR/Specs 放入 `context/`（随包哈希一起钉死；无 H3 时包照样成立，context 尽力而为）。在此之前该线不预焊。

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
  2. 其 `provenance.baseline` == 当场重算的送检包哈希（§3）；
  3. 其 `provenance.lens_version` == k3dit 当前发布值（peer 只新增这一项义务；**无需新 RPC**）。
- **存储分层（v0.5 修正：k3che 从证据存储除名）**：预筛来源两级——① k3dit 案卷（其 store 即档案馆，OID 即索引，跨仓复用=同一部署多 consumer 天然命中）；② 消费仓本地 `docs/reviews/`（含 archive）。镜像/备份＝机构自身运维手段，不入协议；k3che 回归 token 经济（检索/观测/查重），不承载证据存储。CAS 层不可用 ⇒ 退化为仅本地检查；任何 CAS 故障**永不**扩大为跳过审计（`ADR-0006`：service 失败=skip，不进判定链）。
- **痕迹**：预筛命中/落空都写 `logs/k3dge.log` 一行 `PRE-FILTER action=audit verdict=closed|run key=<bundle_hash>@<lens_version> src=<报告路径|cas|absent>`。"静默"只作用于打扰，不作用于痕迹。
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
