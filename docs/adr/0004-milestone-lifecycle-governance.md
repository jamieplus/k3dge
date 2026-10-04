---
Status: Accepted
Supersedes: -
Amended-by:
  - 🅰1 | Core Maintainer | 2026-09-20 | 审计＝封版主体：唯一入口 `seal`（预审 align → 审计 → 审核后自动化）；版号由**审计正常返回**推进；边界＝审计基线（`tag <M> = <B>`），基线之后归下一里程碑；报告降级为可选产物；完成记录＝封版提交 trailer；运行态与 durable 分层；CHANGELOG 由提交区间生成
  - 🅰2 | Core Maintainer | 2026-09-20 | `degraded-manual` 的定义扩到「**manual 传输**（不论它在链里是不是首选）」——判"有没有独立透镜"（事实），不判"相对预期链的位置"
  - 🅰3 | Core Maintainer | 2026-09-21 | 相位 3 先刷**纯投影**、不跑整条 `sync`（事实源写归审前）；派生件新鲜度归闸（`DOC_INDEX_STALE`/`DOCS_GENERATED_STALE`/`SYMBOL_INDEX_STALE`/`EXTRACTOR_PLUGIN_STALE`）+ `k3dge where` 自愈
  - 🅰4 | Core Maintainer | 2026-10-03 | §2.1.14 审计确认硬闸（人主观）与封板增量：seal/audit 解耦；未确认提醒三出路；确认绑定基线；增量排除审计自身+引用封版 hash 的提交；启动必终态
Landed-by: src/k3dge/engine/seal_flow.py
Date: 2026-08-23
Deciders: Core Maintainer
Note: 修订痕迹见 git 历史。
---

# ADR-0004: 里程碑生命周期治理（Milestone Lifecycle Governance）

## 1. 上下文 (Context)
`k3dge` 初始设计覆盖微观门禁（`k3dge check` 的 L0/L1 结构与契约校验）。随着
项目进入多阶段交付，出现两类新需求：(1) 按里程碑验收目标是否达成；(2) 防止
长周期开发下 `docs/tasks/` 上下文膨胀导致 Agent 注意力衰减。需一套轻量、
确定性的里程碑状态机与物理归档机制。

## 2. 决策 (Decision)

### 2.1 目标对齐优先、拒绝常规大重构
采用四步里程碑治理：`规划与开发 → 目标对齐与验收 (k3dge milestone align) →
按需重构（准入清单卡控）→ 上下文压缩封板 (k3dge milestone seal)`。

* **重构准入**：仅当命中 `C1 扩展硬阻塞 / C2 坏味道严重超标 / C3 契约漂移未愈`
  时才允许定向微调；否则严禁大重构。

### 2.1.1 门禁分层（Micro / Macro）
* **Micro Gate**（日常提交）：`k3dge check`；L0/L1 定义见 ADR-0001 §2.2。`--with-tests` 是 **selective L2**（只跑 git 触及域），不是 Full Matrix。
* **Macro Gate**（里程碑对齐）：`k3dge milestone align` 对 `manifest.domains` 做 **Full Matrix** 全域结构 + 契约 + 矩阵测试。

### 2.1.2 触发（Agent，无需用户提醒）
- 某 `Milestone` 下 `docs/tasks/` 顶层条目全部 `Status: done` → 当轮 `k3dge milestone align <id>`（Full Matrix，无人问）。[^🅰1.1]
- align 通过不等于可封：下一步是建议审计（§2.1.4），不是建议封板。

### 2.1.3 封板闸机
- 机器闸（reviews 文件）：含 `align-pass`、不含 `align-stub`、正文列出该里程碑全部任务、`docs/guides/` 无 `guide-stub`。
- 资格闸：由 `audit_trigger.audit_closed` 判（审计闭环、`待修=0`，§2.1.4/§2.1.7）；未闭环时 `seal` 返回 `audit_needed`。[^🅰1.2]
- 不读 `docs/reviews/SUMMARY.md`（禁止手维护类型索引，ADR-0018）；有意留只在 `docs/reviews/LEFTOVERS.md`。

### 2.1.4 两问拆分：审计是界限，封板只是收摊
> **🅰1 起**：本节的「两问」形态由 **§2.1.9（一次声明 + 一条链）** 取代；本节的两条不变量
> （**封板没有尺子** / **审计才是界限**）不变。以下保留作决策史。

