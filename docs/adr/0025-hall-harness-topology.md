---
Status: Accepted
# Append-only after Accepted. Revise via `Amended by` / `Superseded by` below — do
# NOT rewrite this decision's prose in place, and never reuse a number (see README).
Supersedes: -
Amended-by: -
Landed-by: src/k3dge/engine/audit_flow.py
Date: 2026-09-05
Deciders: Core Maintainer
Note: ① 2026-09-05 授权就地修订（Proposed 段，会话四则裁决）：合并语义明确为「audit/quality 内容精细编排为一个模块（同屋檐、多窗多席）」；判断权威分离载体由「独立工件/独立发布轨」改定为「签名钥 + 席位隔离 + 章在人手」；W4 改中性保管表述。授权人：Core Maintainer。
      ② 2026-09-06 续修订（Proposed 段）：W6 活性墙；复核窗（验收+过程审计合并）；统计席位归进程侧；窗序固定（文档→代码→价值）；§2.6 Accepted 双门（G2+G3，席用原机制）；k3che 可调用；标题审计模块优先。授权人：Core Maintainer。
      ③ 2026-09-09 续修订（Proposed 段）：折叠本 ADR 早期拟稿入 §2.7（判读席只写钉、信封/签名/join 归进程、done＝包装器交收成、§8 钉语法 v2 随实现步落）；就地精化 §2.2 锚点②与 §2.3 章笔分离的措辞指向（签的物＝本窗钉的收成），独立性三载体与"席不自签"不变。授权人：Core Maintainer。
      ④ 2026-09-09 再修 §2.7 拓扑（Proposed 段，实现前对齐）：done 信号从"窗 root 内 `artifact.json` 由包装器写"改定为"**Hall 私有心跳 `done_path`（`{K3DIT_HALL_ROOT}/.run/{job}/{window}.done`，在 CLI 目录树外，防内层 edit=allow 伪造）**"；"包装器合成 items 写 artifact.json"划掉，改定**包装器只 touch 心跳、`step_judges` harvest 树并 `_apply_live` 只吃收成、忽略席产 JSON**；修/核窗本批不动；补"分批边界"（k3dit 侧 v2 先行、§8/markers/strip 留契约镜像批）。授权人：Core Maintainer。
      ⑤ 2026-09-10 §2.7 补修/核规程（Proposed 段）：修/核腿**废 `accepted` 二值**、改钉/树驱动——修席删 `pending` 标=改（§8 结案凭据）/翻 `leftover`/`disputed`；Hall 对 Hall 私域 `.orig` 原快照 `diff(窗src,.orig)` 逐条推 state（删标且 diff≠∅=`fixed`；删标但 diff=∅=FORMAT；未碰=`pending` 留 open 由复核打回）；复核按合线 advance diff retest；done=心跳；原快照 `{K3DIT_HALL_ROOT}/.run/{job}/{window}.orig`。授权人：Core Maintainer。
      ⑥ 2026-09-10 再修（Proposed 段）：W4 以 §2.7 心跳/原快照为准（Hall 调度状态可重放，运行现场在私域 `.run/`）；`sign-report` 署名口径＝人或席位（baseline 形式比对归 Hall 机械进程）；引用的早期拟稿 ADR 号改指自身。授权人：Core Maintainer。
      ⑦ 2026-09-10 正交去重（Proposed 段）：W3 降级格式改指 ADR-0006 §2.4；章笔分离去掉对 ADR-0025 P3 的循环引，本 ADR 为署名/收钉单源。授权人：Core Maintainer。
      ⑧ 2026-09-10 正交收尾（Proposed 段）：§2.7 补齐报告文件落盘主语（k3dge 进程落盘，Hall 只 join），与 ADR-0025 §2.9.1 对齐。授权人：Core Maintainer。
      ⑨ 2026-09-10 经 Core Maintainer 本轮显式授权，改名/平移编号（重排前该文件占另一号 → 本号 ADR-0025，填空缺；全仓引用同步）。依 `docs/adr/AUTHORING.md`。
      ⑩ 去 changelog 化（删「就地精化 / 划掉旧稿 / 反转旧 prompt / 双源划掉」等元叙述与「补定 date」）2026-09-10，经 Core Maintainer 本轮显式授权，依 `docs/adr/AUTHORING.md`。
       ⑪ 人读化改写（按 AUTHORING「人读优先」：决策先行、一行一点、长机制拆块；不变量与章节号不变）2026-09-10，经 Core Maintainer 本轮显式授权，依 `docs/adr/AUTHORING.md`。
       ⑫ §2.7 修/核钉生命周期更正（Proposed 段，覆盖 ⑤ 的"修席删标＝改"）2026-09-10，经 Core Maintainer 授权，依 `docs/adr/AUTHORING.md`：**删钉归复核**，修席只 `pending→fixnote`（主张，不删、不自证结案）；`fixed` 只由复核**删 `fixnote`** 产生（独立手）；复核输入＝账本 + 按 location 归的 present diff，不 grep 裸钉；`fixnote` 但 `.orig` diff=∅＝FORMAT（主张却未改码）。授权人：Core Maintainer。
       ⑬ §2.7 拔钉归 Hall（Proposed 段，覆盖 ⑫ 的"删钉归复核"）2026-09-10，经 Core Maintainer 授权，依 `docs/adr/AUTHORING.md`：**任何席不删钉**（席只增/翻，删除＝账本结论的机械后果归 Hall）；修席翻 `fixnote` 主张、复核**不认可翻回 `pending`、认可不动**（也不删）；**Hall 在复核收工时把仍是 `fixnote`（＝未被打回）的拔钉 ⇒ `fixed`**。`fixed`＝修主张(fixnote∧真码差) ∧ 复核未打回 ∧ Hall 拔 三合。授权人：Core Maintainer。
       ⑭ §2.7 复核须正向背书 + 结案前 verify 硬门（Proposed 段，覆盖 ⑬ 的"认可不动即 fixed"）2026-09-10，经 Core Maintainer 授权，依 `docs/adr/AUTHORING.md`：真跑坐实"沉默/正向背书都挡不住改坏测试"（M8 线 version.py 原子写改崩 test_bump_is_atomic）。改定：`fixed`＝**修主张(fixnote∧真码差) ∧ 复核正向背书(翻 `fixnote→fixed`，沉默＝未验不算) ∧ 结案前 Hall 跑被审仓自带 verify 命令绿 ∧ Hall 拔 `fixed`** 四合；新增 `fixed` 钉 kind（非 open）；verify 命令经 `k3dit_audit_submit(verify=…)` 由被审仓带入、Hall 只执行。授权人：Core Maintainer。
      ⑮ 正文按审计结论收紧（信任模型/W1 env 面/W6 签名/pin-only 对齐/verify 执行面/修订纪律/scope 面）2026-09-10，经 Core Maintainer 本轮显式授权，依 `docs/adr/AUTHORING.md`；过闸口径 = manual fallback（Core Maintainer 会话授权，agent 代改字，未经 k3dit 文审）。
      ⑯ D-1..D-3 独立文审回填 2026-09-10，经 Core Maintainer 本轮授权，依 `docs/adr/AUTHORING.md`：① §2.2/§2.3 旧生命周期措辞抹平到 §2.7（复核翻 `fixnote→fixed`、Hall 拔；消同篇自相抵）；② Note 旧号改事件表述（消 `pointer_dangling`）；③ 补独立文审证据——本轮就地修订经 k3dit Doc Audit 透镜独立复核，报告 `docs/reviews/2026-09-10-doc-audit-docs.md`（首轮待修 7，修后复审至 0）；过闸口径 = real lens（独立 agent 执行，非自审）。
      ⑰ 复核加硬（Proposed 段）2026-09-10，经 Core Maintainer 授权，依 `docs/adr/AUTHORING.md`：① 钉加可选尾段 `evidence=<可复跑命令>`，结案前 Hall 逐条 retest；② 复核输入补 `facts/verify.txt`/`tests.json`；③ `fixed` 理由须落到具体符号/调用点/测试名，纯复述 diff 判 FORMAT；④ 复核与修/判用**不同模型**（第二双眼睛）；⑤ verify/evidence 红改「`fixed` 回退 `pending` + 打回」，超 MAX_BOUNCE 才升级。过闸口径 = manual fallback（Core Maintainer 会话授权，agent 代改字）。
      ⑱ §2.7 处置/验证分写 + 盲对比（Proposed 段，覆盖同日"处置＝复核署名"试作）2026-09-10，经 Core Maintainer 授权：修席 `fixnote` note＝报告**处置**（对复核盲：物化 `_blind_fixnotes` 抹 note、`findings.json` 的 `how` 置空）；复核独立写 `fixed` note＝报告**验证**；Hall 并置两侧 `_text_overlap` 粗判（零交集仅公示不阻断）。过闸口径 = manual fallback（Core Maintainer 会话授权）。
      ⑲ §2.2 职责卡单一源（Proposed 段）2026-09-10，经 Core Maintainer 授权：窗职责/焦点/协议/样例＝入库 `src/k3dit/windows/<窗>.md`；Hall 写进窗 `README.md`+`facts/instruction.md`，`seat_prompt` 只指路（"先读职责卡"）不复述，消 prompt/instruction 双源（曾致 C1 提示与 harvest 不一致）。过闸口径 = manual fallback。
      ⑳ §2.7 两阶段复核 + 拔钉后移（Proposed 段）2026-09-10，经 Core Maintainer 授权：R1 盲写验证、**不拔钉**；新增 `compare` 相位，Hall 并置 `处置‖验证` 交**复核席**裁决（`复审:通过` 才通过，沉默/驳回⇒回退 `pending` 打回）；Hall 只封/并/识别标记，不判语义（`_text_overlap` 退役）；**拔钉移到 `_finish`（R2 通过 + verify 绿后）**——`fixed` 是终态，R1 拔早会让 R2 无对比对象、且把终态提前。过闸口径 = manual fallback。
      ㉑ 未尽项完结 + scope 含 docs（Proposed 段）2026-09-10，经 Core Maintainer 授权：① 反复打回/verify 连续红达 MAX_BOUNCE ⇒ 不再 kill；未关留 `pending`，出 `<!-- k3dge:incomplete -->` 报告、工单 `done` 供 collect——`待修>0` 自然过不了 k3dge `audit_closed`/封板 verify，与既有闸"合流"，人据 `[NEXT]` 授意 CLI agent 处理（如模板对只需 `k3dge sync`）。② 送检 scope 默认含 `src`+`docs`、**不含 `.agent` 等隐藏配置**（隐藏文件不进审计；无 docs 的文档审无意义）。过闸口径 = manual fallback。
      ㉒ 审计耗时统计（Proposed 段）2026-09-10，经 Core Maintainer 授权：进程侧记 `collect`/`compare`/`verify` 事件 `dur_s`（spawn→收成墙钟），`observe` 聚合逐窗/合计，报告附录同源——只出事实、不判定、不占判读窗（G8 观测的一部分；统计席位仍待后续）。
      ㉓ 统计席位（部分，Proposed 段）2026-09-10，经 Core Maintainer 授权：事件记座位 `tries`/成功 `model`；`observe` 汇总 counts/tries/models/`verify_fail`/`bounces`/耗时并出**观测行 `line`**；`job_status` 回带 `line`/`total_dur_s`/`tries`，`peer_status` 透传给 `k3dge audit status`。只出事实、不判定；逃逸/误诊口径与跨单汇总仍待定。
      ㉔ 统计口径 + 统计账（Proposed 段）2026-09-10，经 Core Maintainer 授权：k3dit 记 **append-only 统计账** `ledger/stats.jsonl`（每单终态一条：counts/findings/windows/tries/models/bounces/verify_fail/耗时/rounds）；口径（可数、不判定）＝误诊率 disputed/total、有意留率 leftover/total、打回率 bounces/rounds、座位重试率 Σtries/窗运行数、逃逸代理「重提率」见 `metrics.recurrence()`；`k3dit stats --by {milestone,job,date,type,severity,priority,state,window,model}` **任意维度聚合**（账是唯一源，报告/观测行是投影）。
      ㉕ 模型维度（Proposed 段）2026-09-10，经 Core Maintainer 授权：事件记**失败档链** `tried=["<model>: <why>", …]`；判读发现打**产出模型** `finding.model`、修/核记 `last_model`；`stats.jsonl` 的 findings 带 `model`；`k3dit stats --by model`＝发现级聚合；`--models` 出按模型度量（发现数/误诊率/有意留率/窗运行数/重试/耗时/失败档），供模型选型。只出事实、不判定。
      ㉖ verify 解耦（Proposed 段，覆盖 ⑭ 的"结案前 verify 硬门"与 ⑰ 的"verify 红回退打回"）2026-09-11，经 Core Maintainer 授权，依 `docs/adr/AUTHORING.md`：真跑坐实 Hall 侧 mechanical verify **越位**——审计线 worktree 缺 `.venv`/收据 ⇒ 环境假红；all-or-nothing 回退连坐已复核的 `fixed`；打回让席重做做过的事。改定：**审计侧不执行任何被审仓代码**——删结案前 `_verify_line`（仓级 verify + 逐条 evidence 执行）与 `_verify_failed` 打回；`fixed`＝**修主张(fixnote∧真码差) ∧ 复核正向背书 ∧ Hall 拔** 三合，语义＝**复核背书**（非"机械验证通过"）。机械闸归**消费侧落点**：k3dge 既有 pre-commit `check` + CI `k3dge check --with-tests`/`pytest`（环境正确、时机在落地）。`audit_closed`（审计完备）与机械绿（代码能跑）分家，`seal` 两者都要。钉尾 `evidence=<命令>` 退为**证据主张**（进报告、审计侧不执行，由消费侧 CI/落地统一跑）；`k3dit_audit_submit` 不再带 `verify`。过闸口径 = manual fallback（Core Maintainer 会话授权，agent 代改字）。
      ㉗ **合并原 ADR「审计证据交换拓扑」入本条 §2.9**（物理删旧文件，git 历史留档）2026-09-12，经 Core Maintainer 本轮显式授权，依 `docs/adr/AUTHORING.md`：审计线与 Hall 同属“审计模块拓扑”一决策；被并者 0024 删除，全仓指针改指本条（原 §2.1–§2.5 → §2.9.1–§2.9.5）。过闸口径 = manual fallback。
      ㉘ W1 第三方实证 + Reopen 反向条件 + PURPOSE 回指惯例 2026-09-13，经 Core Maintainer 授权，依 `docs/adr/AUTHORING.md`：① 引 WikiSkill（arXiv:2608.27454 Table 3）ablation——给执行席开放累积知识使准确率 63.7%→60.9%——为 W1（执行席只读当轮材料）的第三方依据；② §3 Reopen 补「若放开 W1 隔离（执行席可读累积知识/账本历史），须先复现并推翻该 ablation」；③ 立 **PURPOSE 回指**惯例＝重大透镜修订在 ADR Decision 写驱动它的 pattern（并入既有 ADR 惯例，不新增机制）。过闸口径 = manual fallback。
