---
Status: Proposed
# Append-only after Accepted. Revise via `Amended by` / `Superseded by` below — do
# NOT rewrite this decision's prose in place, and never reuse a number (see README).
Supersedes: -
Amended-by: -
Date: 2026-09-04
Deciders: Core Maintainer
Note: ① 2026-09-07 两次就地修订（Proposed 未定稿，AUTHORING「过早 Accepted 可就地修订」条）：第一次撤回「bundle 单文件＝交换原子」（本地信任域内袋属过度设计）→ 沙盒直读；第二次撤掉独立库与打包器——审计线模型：交换物即消费仓 `.git` 里的一单一条线（+checkout），merge 即普通 git。理由见 §1 末段，正文已按审计线改写。授权人：Core Maintainer。
      ② 2026-09-10 就地修订（Proposed 段）：删除悬空引用 `ADR-0023 §7`（该 ADR 无 §7）。授权人：Core Maintainer。
      ③ 2026-09-10 正交去重（Proposed 段）：P3 裁决签名/钉收钉细节改指 ADR-0025 §2.2/§2.3/§2.7，本 ADR 只留主权四章与审计线形状。授权人：Core Maintainer。
      ④ 2026-09-10 正交收尾（Proposed 段）：报告落盘与 ADR-0025 §2.7 对齐（k3dge 进程落盘 / Hall 只 join）。授权人：Core Maintainer。
      ⑤ 2026-09-10 经 Core Maintainer 本轮显式授权，改名/平移编号（重排前该文件占另一号 → 本号 ADR-0024，填空缺；全仓引用同步；按 ADR-0023 §2.3 不建旧号对照表）。依 `docs/adr/AUTHORING.md`。
      ⑥ 去 changelog 化（Context 只留约束：删「早期推演 / 重设计（两次收敛）」时间线）2026-09-10，经 Core Maintainer 本轮显式授权，依 `docs/adr/AUTHORING.md`。
      ⑦ 人读化改写（按 AUTHORING「人读优先」：决策先行、一行一点、长条拆子项；不变量与章节号不变）2026-09-10，经 Core Maintainer 本轮显式授权，依 `docs/adr/AUTHORING.md`。
      ⑧ §2.1 主权表按阶段拆分「审计意见 / 报告 join / 报告落盘」三行（消除与 ADR-0025 §2.7 的表面冲突：署名在窗、join 在 Hall、落盘在 k3dge，属不同阶段）2026-09-10，经 Core Maintainer 本轮显式授权，依 `docs/adr/AUTHORING.md`；过闸口径 = manual fallback（Core Maintainer 会话授权，agent 代改字，未经 k3dit 文审）。
      ⑨ D-2/D-3 独立文审回填 2026-09-10，经 Core Maintainer 本轮授权，依 `docs/adr/AUTHORING.md`：① Note 旧号改事件表述（消 `pointer_dangling`）；② 补独立文审证据——本轮就地修订（⑧ 及 §2.1 措辞）经 k3dit Doc Audit 透镜独立复核，报告 `docs/reviews/2026-09-10-doc-audit-docs.md`（首轮待修 7，修后复审至 0）；过闸口径 = real lens（独立 agent 执行，非自审）。
---

# ADR-0024: 审计证据交换拓扑（审计线 · 一单一条 · 树上钉 · 分支写回）

## 1. 上下文 (Context)

- 棘轮审计（一单=一快照、单内审↔修交替）确立后，证据如何在 k3dge / k3dit / 席位之间流动成为剩余分歧点。
- 约束：**同机同信任域**（`ADR-0006` S-13），审计不兼任监管——防伪件不成立；交换物须与主干同构，不自造对象格式（弃案见 §2.5）。
- 审计线（分支 + worktree）在消费仓 `.git` 里实现"一单一条线"的隔离；对象格式、树布局与主干天然一致，写回就是 ff 或重演。
- 独立库与打包器（sha256 库、`target/` 前缀、scrub 树、签名骨架、袋 create/resolve）不采用。交换物＝**一单一条线**。

## 2. 决策 (Decision)

### 2.1 主权四章（各归其一，无重叠）

