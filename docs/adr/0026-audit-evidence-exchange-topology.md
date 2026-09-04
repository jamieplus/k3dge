---
Status: Accepted
# Append-only after Accepted. Revise via `Amended by` / `Superseded by` below — do
# NOT rewrite this decision's prose in place, and never reuse a number (see README).
Supersedes: -
Amended-by: -
Date: 2026-09-04
Deciders: Core Maintainer
Note: -
---

# ADR-0026: 审计证据交换拓扑（bundle 单文件 · 数据最小化 · 分支写回）

## 1. 上下文 (Context)

棘轮审计（一单=一快照、单内审↔修交替）确立后，证据如何在 k3dge / k3dit / 席位之间流动成为剩余分歧点。多轮推演排除的形态（详见 `docs/memo/2026-09-02-peer-wiring-and-seat-options.md` 废案账）：MCP 分块上传（自造管道）、file:// hint（暴露对象库全历史）、"证据随案卷"入 k3dit（违背数据最小化）、ack 驱动 GC（编排越权）。信任前提：打包是**纯进程**（机械筛选、配置驱动、无 agent 参与），同机同信任域（`ADR-0006` S-13），审计不兼任监管——针对"被审方自欺"的防伪件不成立。

## 2. 决策 (Decision)

### 2.1 主权四章（各归其一，无重叠）

| 物 | 主权 | 依据 |
| --- | --- | --- |
| 证据本体（快照/树对象/bundle 文件）与 **GC** | **k3dge**（消费仓）：`.k3dge/store.git`＋bundle 文件；清理只挂 **end-flow 钩子**（seal 收口），流程中间站（audit→qa→…）可续用同一袋 | 被审物不迁主权；GC 需要流程全局视野 |
| 工单：findings 正文、裁决史、状态机、报告 | **k3dit**：账本只存机构自身的判断物＋引用（tree oid、bundle sha、config_digest），**不存一字节客户代码** | 数据最小化：处理者不因处理而存档委托方资料 |
| 阅件 | **席位**：claim 得 `bundle{ref,file|url,sha,config_digest}`，自取至临时区，阅后即焚（处理≠归档） | 同左 |
| 报告 | **审计席位**产出并签署；渲染=机械抽取（账本⋈delta），席位只运行与署名，不重打字 |
| 报告落位 | **k3dge 进程**：按本仓命名规约机械放置 `docs/reviews/`（可复算、可哈希验证，不产判断） | `ADR-0006` 双主体铁律（§2.3.6） |

**裁决签名规则（P3）**：账本状态翻转（`fixed/disputed/leftover` 终局）只能由**审计席位**提交；修席的合法动作=改码＋删/转标记＋登记 `fixnote`。整份报告由审计席**运行抽取脚本**从 delta 生成并署名——判的人写判，修的人只改物，笔和章不分离才奇怪。

### 2.2 交换原子：git bundle 单文件（统一形状）

- 一快照=一 bundle：封闭集、自校验、单文件即宇宙；隔离是结构性的（袋外无物），不靠配置。
- **形状唯一，优化走参数**：快照链=分支上的 commit 序列；`has`（前置 oid 列表）为可选参数实现轮间薄包——同一条 create 路径，禁止"全量/增量"两套模式（防漂移，内部优化自由）。
- 身份=tree OID（`cas://sha256:<oid>`），远近只是 `file|url` 之差，协议无分支；远程取件=传输同一个文件，不新增机制。
- `pack_provenance{config_digest, mode, git_version}` 进 manifest：**为可复现性**（基线差异可归因），不作防伪（见 §1 信任前提）。

### 2.3 写回拓扑：分支即快照链（P1/P2 已拍板 2026-09-04）


- 主干**只在 closure 时**接收合并；**合并默认自动执行，冲突即停并升级人工**（rebase 按 §1.4 流程带确认）——机器负责搬运，人只在物理分歧处出现（P1）。
- 账本载"判"、分支载"物"：裁决状态权威始终在 k3dit 工单簿，分支不复制真相。
- 轮次分支 ref 住**消费仓 `.git`**（分支是消费侧的物），对象库只装对象（P2）。
- 废单=删分支（主干从未脏）；崩溃恢复=分支原位续走；过程留痕=`git log k3dit/<job>`。

### 2.4 复用与校验

- 跨仓/跨单复用（§7 预筛）按 **oid × lens_version 匹配工单簿结论**——不需要持有客户内容即成立，与最小化自洽。
- 完整性链条：进程确定性（打包）＋ 席位 fetch 时 git 自校验 ＋ collect 的 `provenance.baseline` 比对；k3dit 无内容故不做内容验货。

### 2.5 非目标 (Non-goals)

- 不建 k3che 证据/CAS 角色（回归 token 经济，`ADR-0023` §7 v0.5 既定）。
- 不做"镜像/备份"入协议（机构运维手段）。
- 不引入被审方防伪机制（信任域内，§1）。
- 不实现范围由本 ADR 承诺的远程部署（push/服务发现等），其形状已被 §2.2 约束（传输同一文件），到实施时另行设计。

## 3. 产生后果 (Consequences)

- **Up**：客户数据全程零第二次落盘；k3dit 无客户代码 ⇒ 案卷体积=判断物＋引用；交换/写回/复用/远程共用一个原子与一条协议形；漂移面（thin/full、local/remote、auto/manual GC 诸模式分叉）被参数化封死。
- **Down**：案卷回看在 end-flow 后依赖消费仓留存策略（主权已声明，接受）；席位需能读 bundle（git 基础件，成本低）；远程大袋的传输优化留给实施。
- **Reopen when**：① 跨信任域部署成真（防伪前提变化，§2.2 provenance 件升级或另立）；② 流程出现"多站并行"（GC 钩子归属需重审）；③ 冲突升级后的人工 rebase 决策若频繁出错（届时再谈是否收紧自动合并的范围）。