# Note: 非修订类元信息（过闸口径、历史痕迹摘要）。修订痕迹一律进 `Amended-by`
# （格式 `- 🅰<序号> | <授权席位> | <日期> | <简述>`）——见 docs/adr/AUTHORING.md。
# 本条上方 ①-㉘ 为旧格式存量（新格式自 ADR-0006 🅰1 起），迁移待专票，不就地改写。
      (40) 2026-09-12 转 `Accepted`：经 Core Maintainer 显式批准（M9 内容项「ADR 成事实源」），补 `Landed-by` 指针；过闸口径 = manual fallback。
---

# ADR-0025: 审计模块（audit+quality）——Hall 确定性编排 + 物理隔离子席位

## 1. 上下文 (Context)

- 三 harness（`ADR-0005`：k3dge / k3dit / k3lity）的审计与质量接口同构（submit / collect / bundle / 12 列报告 / ratchet），一分多带来形式冗余与双份维护面。
- 治理类比：**场地**（Hall＝大厅/政务中心）只组织周转、无审批权；**坐馆单位**（各窗口）持有权威。审计机构的内部监督天然自治，不因外部组织存在而成立。
- 信任前提：同机同信任域（`ADR-0006` S-13）、防伪不成立、Peer Contract §0 双盲与 §1.4 机器不自签仍需主体分离；被审物主权不迁（`ADR-0025` §2.1）。
- 合并的争议点：审计方若同时持有消费仓账本、盖封板章，审计即降格为自我声明——合并可行与否取决于"墙"能否从约定变成机制。
- 本 ADR 冻结拓扑、窗口划分与墙；每窗方法论细节与流转参数（队列优先级、回归面、度量口径）另行讨论（推演账见 `docs/memo/archive/2026-09-05-hall-pattern-discussion.md`）。

