---
Status: Draft
# Append-only after Accepted. Revise via `Amended by` / `Superseded by` below — do
# NOT rewrite this decision's prose in place, and never reuse a number (see README).
Supersedes: -
Amended-by: -
Date: 2026-08-24
Deciders: Core Maintainer
Note: 就地修订（非 Amend/Supersede）2026-09-02，经 Core Maintainer 本轮显式授权，依 `docs/adr/AUTHORING.md` Record lifecycle 合成条；本轮过闸口径 = `manual` fallback（实测 `[PEER-MANUAL] action 'k3dit.actions.audit' has no live lens`），未经真 k3dit 透镜复审
---

# ADR-0006: 对外注入面与并列 harness 编排（入向兼容层 + 出向通道）

> **Related**: ADR-0005（本地自用 / 职责切分）、ADR-0010（rules 切片）、ADR-0016（吸收纪律）、ADR-0021（doc-audit 非阻断）
>
> **就地修订留痕（2026-09-02）**：本文件正文被替换，非新开 ADR、非 Amend。作废/收窄的旧句在 §2.3、§2.4 逐条点名。`Status` 由 `Accepted` 回 **`Draft`**，理由随进度换过两次，记在这里以免被读成"决策反复"：
回 Draft 时（2026-09-02 早段）出向通道确实**没有实现**（`engine/pipeline_runner.py` 无 MCP 客户端，只有 `shutil.which("k3dit")` 探针）。
同日已补上真客户端与动作级透镜入口（`k3dit.actions.audit` / `k3lity.actions.quality` / `k3che.search` 实测 `provider=mcp`、零降级），
**但仍留 `Draft`**：① 入向（本仓自己的 server）在 `mcp` 2.x 下起不来，维护者指示先搁置（`docs/tasks/2026-09-02-M7-fix-k3dge_mcp2_resource_strict.md`）；
② §2.4 的"降级不可静默"只有规范，`milestone audit` 的报告**由谁执笔落盘**尚未定席；③ 未跑通的流程不该顶着 `Accepted`（闸按文档状态区分登记在 `docs/tasks/2026-09-02-M7-feat-check_gate_by_doc_status.md`）。

## 1. 上下文 (Context)

k3dge 先在本仓自用（ADR-0007 自举），下一步是用 k3dge 去开发另外三套并列 harness（audit / quality / cache）而不把它们长进 `src/k3dge`。两者都涉及"k3dge 如何与外部 harness 对接"，易与"MCP 是给本仓终端用户的第二套界面"混淆。

本仓的拓扑约束是**不对称的从属 + 对等的地位**：k3dge 只管一致性自治，peers 的功能由 **k3dge 调用来完成 audit/quality/cache**（功能上从属于 k3dge 的编排），但每个 harness 各自独立成仓、各自发自己的 MCP server、可被别的 harness 使用（地位对等）。

- 原文把 MCP 只定义成**入向**（外部 harness 注入 k3dge 的兼容层），出向（k3dge 连 peers）在决策里没有位置。后果是可复现的：`engine/pipeline_runner.py:152` 的 `mcp` 传输里根本没有客户端，只有一个 `shutil.which("k3dit")` 探针（`:109`）——"k3dge 使唤 peers"停在注释里，真正调 peer 的是 agent，调不到就由 agent 代笔。
- 同一探针把 `k3lity_score` / `k3che_search` 译成 `k3dit k3lity_score` 执行，与本 ADR §2.2 末条「harness 身份不混用」相抵。
- `AGENTS.md` 常驻内联的那一行（「审计回退……**不是独立审计**……须转人工」）已经要求**降级不可自证**，而旧 §2 末段却写"编排执行失败走 fallback / skip，**不改变一致性判定**"——同一条链在本仓两份权威文件里有两个说法，本 ADR 予以裁决。
- 本机 stdio 是唯一传输面（ADR-0005 local-first）：出向调用的对端仍是同一 OS 用户自己 spawn 的子进程，不新增信任域。

## 2. 决策 (Decision)

### 2.1 两个入口，都是"传输"，都不判定

- **CLI**（`k3dge.cli.main`）：本仓人/脚本原生入口（shell、pre-commit、CI）。
- **MCP**（`k3dge.cli.mcp`）：对外兼容层，只委托 `engine` / `sync` / `milestone`，零漂移；消费者是外部 harness，不是第二套交互设计。仍放在 `cli` 域（都是传输，不判定）。

### 2.2 并列 harness 模型

k3dge 是**一致性元门禁**；下列三者是独立仓，各自挂 k3dge（`K3DGE_SOURCE` 指向本检出）：