- **封板没有尺子**：全 done、硬闸绿、甚至零 task 都能被说成"可封"；封板只是归档+版本+指针，不构成界限。
- 真正的界限是**审计闭环**（定义见 §2.1.6）；之后问封不封，是在问"要不要压缩上下文收摊"。
- **问题一·要不要审（可量化触发，§2.1.5）**：[^🅰1.3]
  - `check`(绿) / `task done` / `align` / `status` 命中定量信号 → `[NEXT] audit_suggested` + reasons；人只答要不要审。
  - 答是 → `k3dge milestone audit <id>`：必审 → `待修>0` 问 agent 修（倒计时默认修）→ 重审；`>3` 次未闭环 → `escalated` 转人工。
- **问题二·要不要封（仅审计闭环后唯一一次）**：[^🅰1.4]
  - `待修=0` 且有报告 → `[NEXT] seal_ready`；`k3dge milestone seal <id>` 才问"封板？(y/N，无倒计时)"。
  - 未审计先调 → `audit_needed` 指回 audit；答是 → align → 归档+版本+指针 + `*-closure.md` 收摊清单；答否 → 不封。
- **空窗 / 零 task / 只是硬闸绿**：不建议审、也不建议封。
- **有意留不算待修**：进 `docs/reviews/LEFTOVERS.md` 即可往下走。
- **k3dge 只调透镜、不自己审**：sidecar 与署名见 ADR-0006 §2.3.6，审计模块见 ADR-0025 §2.2；同一 agent 不得自审自封（fallback 到 `manual` 由人工复核除外）。
- **倒计时只出现在"有待修、agent 是否动手"**：超时默认"开修"，不跳过审计。
- **封板动作＝收摊/上下文压缩**：`seal` 机械部分只做归档+版本+指针。
  - `run_seal_flow` 写 `docs/reviews/<date>-<id>-closure.md` 清单，指引补齐落盘失败/未采用方案、清理上下文、更新设计文档、提交里程碑。

### 2.1.5 审计建议的量化尺子（§2.1.4 的触发条件）[^🅰1.5]
- "建议审"只用 k3dge 能自量的条件（不连 MCP、不跑 LLM），过线才 `[NEXT] audit_suggested`：
  - **账齐**：当前里程碑顶层任务 N>0 且 in-progress/idea=0。
  - **C2 嵌套**：触及 `src/` 控制流 AST（if/for/while/try/with）最大深度 ≥ 5。
  - **体积**：`src/`+`docs/specs/` 变更文件 ≥ 8。
- 同一快照只问一次：本里程碑已有报告即视为已审。
- 不纳入"建议审"的（已有别的闸）：`check` 红（去修/`k3dge sync`）、`guide-stub`（挡真封）。
- **架构/`overview.md` 更新不再是触发**：没有可数尺子，且"算不算持久设计、写得对不对"归 k3dit/人；改到封板 closure 清单里做（§2.1.4）。
- 单一事实源：`engine/nextstep.STATE_OPTIONS` + `engine/audit_trigger.py`，与 §12 同一张表。

### 2.1.6 一轮 = 一份报告 + 位置钉子
- 报告 schema 见 ADR-0017；单报告模型见 ADR-0005；钉的写源/收钉语义见 ADR-0025 §2.7。
- **闭环界定**：报告 `待修=0` 即 `audit_trigger.audit_closed`；改后由 `verify` 核该报告。[^🅰1.6]
- **`[NEXT] pending_findings`**：
  - `scan_pending_findings` 扫 `src/`+`docs/`（跳 archive/reviews/generated）的 `k3dit:pending` 钉（语法见 `peer_contract §8`）。
  - `check`/`status` 以最高优先报 `pending=N`——修的人打开文件就看见。
  - 往配对模板里插注释仍会误触 `TEMPLATE_DRIFT`。

### 2.1.7 人工入口 / Checklist 缓存 / 自动 loop 上限
- **人工主动入口**：`k3dge milestone audit <id>` 与 `k3dge milestone seal [--yes] <id>` 走同一套 `run_audit_flow` / `run_seal_flow`。[^🅰1.7]
  - `--yes` 仅跳过"要不要封"提问，不跳过审计（未闭环时 `seal` 返回 `audit_needed`）。
  - 自动探测（`[NEXT] audit_suggested` / `seal_ready`）与人工入口收敛到同一条流程。
- **审计条件 Checklist 缓存（非封板 checklist）**：`.agent/audit_checklist.json` 记条件快照（账齐/C2/体积 + reasons）、报告的 `待修`、`verify_attempts`、`audit_started_at`，以任务状态 hash 为键。
  - `check` 只读缓存、任务集不变不重算；`milestone audit` 发起时重置（预算归零 + 打 `audit_started_at`），人工/自动重跑各拿一个新的 3 次预算。