## 2. 决策 (Decision)

### 2.1 模型：审计模块含 Hall 子概念

- **Hall = 单一确定性调度进程**：叫号（闭包计数）→ 物化（按角色裁剪作用域落目录）→ 收集 → 验签 → 推进 → 通告牌（降级公示）。
- Hall**无内容判决权**：不判代码对不对、设计值不值。
- Hall 只持程序/一致性判定：账本可复算、隔离可测、降级可见、check 的声明↔实际，以及 Hall 规则典。
- 内容判断权威全部落在窗口（席位），各司其职、各自独立授权。
- Hall 部署在物理哪一侧是部署细节；不变量在数据保管与写权（§2.3 W3/W4）。

### 2.2 窗口 = 合并后审计模块的职责单元

- 合并＝把 audit/quality 的内容**精细编排为一个模块**（同屋檐、多窗多席），不是两套东西塞进一个目录。
- 基本责任单元是**窗口**：签名钥、scope、方法论全部落窗口级。
- 方法论正文可同源（如 audit-method.md）；独立的是判断权，不是文本。
- **职责卡单一源**：每窗职责/焦点/协议(落/翻钉)/好坏事例/边界＝入库文件 `src/k3dit/windows/<窗>.md`；Hall 物化时写进窗 `README.md` 并落 `facts/instruction.md`，席 prompt 只**指向它**（"先读职责卡"）不复述——消 prompt/instruction 双源漂移。
- k3dit / k3lity 作为历史来源消失，能力资产按窗口重分，旧名不再作为模块内划分依据。
- **分离锚点**（独立性的全部载体，缺一即角色扮演）：① W1 目录墙；② 各判读窗签名钥互不相同；③ W5 章在人手。
- 独立性不依赖独立工件或独立发布轨（一个模块同一构建可签多产物），但三载体必须真实存在且可测。
- **信任模型**：Hall 是受信确定性进程（同机同信任域，§1）。窗钥＝**归因/封签**（哪窗产出什么、可追溯），不是对 Hall 的防伪——Hall 持钥可代签，故②是职责与署名分离，不指密码学独立（防伪件不成立）。
- 窗口分两族：**判读窗群**（有签名钥、独立方法论）与**行动窗**（无签名钥，只执行改造）。
- **判读窗群**（独立钥，各自判读）：
  - 代码审计窗：健壮性、并发红旗、错误路径、RCA 根因复查；含反例/边界击穿方法选项。
  - 文档审计窗：文本质量、悬挂指针、类规约、doc-audit。
  - 价值窗：复杂度、重复、过重设计、更简做法（k3lity 可数判据的判断侧）。
  - 复核窗：对照声明查实际；对照面＝findings 验收（Retest 独立）＋流程合规（SQA，审计原义）；验收发现的新问题回执路由，不由复核窗裁决。