| Harness | 守什么 | 不守什么 |
| --- | --- | --- |
| **k3dge**（本仓） | 契约哈希、spec 结构、milestone 证据 | 好不好、怎么审、记不记得住 |
| **audit** | 五轮/8 维透镜、12 列报告（ADR-0017） | 不跑 `k3dge check` 的判定 |
| **quality** | 圈复杂度、重复、类型（ruff/mypy 等） | 不替代契约闸 |
| **cache** | 提高 Agent 命中率的检索/缓存 | 不进 engine、不做门禁出口码 |

- 禁止把 audit/quality/cache 做成 k3dge 的第五、六、七域。审计种子是 `docs/protocols/audit_default.md` / `verify_default.md`；透镜与 `check-report` 在 **k3dit**。
- 新仓 init 之后与自举 k3dge 同一套 Agent 协议（门控、`AGENTS.md` §12 触发、MCP 只走固定剧本）；`k3dge check` 在该仓 pre-commit 硬拦。脚手架幂等不覆盖已有 `AGENTS.md`/`scripts/init.sh`——协议升级要再同步这两份，不是 init 行为回退。
- **透镜审计不在 `src/k3dge`**（ADR-0005 §2.6）：MCP prompt 只指路，不在桥里演进规程。
- **信任边界**：本机 stdio 信任边界 = 调起该 MCP 的 OS 用户（S-13）；k3dge 作为出向客户端时同样成立（对端是自己 spawn 的本机子进程）；网络化后再重开鉴权。
- **harness 身份不混用**：其它并列 harness 自定入口，禁止共用 `k3dge_*` 工具名装成一个进程；且一个 peer 的传输**只准**命中该 peer 自己的 server/CLI（详见 §2.3）。

### 2.3 MCP 的方向性不变量【新增】

MCP 有两个方向，**互不借道、互不背书**：

| 方向 | 谁实现 | 谁调用 | 唯一事实源 |
| --- | --- | --- | --- |
| **入向** | 各仓自己的 `<pkg>.mcp`（stdio server） | 外部 agent harness | `.mcp.json`（该 harness 读它决定 spawn 什么） |
| **出向** | **k3dge**（stdio MCP 客户端） | k3dge 的编排（`milestone audit` / `seal` / `doc-audit`） | 同一份 `.mcp.json`（endpoint）+ `pipeline.toml`（流程） |

1. **每个 harness 各发一个 MCP server**，工具名带自己前缀，签名里不出现调用方的私有概念。peers 被第三方 harness 直连是正常态（MCP 无"一 server 一客户端"限制），不得为 k3dge 增设专用参数。
2. **`check` 是纯静态硬闸**：只验盘上文件与结构（schema / 符号引用 / 协议文件存在），**永不调用任何 agent、透镜或 peer 进程来帮忙验证**——不连 MCP、不跑 peer CLI（T-01 保留）。旧句把这条写在"pipeline.toml 支柱"段里，容易被读成"整条编排都不许连 MCP"，现予澄清：作域只限于 `check`；出向调用只发生在 `milestone audit` / `seal` / `doc-audit`。
3. **endpoint 单一事实源 = `.mcp.json`**（`command` / `args` / `env` / `cwd` 四字段即全部连接配方）。`pipeline.toml` 只声明流程：哪个 stage、调哪个 `tool`、fallback 链、超时——**不得重复写 endpoint**，否则两份配方必然漂移。
4. **`pipeline.toml` 仍是第三根门禁支柱**（旧句保留）：旧键 `[harnesses]` / `[hooks]` 必须 `PIPELINE_SCHEMA_INVALID`，不得当空 `peers` 放行；`k3dge check` 对它只验 schema / 符号引用 / 协议文件存在。
5. **gate 角色 peer 双传输出面**：绑定 **gate 类**角色（audit / quality）的 peer 必须同时提供 MCP server 与本机 CLI，使"无 MCP 的 harness / CI"仍有退路；缺 CLI 即视为未完成接入。**service 类（cache）豁免**：`mcp → skip` 是其正确终态（查询失败=能力暂缺，永不阻断放行链），CLI 属该产品完善项而非门禁要求。（分类依据：`docs/protocols/peer_contract.md` §0；本条收窄是修正 v0.2 把 cache 误并入 gate 模型的分类错误。）
6. **双主体铁律（2026-09-04 修正，旧条「k3dge 不产内容」是对『进程不产内容』的错误概括）**：k3dge 环境含两类 actor——**进程**（机械变换：输入定输出，可复算、可哈希验证）与**席位**（判断：自由发挥，必须署名）。铁律三条：
   ① 进程永不判断；
   ② 一切判断必须落到具名席位（`审计人` / `透镜来源` / `验收`）；
   ③ 无席位署名、或署名席位＝修改者的内容，**不得自动过闸**——只能带着 `WARN[DOWNGRADE]` 标签走人 attest 路径（§2.4）。
   出向调用不改变此律：报告正文与「待修/有意留」的裁量属**审计席位**；k3dge 进程只做形式校验、计数与字节落位。agent 经 manual 兜底在 harness 内写报告，正是产内容的行为——教义按 actor 陈述才成立。