| 物 | 主权 | 依据 |
| --- | --- | --- |
| 证据本体（分支 `k3dit/<单>` + worktree）与 GC | **k3dge**（消费仓）：线自锁点 L 拉起；闸过合主干后删现场删线（仅已并入时）；废单删分支——主干从未脏 | 被审物不迁主权；线是消费侧的物 |
| 工单（findings / 裁决史 / 状态机 / 报告） | **审计模块**：账本只存机构判断物 + 引用（baseline / branch / scope），不存一字节客户代码 | 数据最小化 |
| 阅件 | **席位**：submit 得 `{baseline, branch, wt_dir, scope}`；Hall 按 scope 拷窗，轮毕即清；席位/机构永不直接操作消费仓 `.git` | 处理≠归档 |
| 审计意见（findings/裁决） | **判读窗/复核窗**各自署名（窗钥签本窗收成）；窗产出即意见，Hall 不代笔 | ADR-0025 §2.2/§2.7 |
| 报告 join | **Hall 进程**把各窗署名收成机械合并成 12 列（账本⋈delta，不判断、不重打字） | ADR-0025 §2.7 |
| 报告落盘 | **k3dge 进程**机械放置 `docs/reviews/`（可复算、不产判断）；Hall 只 join/验签 | ADR-0006 §2.3.6 |

**裁决签名规则（P3）**：翻转与署名机制以 ADR-0025 §2.2/§2.3/§2.7 为准（章笔分离；修席只改物，人或席位署名）。

### 2.2 交换物：审计线（一单一条）

- **形状**：线＝分支 `k3dit/<单>`（自锁点 L 拉起，住消费仓 `.git`）＋ worktree 现场（`.k3dge/wt/<单>`）。
  - 送检＝锁线（`ensure`＋`advance`，脏改动进程代提交）；交件＝字符串句柄（baseline=L/branch/wt_dir/scope）；取件＝机构内部读现场。
  - 独立库、打包器、袋、sha256 特殊对象格式全部退役。
- **钉即交换介质**：判读/修/核在树上的钉上交换（语法与写源见 `peer_contract §8`、ADR-0025 §2.7）；JSON 只当签名信封，12 列从账本渲染。
- **隔离三层**：审计线 vs 主干（ref＋本地 exclude＋闸过删线）；窗 vs 窗（Hall 按 scope 拷窗＋CLI root/deny）；席位 vs 消费仓 `.git`（改动经 Hall 收回、进程 advance 提版）。
- **身份**＝最新线头 commit oid（主干血统、可复算、可 `git log`）。
  - submit 锁 L 只是首钉；Hall 每提版（advance）即重钉——报告按最新基线签。
  - 判读在旧 L 下的工作由复核窗覆盖；案内版本史＝线本身＋账本判读记录。
- **代价（承认）**：无包级脱敏——审计线是全树 checkout，secret 随现场直穿机构全程；送检范围退为 Hall 物化参数。同信任域可接受（§1）；跨信任域 ⇒ Reopen ①。

### 2.3 写回拓扑：线上最终版合入主干

- 主干只在 closure 时接收合并；合并默认自动执行，冲突即停并升级人工（P1）——机器搬运，人只在物理分歧处出现。
- 路径：先去钉（钉永不进主干：独占钉行删，行尾钉上报；去钉产物提版）→ ff 直达。
  - ff 不成 ⇒ 线 `(base..L′]` `rebase --onto` 重演到主干头再 ff（真 merge 已废：线提交全是机械件）。
  - 冲突 ⇒ abort 复原＋升级人工（§1.4）。
- 账本载"判"、分支载"物"：裁决权威在工单簿，分支不复制真相。
- 轮次分支 ref 住消费仓 `.git`（P2）。
- 废单＝删分支（主干从未脏）；崩溃恢复＝分支原位续走；过程留痕＝`git log k3dit/<job>`；闭环后删现场删线（仅已并入时）。

### 2.4 复用与校验

- 跨仓/跨单复用按 **oid × lens_version 匹配工单簿结论**——不需持有客户内容，与最小化自洽。
- 完整性链条：锁点 L 即基线（主干血统、可复算）＋ report `provenance.baseline` 与 L 的形式比对。
- k3dit 无内容，故不做内容验货。

### 2.5 非目标 (Non-goals)

- 不建 k3che 证据/CAS 角色（回归 token 经济）。
- 不做"镜像/备份"入协议（机构运维手段）。
- 不引入被审方防伪机制（信任域内，§1）。
- 不实现远程部署（服务发现/推拉鉴权等）。远近同形只是包时代的愿景，线时代远程即另题——到实施时另立 ADR，不在本条内预焊。

## 3. 产生后果 (Consequences)

- **Up**：线即送检即现场；无打包、无独立库、无双份磁盘、无特殊对象格式；对象格式与树布局同主干，合并是普通 git；消费侧只认"锁点 L"一个身份。
- **Down**：审计线全树 checkout——无包级脱敏，secret 直穿机构全程（同信任域接受）；范围裁剪退为 Hall 物化参数；非 git 消费仓无法审计（显式拒绝）。
- **Reopen when**：① 跨信任域部署成真（需封闭集/脱敏通道）；② 出现"多站并行"（同线多站读写同一时点）；③ 冲突升级后人工 rebase 频繁出错（再谈收紧自动合并）。