- 契约/分诊不入窗：契约一致性＝check 的声明↔实际，属 Hall 规则典；分诊/语义路由＝物化阶段参数。两者都不占判读窗。
- **修席窗 = 行动窗**：Hall 只组织窗口、不亲自干活；修席窗「改码 + 翻 `fixnote`（主张）/`leftover`/`disputed`，不删钉」（`fixed` 由复核把 `fixnote` 正向翻成、Hall 机械拔），唯有它持有 repo 写权，永不签名。收钉细则见 §2.7。
- 窗与窗隔离＝物理层（进程 + 目录）＋ CLI 原生访问控制：root 专属目录、权限 deny-by-default（根外与邻窗拒绝、无审批路径）、env 清洗（仅本窗签名钥 + 配置摘要）。
- 墙的最终归属是 Hall：spawn 时必须校验 root 与权限配置，CLI 只是放大器。
- **物化裁剪**：Hall 决定什么内容落进哪个目录（只读送检包 / 只读包+清单 / 可写 scratch / 修席窗唯一 repo 写权）；数据最小化的表面在物化。
- 三件事不混：确定性管流程（调度/物化/闭包/归档）；自由裁量管判断（窗口输出天然不确定）；规则管行为边界（范围/能力/程序固定、裁量留痕、窗口权威有界）。
- **窗序固定**：判读（文档→代码→价值）→ 修席（行动）→ 复核（验收+流程）→ 闭包 → seal。
- 打回只回退到修席；不跳窗、不插队、不动态重排。判读三窗可实现层并行，收集/推进按固定序。

### 2.3 不变量（墙，机制化、可测）

- **W1 ctx 隔离**：跨窗口泄露＝Hall 失职。
  - 窗口 root 专属目录、权限 deny-by-default（根外与邻窗拒绝、无审批路径）。
  - Hall spawn 时校验 root + 权限配置。
  - **env 面**：送检物是 git 树，本身不含 env/secret 状态；"env 清洗"只针对 **Hall 交给席位进程的宿主环境**——不继承全量宿主 env，仅白名单 + 本窗 `env` 文件（`HALL_*`、钥路径）。不是对审计线内容脱敏（线是全树 checkout，ADR-0025 §2.9.2 已承认）。
  - 测试：窗内 Read / Grep 根外与邻窗 → 断言拒绝；席进程 env 不含账本/无关密钥。
- **W2 轮间清场**：每轮结束销毁 / 轮换目录，防残留。
- **W3 降级可见**：任一窗口不可达 → `WARN[DOWNGRADE]` 上抛消费仓（四落点见 ADR-0006 §2.4）；禁止 Hall 内自愈掩盖。
- **W4 账本主权**：Hall 保管账本原件（findings/rounds/计数，程序可复算）。
  - 被审仓快照原件与归档主权在消费仓侧；归档经消费仓侧 shim 镜像（ADR-0025 主权四章不破）。保管诚实是程序不是判断。
  - 调度状态由账本重放重建；运行现场（心跳/原快照）在 Hall 私域 `.run/`（§2.7）。
  - Hall 崩溃重启后必须回到同一调度位置；kill -9 演练是 G2 验收项。
- **W5 闭包计数**：计数器任何席位不可读/不可写；接受权＝人（章在人手，非任何席位角色）。
  - rounds/findings 账本复核窗只读、禁写。