- **自动 loop 上限**：`run_audit_flow` 里 `verify` 连续 >3 次未闭环 → `escalated`，停止自动 loop、转人工。

### 2.1.8 外来审计源落盘
- 人把报告贴进对话框（或 agent 转发）＝**外部审计源**，不能直接被流程解析。
- 必须落盘为 `docs/reviews/YYYY-MM-DD-<id>-external-audit.md`：`k3dge milestone audit-submit <id> [--file <报告.md> | -]`（CLI）或 MCP `k3dge_submit_audit_report`。
- `persist_external_audit_report` 缺 12 列表头时自动补；最新一份覆盖旧的。
- 落盘后 `audit_closed` 即可判闭环，进入"问题二·要不要封"；外部源与 peer 产出走同一条路径。[^🅰1.8]

### 2.1.9 审计＝封版主体：一次声明 + 一条链（🅰1）

- **唯一入口**：`k3dge milestone seal <id>`。它同时是"人宣布要收这一章"与"开启封版流程"，
  **幂等重入**：预审失败 ⇒ 人修完再 seal；审计未闭环 ⇒ 返回"在办"，不阻塞、不空转。
- **三相位**：
  1. **预审**（进审计的门槛）：`tasks_all_done` + Full Matrix 绿（写对齐报告含 `align-pass`）
     + 形式闸（`docs/guides/` 无 stub / ADR 全 `Accepted` 且带可解析 `Landed-by` / docs 规约化）。
  2. **审计**：对**基线版本**跑（棘轮或 oneshot）；**审计正常返回 ⇒ 版号前进**（闭集见 §2.1.11），
     **不管有没有报告**。
  3. **审核后（自动）**：**先刷纯投影**（`docs/generated/{api,domains}.md`、`docs-index.json`、符号索引、README 自动块——全部派生、幂等），**再**写收摊清单
     → 封版提交（提版 + 归档 + 收摊清单 + 记录 trailer，见 §2.1.10）→ `tag <M> = <B>` → 指针前进 → 交接（打印待执行命令）。
     相位 3 **不跑整条 `sync`**：spec 接口块/契约哈希与 ADR reconcile 是**事实源写**，审计之后动它们等于改审计看过的内容；派生件的新鲜度另有闸（`DOC_INDEX_STALE` / `DOCS_GENERATED_STALE` / `SYMBOL_INDEX_STALE` / `EXTRACTOR_PLUGIN_STALE`），`k3dge where` 遇陈旧索引自愈。[^🅰3.1]
- **机械验证两道**：相位 1 的预审，以及**落点闸**（审计线的修复合并回主干时跑
  sync/check/doc-gate/pytest，红则回滚主干——先验后并）。
- **边界与标识**：审计的输入标识＝**基线 B 的 git hash**（不用 job id 作标识）；
  封板边界由 `tag <M> = B` 表示。**B 之后的主线改动归下一个里程碑**（票随之重挂）。
- **不要求封版提交紧贴 B**：审计期主线可自由提交，不冻结、不重写公共历史
  （代价：历史中封版提交位于后续工作之后，边界靠 tag 表达——这是有意的取舍）。

### 2.1.10 完成记录与运行态分层（🅰1）

- **durable（判据只认这些）**：基线 B、`tag <M> = B`、以及封版提交的 trailer：
  `seal-milestone` / `audit-baseline` / `audit-seat` / `audit-result`。
- **报告＝可选产物**：存在则须合格（12 列表头 + `审计人` / `透镜来源` / `基线`）；不存在不卡流程。
- **运行态（投影，不作判据）**：`.agent/audit_jobs.json`（phase / rounds / attempts / worktree /
  合并欠账）与 `.agent/audit_checklist.json`（verify 预算 / attempts）。它们是本地状态、可重建；
  **与 git 事实冲突时以 git 为准**（同 ADR-0025 §2.7 的写源/投影纪律）。

### 2.1.11 保证审计不可空转（🅰1）

- "审计正常返回"是**闭集**，逐条落进封版提交 trailer 的 `audit-result`：
  `closed`（真实执行且闭环）| `degraded-manual`（**走了 manual 传输**：没有独立透镜审过，
  **须带签名/席位**）[^🅰2.1] | `escalated`（转人工）| `refused`（skip / 无可达透镜）。
- **只有 `closed` 与带签名的 `degraded-manual` 允许推进版号**；`escalated` 交人；
  `refused` 拒绝且不推进。
- 禁止把"跳过/降级"当成功：审计失败、席未到位、透镜不可达，都不得表现为"时间到了就前进"。

### 2.1.12 CHANGELOG 由提交区间生成（🅰1）