7. **跨仓改动需被改仓授权**：k3dge 不得单方面改 peer 仓的文件。每次动 peer 仓都要该仓维护者在本轮显式授权，并在**该仓自己的** `docs/tasks/` 留痕（改了什麼、实测了什么）。约定变了就改写有那条约定的地方，不许留下自相矛盾的旧句。

8. **k3dge 调的是「动作」，不是「步骤」**：一次 `run_action` = peer 侧一件完整的事（例：「审这份目标」）。peer 内部跑几轮、什么顺序、用哪些子步骤，属该 peer 的私有实现，不得外溢成 k3dge 的调用参数。缺「动作级」入口时，补 peer 的入口，而不是在 k3dge 里循环拼步骤。

### 2.4 编排失败语义：降级不可静默【替换旧句】

旧句「**编排执行失败走 fallback / skip，不改变一致性判定**」（T-01 后半）**作废**，改为：

1. **不可静默**：任何一次降级（`mcp`→`cli`、`mcp`/`cli`→`manual`、→`skip`）都要显式表述到四个地方：
   - stderr 一行 `WARN[DOWNGRADE] <action> <reason> <后果>`；
   - `logs/k3dge.log`（机器可读，供事后复述）；
   - 当轮 12 列报告的 `透镜来源` + `审计人/验收人`（例：`downgrade=mcp->manual action=k3dit.actions.audit reason=no live lens`）；
   - **出总结时必须高亮**：本轮哪几项判定是降级产物、因此不是独立审计。高亮义务同时在 k3dge 输出面（`[NEXT]` / 回执）与 agent 汇报面。
2. **不设逐次放行开关**：曾考虑的 `--allow-manual-audit` **不采纳**。`manual` 是合法档位，机器不逼你申请，只逼你说出来（上一项）。
3. **但降级产物不是独立审计**：干活的 agent 不得拿 `manual` 出的报告自证"审过了"（`AGENTS.md` 常驻行与本条同调）。`escalated` 只剩一个含义：**审计链整体落到 `manual` 且人未确认它作数时，`seal` 不放行**——不是"没申请就报错"。
4. `skip` 只允许用于**不在必做链上**的 peer（cache），语义不变：记 `HARNESS_SKIP` 即算通过该 stage。
5. `check` / `status` 可以**读取上述已落盘的降级事实**并复述高亮，但不得为此自行连 MCP 或跑 peer CLI（§2.3.2）。本轮取向是把流程**调通**，不是验证兜底能力；fallback 本身的可用性由后续里程碑专门测。

### 2.5 非目标 (Non-goals)

- 不做服务发现、不做注册中心、不做跨机传输（网络化重开 §2.2 信任边界）。
- 不在 k3dge 内实现任何透镜、评分或报告正文生成（含"顺手算个分"）。
- 不让 k3dge 的出向通道反向成为别人的门禁（peers 不得 import k3dge 判定核）。
- 不把 `Status: Draft` 的决策当作已生效——投递与生效分开（`ADR-0011`/`ADR-0012`）。

## 3. 产生后果 (Consequences)

- **Up**：`"k3dge 使唤 peers"` 从注释变成可判定的架构位置；endpoint 一处定义、两个读者（外部 harness 与 k3dge）；sidecar 边界因"证据来自进程外"而**变硬**（旧状态下 manual 是唯一实际路径，等于默认自审）；`AGENTS.md` 常驻行与本 ADR 不再互相否定。
- **Down**：k3dge 开始持有子进程生命周期（spawn / 超时 / 清理 / stderr 归集），多一处故障面；每次出向调用冷启动实测 ≈0.81–1.01 s（`k3che` 真握手，3/3），5 Pass 量级可接受但 CI 会慢；`escalated` 语义一旦生效，未装 peers 的机器上 `seal` 将不可用（必须逐次人工放行，这是刻意的）；`.mcp.json` 成为 k3dge 的输入 ⇒ 该文件形状变更同时影响外部 harness 与 k3dge（public 面，见 `docs/tasks/2026-09-02-M7-feat-peer_outbound_mcp_client.md`）。
- **Reopen when**：① 出向通道真实现并跑通一轮 audit/quality（届时本 ADR 转 `Accepted`，并按 append-only 收编遗留）；② 需要跨机 / 多用户传输（鉴权重开）；③ 主流 harness 开始默认扫描 `.agent/` 或显示点目录（ADR-0011 的发现面结论）；④ `check` 若被要求按文档 `Status` 区分严格度（已登 task，本轮不迭代）。