- **W6 活性（空转熔断）**：每个窗口 spawn 必须带三重预算——轮数 / token / 无进展次数。
  - 无进展＝`(动作签名, 结果签名)` 连续 N 次全等；N 默认 3。
  - 动作签名＝本窗**收成 delta**：判读窗＝树上钉集合 `(id, kind)`；修/核窗＝账本逐条 `(id, 迁移态)` 集合。
  - 结果签名＝收成规模 + 形检结果（items/actions 计数、FORMAT|ok）。pin-only 后无命令流/`verdict`，签名取自 Hall 收成，不取席自述。
  - 计数者是**Hall（进程侧）**，不是席位自我观察——上下文压缩后看不见前 N 轮。
  - 触发 ⇒ 停机 + `WARN[DOWNGRADE]` + 输出已试签名清单（先落账本再 W2 销毁）⇒ 按 escalated 先例转人工；窗口永不自判"再试一次"。
  - 推广路径：宿主 hooks 记 tool-call 流水 / Hall 看门狗；check 红×2 与 seal verify >3 是 commit 侧与 seal 侧先例。
- **章笔分离**：判读窗群签各自发现；复核窗签验收/流程结论；修席窗永不签名（机制见 §2.7）。
- **复核独立**：复核窗把 `fixnote` 正向翻 `fixed`（逐条验收 + 流程合规核对），Hall 随后机械拔；判读窗不自提自验。
  - 不通过 ⇒ 打回修复、`fixnote` 续记、闭包不闭合。
  - 复核发现的新问题回执路由，不由复核窗裁决。
- **seal 仅 Hall 门槛**：闭包计数由 Hall 且仅为 Hall；计数闭合才到 seal；接受权＝人（维护者），任何窗口碰不到 seal。

### 2.4 合并边界与行业对标底线（并什么 / 不并什么 / 什么不能丢）

- **并**：Hall（编排 + 调度 + 隔断 + 通告牌 + 叫号）与审计模块（重新编排的 audit+quality，接口＝原 audit；Hall 为其子概念）。
- **k3che 不并入**：保持独立 peer（记忆/检索），与审计模块分界清晰（记忆该不该出现 vs 代码对不对）；记忆侧不参与判断，审计模块可照常消费其检索。
- **不并**：判读窗群互相之间的权威——各窗独立签名钥 + 独立席位隔离（§2.2 分离锚点）。
  - "假装两个局"即自审塌缩，"假装六个局"同理。
  - 工件与发布轨可共享（同模块多产物）；锚点在三载体，不在工件数。
- **统计席位（程序控制+收尾度量+回归测试）归进程侧**：Hall 确定性程序控制 + 观测，不占判读窗、无签名钥。
  - 送检快照之外的数据走读裁剪；观测只出事实、不判定（先例：k3che 观测行、k3dge status）。
- **行业对标三列对账**：拟引入的外部标准要素先查对应 k3dge 既有机制，落「保留 / 优化 / 新增」三列；已有设计只能被优化、不可丢失。
  - 三条不可丢基准：一单一条审计线＋主权四章（ADR-0025）；12 列报告 + provenance/baseline；双盲 + 机器不自签 + 审计钉棘轮。
- **补缺增量**（三方均缺）：修席队列优先级（严重度×优先级）、回归面选择（blast radius）。
  - 度量回灌（误诊率/泄漏率/窗口漂移，观测不判定）、反例/边界击穿；全挂"Hall 确定性程序控制 + 代码审计窗方法"名下。
- 单席角色扮演被禁：任何角色必须有独立窗口与独立授权。

### 2.5 非目标 (Non-goals)

- 不定流转参数（修复队列优先级启发式、回归面规则、度量口径），仍下一步讨论；本 ADR 冻结拓扑、窗口划分与墙。
- 例外：判读席写面与窗工件合成已定于 §2.7。
- 不跨信任域部署；不引入被审方防伪机制（ADR-0025 §2.9.5 保持）。

### 2.6 转 Accepted 门槛

- Proposed 期间文审照常（措辞、拓扑、墙的定义可审可改）。
- 转 Accepted 必须叠加**实现背书**：
  - G2：人肉窗全链跑通（含打回一次、kill -9 重启位置一致、单均成本基线落盘）。
  - G3：墙跑通（W1 目录墙 + 钥验签；席用原 seats 机制经配置自动起，G3 只加墙）。
- 事实源描述的必须是已落地的现实；W2/W6（G5）与测试骨架（G7）在 Accepted 后、G6 前完成。
- G6 割接（k3lity 归档，不可逆）必须在 Accepted 之后。
- **修订纪律**：任何**改变行为**的就地修订，若对应实现已落地，必须**同任务**改代码/测试并 `k3dge sync` 回写契约——不许只改正文、留下代码按旧版跑（设计债不得转成静默实现债）。

### 2.7 判读席写面与窗工件合成

判读席只写钉，账本/报告由进程从钉合成。独立性三载体（目录墙 / 各窗钥互异 / 章在人手）与"席不自签"不变——窗钥签的是"本窗树上钉的收成"。

**写面**
- 判读席只在窗 src 独占行写结构化钉，不产 `artifact.json` 的 `items`。
- 判读四格（严重度/优先级/类型/问题描述）写源＝钉；账本、报告＝钉的投影（每轮重生成，从不手填）。
- 多行块 / note-file 第二写口明确否。

**钉语法 v2**
- 形状：`k3dit:pending <ID>[@<scope>] sev=<高|中|低> prio=<P0|P1|P2|P3> type=<枚举> <desc>`。
- 属性段闭集、顺序固定；其后至行尾＝`desc`（`desc` 内不得再含 `sev=`）。
- `leftover` / `disputed` / `fixnote` 可省略属性段。
- 语法权威＝`peer_contract §8`；v2 三处镜像随实现步落地（见 §3）。

**note 上限与 strip**
- `pending` note 上限 500（硬顶），>500 拆两条钉；strip 在 ff 回主干前删净 pending。
- `leftover` 维持 ≤80，且 strip 放过 leftover（§8「leftover 例外随文件走」）。
- `peer_contract §3③` 待改「除 leftover 外永不进主干」。
- 落点：`markers.py` 超限检查、`worktree.strip_pins` 按 kind 分支。