- 来源：`<上一里程碑 tag>..<本轮 tag>` 区间的**非机械提交**（过滤进程作者与审计线机械件）；
  类型取 conventional 前缀（commit-msg 闸已强制）。
- 闸只验**不漏项**（区间内每个非机械提交都有对应条目）与类型合法；**写得好**归人/审计，
  不假装有机检。
- 目的：消除"票各写一行 + 封版再写一次"的双写（漏项与漂移的常见来源）。

### 2.1.13 非目标（🅰1）

- **不重写公共历史**（不为"封版提交紧贴基线"rebase 主线）；**不引入过渡号**（如 `M+` 形态）。
- **对外发布动作（push 等）归人**：k3dge 只打印待执行命令。
- closure 清单的人判项（落盘未采用方案 / 清理上下文 / 更新设计文档）保持 **advisory**，不塞硬闸。

### 2.1.14 审计确认（硬闸，主观）与封板增量（🅰4）[^🅰4.1]

- **解耦**：`seal` 不再强制跑审计（`[checks.seal].actions` 的 `audit` 节点降为可选/按需）；"审计是封板主体"退为"**审计确认是封板硬闸**"。
- **硬闸**：`audit 已确认`（人主观确认全版 audit 已做，或授权机器替打勾），**不可绕过**；机器/agent 不验证"审没审过"（第三方可替代 audit；"只审计、再让 agent 修"不受限）。
- **未确认 ⇒ 提醒（非死拒）**：打印第三方审计命令信息 + `k3dge milestone audit <id>` + `--confirm-audit`（确认当前即审后状态，替人打勾）。
- **基线绑定**：确认记基线 `B_ack`；封版时算增量 `B_ack..HEAD`，**排除**审计自身改动（job/报告 provenance、`Audit-*` trailer/审计基线）与**引用本次封版 hash 的提交**（trailer 如 `Audit-covered: <seal-hash>`，带即豁免；机械/审计归因小提交不再逐次弹提醒；不防伪造、不限提交类型、不追责）。
- **非空增量 ⇒ 提醒增量审计**（+ 冻结源码警告：再改触发新提醒）；**审计时点自由**。
- **启动必终态**：audit 一旦启动必须跑到终态（`closed`/`degraded-manual`/`escalated`/`refused`），不留 `incomplete` 悬空（salvage→落报告→记终态）。

### 2.2 为什么通过文件系统物理移动实现上下文压缩
`k3dge milestone seal` 将 `docs/tasks/*.md` 物理移入 `docs/tasks/archive/<id>/`。
`k3dge task list` 只扫顶层活跃文件，`archive/` 不在扫描面——Token 零浪费的上下文重置，且符合 `docs/tasks/archive/` 的 append-only 审计需求。

### 2.2.1 reviews 同批归档
- reviews 同属 append-only 证据；顶层堆积会把 leftovers 寻址与当前里程碑报告混在一起。
- 同一次 `seal` 把本里程碑的 `docs/reviews/*.md`（文件名含该 id，或正文含 `<!-- k3dge:align-pass:<id> -->`）移入 `docs/reviews/archive/<id>/`；其他里程碑的文件不动。
- 相对链接（LEFTOVERS.md）改写为 `archive/<id>/…`；失败则回滚移动并还原 LEFTOVERS.md。
- archive 契约（默认不扫、显式 `include_archive`）见 ADR-0023 §2.2。

### 2.3 版本与变更日志（原独立 ADR，合并入本条）
- **单源**：`pyproject.toml` 的 `project.version` 唯一事实源；`k3dge version bump` 镜像至 `.agent/manifest.json` 与 `src/k3dge/__init__.py`；三者不一致时门禁 `VERSION_MISMATCH` 阻断。
- **入口**：`k3dge version show` / `k3dge version bump [--major|--minor|--patch|--set X.Y.Z] [-m msg]`；bump 同时追加 `CHANGELOG.md`（Keep a Changelog + SemVer），原子写、失败回滚。
- **seal 联动**：`seal` 成功自动 `patch` bump + CHANGELOG 条目（`Seal milestone <id>.`）；`--no-version-bump` 可跳过；CLI 与 MCP 行为一致。[^🅰1.9]
- **失败语义**：`bump_version` 原子；`seal` 后自动 bump 失败**不回滚已归档 tasks**，仅 stderr / MCP `version_bump_failed` 告警——禁止"归档成功、版本一半"被静默忽略。
- **不引入** hatch-vcs / setuptools_scm（自举期 `pip install -e` 已满足）。重开条件：需 `git tag` 驱动或 PyPI 发布。