**枚举单一源**
- 权威表＝k3dit `rounds.py`（`TYPES/SEVERITIES/PRIORITIES`）；`audit-method.md` / §8 / 12 列 / `markers --check` 全镜像。
- 并表必须先于钉语法落地；现 `TYPES` 缺席实吐 {设计,悬空指针,正确性,结构}，闸一上即 FORMAT。

**验收闸**
- 删旧 `items × 钉` 交叉。
- 新闸＝`step_judges` harvest 时 + `markers --check`：钉 ID 必 ∈ claim 时 k3dit 发的号段（A/F 段），`sev/prio/type` 必 ∈ 单一源枚举；否则该窗 FORMAT。
- 本批先做 harvest 拒收；号段/枚举硬闸留 step5。

**收钉（判读）**
- 包装器不 harvest、不写 items。
- 内容源＝树：`step_judges` 见心跳 → `harvest_pins(window/src)` → 按 id 去重合成 `items`。
- `_apply_live` 只吃这份 harvest、忽略席产 JSON；窗钥签这份收成。

**收钉（修/核）——席只增/翻，拔钉归 Hall**
- 钉/树驱动，不设 `accepted` 二值；**任何席都不删钉**——删除＝账本结论的机械后果，归 Hall；席删＝自证 + 毁锚。
- 修席（行动窗，不签）逐条：**接受并改＝改码 + 翻 `pending→fixnote`（note=改法）**（主张"这条改了、待独立验"，仍 open、不结案）；有意留＝翻 `pending→leftover`（how）；误报＝翻 `pending→disputed`（how）；不碰＝留 `pending`。不产 items、不删钉。
- 复核窗（独立钥）：**输入＝账本（findings 行）+ `facts/present.md`（`.orig→现线` 代码 diff）+ `facts/tests.json`（相关测试）**——没这份料，"独立 retest"就是空话（真跑坐实：复核窗只有"已修"声明、零可核材料 → 只能信或瞎翻）。逐条判真伪——**认可＝翻 `fixnote→fixed` 且给具体依据（符号/调用点/测试名 + 反证尝试；纯复述 diff 或空理由＝该窗 FORMAT）、不认可＝翻 `fixnote→pending`（打回，受 MAX_BOUNCE）**。**沉默（留 fixnote）＝未验 ⇒ 不算通过**。复核**不删钉**（删除归 Hall）。复核与修/判用**不同模型**（第二双眼睛）。
- **处置/验证＝两窗署名 + 盲对比（两阶段复核）**：修席 `fixnote` note＝报告 `处置`（改了什么/为什么）；R1 复核**看不到它**（物化抹 note、`how` 置空），独立写 `fixed` note＝报告 `验证`。**R2** Hall 才把 `处置‖验证` 并置（`compare.md`）交**复核席**裁决：一致 ⇒ 追写 `复审:通过`；不一致 ⇒ 翻 `pending` 打回；沉默＝未裁。Hall 只**封/并/识别标记**，不判语义（`_text_overlap` 退役）。
- **拔钉在 R2 通过之后**（`_finish`），不在 R1：`fixed` 是终态，R1 拔早会让 R2 无对比对象。

> 正向背书治"不碰"，present diff 治"没料查"，`fixed` 必须带 diff 指向理由治"碰了但没看"——三层缺一仍是橡皮章。代码"改坏测试"由**消费侧落点/CI** 兜底（Note ㉖），不在审计侧；审计只判"改得对不对"。

**机械闸不在审计侧（verify 解耦，Note ㉖）**
- 审计侧**不执行任何被审仓代码**（原"结案前 Hall 跑 verify/evidence"已删）：`fixed` 语义＝**复核背书**（改得对不对），非"机械验证通过"。
- 钉尾 `evidence=<命令>` 退为**证据主张**（进报告「验证」栏兜底），审计侧不跑。
- 代码能不能跑/过闸归**消费侧落点**：k3dge pre-commit `check` + CI `pytest`/`check --with-tests`（环境正确、时机在落地）。`audit_closed`（审计完备）与机械绿分家，`seal` 两者都要。
- **未尽项完结（不升级的出口）**：反复打回达 MAX_BOUNCE ⇒ **不 kill**；未关条目留 `pending`，出报告（`<!-- k3dge:incomplete -->` + 未尽项清单 + 人工旗）、工单 `done` 供 k3dge collect——`待修>0` ⇒ 不闭环、封板照堵。人据 `[NEXT]` 授意 CLI agent 处理（如"模板对只需 `k3dge sync`"）。判据机械＝达 MAX_BOUNCE；用于"硬限制（scope 外/隐藏文件对）修不全"这类。

**state 推导（Hall，含机械拔钉）**
- 判读后：见心跳 → `harvest_pins(窗 src)`，逐条 `pending` 钉收成 items。
- 修后：见心跳 → diff(窗 src, 原快照) + 读钉变迁，逐条推——
  - `pending→fixnote` 且目标文件 diff≠∅ ⇒ **`fixnote`（proposed-fixed，仍 open 待复核）**；
  - 翻成 `fixnote` 但目标文件 diff=∅ ⇒ 该窗 FORMAT（主张改了却没动码＝谎报）；
  - 翻 leftover/disputed ⇒ 对应态；未碰仍 pending ⇒ 留 open。
- 核后（**Hall 机械拔钉**）：复核把认可项翻成 `fixed` 钉 → **Hall 把 `fixed` 钉拔除、账本置 `fixed`**；仍留 `fixnote`（复核未背书）＝未验 ⇒ 保持 open、闭不了案；被翻回 `pending` ⇒ 打回。
- **不变量**：钉集合＝账本状态的投影；`fixed`＝**修主张(fixnote ∧ 真码差) ∧ 复核正向背书(fixnote→fixed) ∧ Hall 拔钉** 三合（机械闸在消费侧，Note ㉖）；席不得凭删标记或沉默毁证据/自证结案，删除动作全程只在 Hall。
- 物化时在 Hall 私域存只读原快照 `{K3DIT_HALL_ROOT}/.run/{job}/{window}.orig`（窗 root 外）；不给窗塞 `.git`。present diff 由 Hall 按 finding location 归到每条注入复核窗（"判断只读账本"，diff 作物证由进程供给）。

**done 信号**
- 等的是 `launch()` 返回的 `done_path`：`{K3DIT_HALL_ROOT}/.run/{job}/{window}.done`，不在 CLI `--dir`/`--cwd` 树内（防内层 `edit=allow` 伪造）。
- 包装器仅内层干净退出后 `touch`；非零/超时/被杀不写。
- 判定：干净退出 + 心跳 → 窗完（判读零钉＝合法空判；修/核据 diff，未碰留 open）；非零/超时/无心跳 → 升级，禁收成空判。
- 席 prompt、窗目录列表、instruction 不得出现 `.done` / `.orig` / `artifact.json`。

**非目标（不动）**
- §2 collect 信封四字段（`provenance.seat`＝Hall 汇总窗名；baseline＝线头）。
- 窗 ed25519 仍＝Hall 对"本窗收成"的章，不迁 git author；`advance` 仍 `k3dge-process` 机械 commit。
- 结项 12 列仍 §1.4 `audit-report` join（baseline 比对由 Hall 机械执行）→ `sign-report` 人或席位署名、机器不自签。
- 报告文件落盘归 k3dge 进程（`docs/reviews/`，ADR-0025 §2.9.1）；Hall 只 join/验签，不写消费仓。
- **窗收成 scope 面**：Hall 只收窗内 `@line` 钉（`@file` 头部块同语法可收）；`@repo`/`AUDIT.md` 侧车条目不进 Hall 流程——多文件发现由 k3dge 侧 `markers` 与报告承载，窗 scope 语义与执行面此不等价（另立任务前不预焊）。
- §4 findings 产出方＝合并审计模块内各窗（quality 已并入，无独立腿）；ADR-0012 不引用于此。

**Hall 依赖**
- 物化时留只读原快照（修/核用；修席窗无 `.git`）；不得为 diff 给窗塞 `.git`。

### 2.8 窗×透镜对口与类型/严重度域（规范；代码为可执行镜像）

> 这是**决策级规范**：窗分域、各窗类型域、严重度带在此定。可执行镜像＝`mcp._PASS_FOCUS`（透镜焦点）、`hall.JUDGE_TYPE_DOMAIN`（类型域）、`rounds.TYPE_SEV_CAP/TYPE_PRIO_CAP`（严重度/优先级带）、`rounds.TYPES/SEVERITIES/PRIORITIES`（枚举单一源）——改本表须同步代码（结构律、规则 10）。判断**方法散文**在 `k3dit/docs/guides/audit-method.md`（输出型指南，不称事实源）。

| 窗 | 对口透镜/节 | 类型域（越域 harvest 拒） | 严重度带（按 type 夹回上限） | 工具面输入（确定性事实，席不重算） |
| --- | --- | --- | --- | --- |
| 文档审计窗 | Doc Audit：ADR 冲突/覆盖/正交 + authoring 软合规 | 规范·冲突·覆盖·悬空指针·设计 | 规范≤低/P3 | `k3dge_adr_index` |
| 代码审计窗 | Pass 1-4 + 安全/正确性深审 + 性能8族 + 反例/边界 | 安全·正确性·缺陷·竞态·破坏性·隐蔽·冲突·覆盖 | 无上限（真阻断） | diff/trace 指针、数据流/污点、锁图 |
| 价值窗 | code-judo / Approval Bar / 结构红旗（判"该不该阻断"） | 复杂度·结构·冗余·性能·设计 | 复杂度·结构·冗余·性能≤中/P2 | k3lity scan_facts（CC/行数/重复度） |
| 修席窗（行动窗，非透镜） | 无（改码 + 翻 `fixnote`/`leftover`/`disputed`；见 §2.7） | — | — | 待关 findings + 窗内 `pending` 钉 + `.orig` |
| 复核窗（独立钥） | Retest：看 `present.md`（修席 `.orig→现` diff）+ conformance/LTL | — | — | findings 账本 + present diff |

价值窗独立于代码窗：前者审"设计值不值"（含工具预计算事实）、后者审"这段贵不贵/对不对"（diff 内），对照面不同、不共钥。

### 2.9 审计线与证据交换拓扑（原独立 ADR，合并入本条）

> 线是审计的物，Hall 在上面调度；原「审计证据交换拓扑」与本条同属"审计模块拓扑"一决策，故作一。以下 §2.9.1–§2.9.5 即原条 §2.1–§2.5。

#### 2.9.1 主权四章（各归其一，无重叠）

| 物 | 主权 | 依据 |
| --- | --- | --- |
| 证据本体（分支 `k3dit/<单>` + worktree）与 GC | **k3dge**（消费仓）：线自锁点 L 拉起；闸过合主干后删现场删线（仅已并入时）；废单删分支——主干从未脏 | 被审物不迁主权；线是消费侧的物 |
| 工单（findings / 裁决史 / 状态机 / 报告） | **审计模块**：账本只存机构判断物 + 引用（baseline / branch / scope），不存一字节客户代码 | 数据最小化 |
| 阅件 | **席位**：submit 得 `{baseline, branch, wt_dir, scope}`；Hall 按 scope 拷窗，轮毕即清；席位/机构永不直接操作消费仓 `.git` | 处理≠归档 |
| 审计意见（findings/裁决） | **判读窗/复核窗**各自署名（窗钥签本窗收成）；窗产出即意见，Hall 不代笔 | §2.2/§2.7 |
| 报告 join | **Hall 进程**把各窗署名收成机械合并成 12 列（账本⋈delta，不判断、不重打字） | §2.7 |
| 报告落盘 | **k3dge 进程**机械放置 `docs/reviews/`（可复算、不产判断）；Hall 只 join/验签 | ADR-0006 §2.3.6 |

**裁决签名规则（P3）**：翻转与署名机制以 §2.2/§2.3/§2.7 为准（章笔分离；修席只改物，人或席位署名）。