## 3. 产生后果 (Consequences)
- **正面**：确定性验收 + 防过度工程 + 上下文经济性闭环；`engine` 扩展为"门禁判定与生命周期治理核心"（边界见 `overview.md` / `engine/spec.md`）。
- **负面**：`engine` 引入文件生成/移动副作用，需与 `sync` 的 spec 回写职责保持边界（`engine` 管归档，`sync` 管契约）。

---

[^🅰1.1]: 修改（🅰1）：align 不再是独立自动步骤，而是**封板流程的预审相位**（§2.1.9 相位 1）。`[NEXT]` 仍以量化信号提醒"要不要审"（§2.1.5），但不再自动调 align。

[^🅰1.2]: 修改（🅰1）：`audit_closed`（报告存在 + `待修=0`）**不再是封板前置**；边界改由"审计正常返回 + 基线"定义（§2.1.9/§2.1.11）。报告降级为**可选产物**：存在则须合格（12 列 + 署名 + 基线），不存在不卡流程。

[^🅰1.3]: 修改（🅰1）：量化信号降为**提醒**，且"要不要审"不再是独立的第一个人工问答——人发起 `seal` 即表示进入封版流程，预审通过后由同一条链自动发起审计（§2.1.9）。

[^🅰1.4]: 修改（🅰1）：不再是独立的第二个问答。人发起 `seal` 就是在宣布"要收这一章"；审计闭环后由**同一条链**自动收尾（§2.1.9 相位 3），无需再敲一次命令。

[^🅰1.5]: 修改（🅰1）：量化尺子**只作提醒**（"要不要审"的建议），与"能不能封"无关；封板由 §2.1.9 的链定义。"本里程碑已有报告即视为已审"在提醒语境下仍成立。

[^🅰1.6]: 修改（🅰1）：闭环界定从"报告 `待修=0`"改为"**审计正常返回**"（闭集见 §2.1.11）。报告与钉仍是产物/写源，但不再是"封板资格"的唯一判据；机械闸另由落点闸托底（§2.1.9）。

[^🅰1.7]: 修改（🅰1）：人工入口收敛为 `k3dge milestone seal <id>` **唯一入口**（幂等重入）；`--yes` 只跳"封板？"提问。`.agent/audit_checklist.json` 降为**运行态**，不作判据（§2.1.10）。

[^🅰1.8]: 修改（🅰1）：`audit-submit` 只**补证据**（落盘报告），**不推进版号、不触发封板**——版号前进由"审计正常返回"决定（§2.1.11）。

[^🅰1.9]: 修改（🅰1）：版本在**审计正常返回后**前进（不再等"seal 成功"）；CHANGELOG 改由**提交区间**生成（§2.1.12），闸只验不漏项，语义润色归人。

[^🅰2.1]: 修改（🅰2）：`degraded-manual` 原表述是"降级到 manual 协议"，容易被读成"只有**降级**才算" ——于是"把 manual 排在 transports 首位"就成了绕开署名要求的路（`downgrades` 为空 ⇒ 判 `closed`）。 裁定：判据是**事实**（有没有独立透镜），不是**相对位置**（链里排在哪儿）。故 `provider == "manual"` 一律 `degraded-manual`、一律须署名；本仓 `[mcp, manual]` 不受影响（本就落在降级位）。

[^🅰3.1]: 修改（🅰3）：新增"相位 3 先刷纯投影"。为什么不是整条 `sync`：`sync` 链里 `sync_domains` （spec 接口块 + `Contract Hash`）与 `reconcile_adrs`（ADR frontmatter + 移文件）是**事实源写**， 审计之后执行等于让"审的那一版"与封版内容脱钩（§2.1.9「审哪版封哪版」）。纯投影刷新与新鲜度闸 是同一件事的两半：**闸管发现**（重算比对，红了给重生命令）、**刷管及时**（封版那一刻与 `k3dge where` 自愈）。 落地：`src/k3dge/engine/seal_flow.py::_refresh_projections`、`engine/evaluator.py`（三闸）、 `engine/search.py::_is_stale_cheaply`；见 `docs/tasks/2026-09-21-M11-feat-projection_refresh.done.md`。

[^🅰4.1]: 修改（🅰4）：seal/audit 解耦 + 审计确认硬闸（人主观）+ 增量豁免。驱动缘由：k3dit 一轮闭环不可靠（多轮 `incomplete`/未关，封板被机器验证卡死）+ 第三方工具可替代 audit + 审计时点应自由；本地确认丢了大不了再提醒一次，不防伪造/不限类型/不追责（单人流，hash 引用是公开声明）。