#### 2.9.2 交换物：审计线（一单一条）

- **形状**：线＝分支 `k3dit/<单>`（自锁点 L 拉起，住消费仓 `.git`）＋ worktree 现场（`.k3dge/wt/<单>`）。
  - 送检＝锁线（`ensure`＋`advance`，脏改动进程代提交）；交件＝字符串句柄（baseline=L/branch/wt_dir/scope）；取件＝机构内部读现场。
  - 独立库、打包器、袋、sha256 特殊对象格式全部退役。
- **钉即交换介质**：判读/修/核在树上的钉上交换（语法与写源见 `peer_contract §8`、§2.7）；JSON 只当签名信封，12 列从账本渲染。
- **隔离三层**：审计线 vs 主干（ref＋本地 exclude＋闸过删线）；窗 vs 窗（Hall 按 scope 拷窗＋CLI root/deny）；席位 vs 消费仓 `.git`（改动经 Hall 收回、进程 advance 提版）。
- **身份**＝最新线头 commit oid（主干血统、可复算、可 `git log`）。
  - submit 锁 L 只是首钉；Hall 每提版（advance）即重钉——报告按最新基线签。
  - 判读在旧 L 下的工作由复核窗覆盖；案内版本史＝线本身＋账本判读记录。
- **代价（承认）**：无包级脱敏——审计线是全树 checkout，secret 随现场直穿机构全程；送检范围退为 Hall 物化参数。同信任域可接受（§1）；跨信任域 ⇒ Reopen ①。

#### 2.9.3 写回拓扑：线上最终版合入主干

- 主干只在 closure 时接收合并；合并默认自动执行，冲突即停并升级人工（P1）——机器搬运，人只在物理分歧处出现。
- 路径：先去钉（钉永不进主干：独占钉行删，行尾钉上报；去钉产物提版）→ ff 直达。
  - ff 不成 ⇒ 线 `(base..L′]` `rebase --onto` 重演到主干头再 ff（真 merge 已废：线提交全是机械件）。
  - 冲突 ⇒ abort 复原＋升级人工（§1.4）。
- 账本载"判"、分支载"物"：裁决权威在工单簿，分支不复制真相。
- 轮次分支 ref 住消费仓 `.git`（P2）。
- 废单＝删分支（主干从未脏）；崩溃恢复＝分支原位续走；过程留痕＝`git log k3dit/<job>`；闭环后删现场删线（仅已并入时）。

#### 2.9.4 复用与校验

- 跨仓/跨单复用按 **oid × lens_version 匹配工单簿结论**——不需持有客户内容，与最小化自洽。
- 完整性链条：锁点 L 即基线（主干血统、可复算）＋ report `provenance.baseline` 与 L 的形式比对。
- k3dit 无内容，故不做内容验货。

#### 2.9.5 非目标 (Non-goals)

- 不建 k3che 证据/CAS 角色（回归 token 经济）。
- 不做"镜像/备份"入协议（机构运维手段）。
- 不引入被审方防伪机制（信任域内，§1）。
- 不实现远程部署（服务发现/推拉鉴权等）。远近同形只是包时代的愿景，线时代远程即另题——到实施时另立 ADR，不在本条内预焊。

## 3. 产生后果 (Consequences)

- **Up**：形式冗余消除（少一套 harness 面 / 接口 / 运输）；判断权威不因合并降级；墙从约定变机制（进程 + 目录 + CLI 原生隔离可测）。
  - "部署在哪侧"变部署细节；修复通用化 + 验收独立，消除"打回作者"人格化残余；行业对标有"保留/优化/新增"底线护栏。
- **Down**：同二进制共存失效相关性（Hall 崩＝多目全黑，本地信任域接受）；窗口同机，靠目录 + 物化裁剪兜底；一个模块多把签名钥的签发/轮换运维成本。
- **Reopen when**：
  - ① 跨信任域部署成真（墙需升级为防伪）；② W1/W2 测试抓到越墙事故。
  - ③ Hall 单进程承载不足（多进程 Hall / 分 Hall）；④ 窗口划分与判断类型/对象不再咬合（窗口增删走新 ADR）。
- **分批边界（判读收钉批 vs 契约镜像批）**：
  - 先落 k3dit 侧：`rounds.TYPES` 并表、`pins._PIN_RE` 解析 v2、`step_judges` 心跳收钉、`seats.launch→seatwrap`。
  - 该批只回写 k3dit spec 契约哈希（`insert_pin`/`harvest` 属公开签名）；`hall deposit` 对判读窗 `items` 拒收 FORMAT。
  - 此批不动 `peer_contract §8` / `k3dge markers.py` / `worktree.strip_pins`。
  - 契约 v2 三处镜像 + `§3②③` 措辞留同一后续批，与 G2/G3 背书一起 `k3dge sync`。

## 4. 相关

- `docs/memo/archive/2026-09-05-hall-pattern-discussion.md`（推演账与废案表）
- `docs/memo/archive/2026-09-05-industry-benchmark-vs-4-harness.md`（四缺项归属 §3.1–§3.2；观测 G8）
- `docs/memo/archive/2026-09-05-graph-lens-for-audit-and-qa.md`（§6 窗路由表、§7 理论编排）
- §2.7（判读席写面/窗工件合成）折叠自本 ADR 早期拟稿（未单列）；其触发的 `peer_contract §8` v2 钉语法随实现步落（本 ADR 定稿不提前改活契约）。
- 落地链（M8）：G3b CLI 探测 → G1 合并 → G2 内核 + G3 墙（Accepted 双门）→ G5 看门狗 + G7 测试（墙完整验收）→ G6 割接 → G8 观测（各见 `docs/tasks/archive/M8/2026-09-06-M8-feat-hall_G*.done.md`；另一票 `2026-09-10-M8-feat-hall_harvest_repo_scope.md` 在 `docs/tasks/archive/M9/`）
