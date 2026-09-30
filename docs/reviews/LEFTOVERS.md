# Intentional leftovers

Do not reopen IDs in this table. Overturning a leftover = edit this file, not a shadow list.

Denial reason and reopen condition live here only.

| ID | 一句话 | 报告 |
| --- | --- | --- |
| A-11 | git 无 timeout：本地立刻返回；加 timeout 会把门禁变成假失败 | [2026-08-24-5pass-audit.md](archive/untagged/2026-08-24-5pass-audit.md) |
| S-13 | MCP 任意 `workspace_path`：本地 stdio = OS 用户；改网络 MCP 必须重开 | [2026-08-24-8dim-vibe-audit.md](archive/untagged/2026-08-24-8dim-vibe-audit.md) |
| F-14 / LR-5 | `_replace_between_all` O(N²)：spec ≪ 100KB，可读性优先 | [2026-08-23-5pass-audit.md](archive/untagged/2026-08-23-5pass-audit.md) |
| F-15 / LR-6 | milestone 重复读盘：活跃任务少，OS 缓存够 | 同上 |
| R3-1 | 三处域表行：4 域 + ADR-0018 判据/投影不可合并 | [2026-08-21-line-by-line.md](archive/untagged/2026-08-21-line-by-line.md) |
| R3-4 | 函数内 import subprocess：L2 冷路径 | 同上 |
| P1-06 | `K3DGE_BASE_SHA` 是 argv 不是 shell | [2026-08-25-pass1-robustness-security.md](archive/untagged/2026-08-25-pass1-robustness-security.md) |
| P1-09 | `test_command_template`：能改 manifest 已能改命令 | 同上 |
| P2-PUR-04 | `render_readme_layout` 仍被 generate-docs 调用 | [2026-08-25-pass2-architecture-dag.md](archive/untagged/2026-08-25-pass2-architecture-dag.md) |
| D-01/02/03/06/10/11 | 两提取器 + 零 TS，不抽 register/ABC —— **已推翻（2026-09-16）**：`register_extractor()` + manifest `extractors` 键已落地，`ContractExtractor` ABC 为插件契约，内置提取器经同一接口注册 | [2026-08-25-pass3-design-abstraction.md](archive/untagged/2026-08-25-pass3-design-abstraction.md) |
| D-07/08/12 | MCP 同域适配、本地 stdio、seal 恒 bump | 同上 |
| D-09 | pyproject 双引号形态固定 | 同上 |
| P4-05/08 | architecture 与运行时状态不进 PAIRS | [2026-08-25-pass4-consistency-alignment.md](archive/untagged/2026-08-25-pass4-consistency-alignment.md) |
| P4-06 | doc/task 薄路由；audit 见 P2-PUR-06 | 同上 |
| P4-07 | 矩阵 ≠ L2 执行（ADR-0005） | 同上 |
| P5-02..07 | 性能阈值未到 | [2026-08-25-pass5-simplicity-performance.md](archive/untagged/2026-08-25-pass5-simplicity-performance.md) |
| BV-01 | `bump_version` 跨三文件非原子：单文件 `tmp+replace` 原子，`kill -9` 半漂移由 `VERSION_MISMATCH` 暴露，已加内存回滚；引入跨文件原子需 `write-ahead log` 复杂度不值 | [2026-08-27-5pass-full.md](archive/untagged/2026-08-27-5pass-full.md) |
| T-01 | `check` 纯静态：peer 挂死不阻断 `GateReport`；出向编排只在 `milestone audit`/`seal`/`doc-audit`（ADR-0006 §2.3.2） | [2026-08-27-5pass-full.md](archive/untagged/2026-08-27-5pass-full.md) |
| T-02 | Pure Evaluator vs Mutator：判定与 milestone/version 副作用同域，阈值未到不拆 `lifecycle` | 同上 |
| T-03 | Self-Hosting 嗅探：`Manifest self_hosting` 显式化待规模化再 ADR | 同上 |
| SEAL-01 | `seal` 验 align-pass + 无 stub；报告格式由 `k3dit check-report` 在 `on_pre_seal` 卡 | 同上 |
| AGENTS-SP-01 | `AGENTS.md` 稀疏寻址无已读断言：以 Gate 红灯逼回读 | 同上 |
| value-7 | `run_milestone_alignment` 职责混居：已拆 `_align_run_gates()`（gate 注册+dispatch） | [2026-09-13-M9-audit.md](archive/M9/2026-09-13-M9-audit.md) |
| value-9 | `.mcp.json` 读口已归 `engine/mcp_json`（cli+engine）；`templates/scaffold` 写侧仍自解析（孤岛，ADR-0001 §2，templates ↛ engine） | 同上 |
| CC-01 | `audit_flow.collect_audit` CC35：线性管线（找 job→调 collect→验信封→验基线→落盘→回填→merge→存状态），拆了跨文件追管线 | cc_debt_remaining 复判 |
| CC-02 | `audit_flow.submit_audit` CC17：同上，线性管线（锁线→调 action→验信封→建 task→存状态） | 同上 |
| CC-03 | `milestone_audit._ratchet_audit_step` CC26：状态机天然多分支（pending_merge→inflight→done→submit→collect），48 行读起来就是一棵决策树 | 同上 |
| CC-04 | `evaluator._run_batch_tests` CC24：subprocess 调用 + 错误分类（timeout/not-found/non-zero/module-missing），每种一个 per-domain violation | 同上 |
| CC-05 | `evaluator._warn_changelog_done` CC15：线性扫描（读 CHANGELOG→遍历 tasks→检查 status=done 是否在 Unreleased） | 同上 |
| CC-06 | `evaluator._check_domain_imports` CC12：线性 AST 遍历，37 行已紧凑 | 同上 |
| CC-07 | `evaluator._check_template_drift` CC13：线性比对（assets ↔ 本仓文件） | 同上 |
| CC-08 | `evaluator._check_verification_matrix` CC11：线性逐行校验 | 同上 |
| CC-09 | `evaluator._package_prefix` CC14：字符串 LCA 计算，32 行 | 同上 |
| CC-10 | `worktree.merge_back` CC17：线性 git 工作流（strip→advance→dirty→ff→rebase→ff） | 同上 |
| CC-11 | `worktree.ensure` CC14：git worktree 创建 + "already registered" 自愈 | 同上 |
| CC-12 | `worktree.strip_pins` CC13：线性树遍历 + 逐文件去钉 | 同上 |
| CC-13 | `seal._seal_archive` CC18：线性文件操作（碰撞检查→搬文件→bump→rollback） | 同上 |
| CC-14 | `seal._seal_review_gate` CC16：四个顺序检查（stub→pass→task list→兜底），51 行 | 同上 |
| TERM-01 | `scope` 一词四义：钉作用域（line/file/repo）/ 提交来源（external）/ 审计目标（milestone M10、docs）/ transport 路径（k3dit.actions.audit）。各自活于独立模块，语义相邻，风险仅在跨模块推理时误读 | [2026-09-16-M10-refactor-term_collision_cleanup.done.md](../tasks/2026-09-16-M10-refactor-term_collision_cleanup.done.md) |
| TERM-02 | `kind` 一词三义：钉种类（pending/leftover/…）/ 报告种类（audit/quality）/ 角色种类（gate/service）。同上，且各有枚举常量定义（`markers.KINDS`、`pipeline_schema` 校验） | 同上 |
| TERM-03 | `state` 一词四义：审计 job 态 / next-step 态 / task status / `state_machine` 模块。同上 | 同上 |
| DUP-01 | `AUX_NAMES` 在 `doc_catalog` 与 `pure_schema` 各一份：**刻意复制**（pre-commit 零依赖硬约束），已由 `test_aux_names_in_sync` 守卫抗漂移 | 同上 |
| INTRO-01 | 规则 12「引入纪律」prose-only 无闸：判据是决策质量非文件事实。曾试把筛子 2（接入点）机检——实测 20 子命令中 13 个无到达路径（65% 误报），不可用 | [memo §S9](../memo/archive/2026-09-16-orchestration-form-exploration.md) |
| ADR-01 | 12 条 ADR 的 `Note` 仍是旧式修订日志（①②③…）；AUTHORING 已定「修订痕迹全进 `Amended-by`」——迁移未做，无实测危害 | [0006](../adr/0006-mcp-foreign-harness-injection.md)（已迁样板） |
| NEXT-01 | `[NEXT] state=seal_ready` 与 `seal_preconditions_error` 是两份源：前者不读封板前置，故 Proposed ADR / 未 done 任务仍在时仍报「可封板」 | [0026](../adr/0026-projection-contract.md) |
| SYNC-01 | `docs_updated` 标志只含 manual docs：只重生 `docs-index.json` 时 MCP 报 `up_to_date: true`（同一快照实际写了盘）。**CLI 文案已修（2026-09-21，`2026-09-21-M11-fix-memo_review_landing`）**；MCP 字段语义仍窄（reopen 条件见 memo）| [2026-09-21-sync-docs-updated-flag.md](../memo/2026-09-21-sync-docs-updated-flag.md) |
| PRE-01 | **已收口（2026-09-21，`2026-09-21-M11-fix-commit_runs_hooks`）**：`k3dge commit` 不再用 `--no-verify`，改由 live hook 承担引用/名实/markdown/排查闸（探针：临时加 `ADR-42xx` 后 `k3dge commit` exit=1）。**仍有意留**：内层 `evaluate(staged)` 与外层 hook 的 `check`（worktree 范围）各跑一遍；审计线/封版的 `--no-verify` 不动（机械件）| [2026-09-21-hookization-surface-inventory.md](../memo/archive/2026-09-21-hookization-surface-inventory.md) |
| PRE-02 | 引用闸是**增量闸**：只扫当次 staged 的受管（非 aux、非 archive）文档 ⇒ 已入库文件永不复扫。收口 2 处后，全量复扇余 **14 处 `DANGLING_ADR_REF`**，分布已查清、**不是缺口**：13 处全在 `archive/`（ADR-0023 低权威留档，不修）；1 处在 `docs/reviews/2026-09-10-doc-audit-docs.md` 的**发现正文**（D-2 行引用“已不存在的裸号 0026/0027/0028”作为问题本身，非活指针；该文件若重新 staged 会报 DANGLING —— 属报告引用历史编号的误报面）。另：`check_adr_ref_retired` **设计上就不扇 `docs/reviews/` 与 `archive/`**（append-only 证据），所以那 14 处只有 DANGLING 一种码。真正在面上的问题只有 PRE-01（`k3dge commit` 绕 hook）| 同上 |
| FSM-01 | `state_machine.resolve()` 无生产消费者：状态转移在生产路径上由 `task done` 直写 status + align/seal 事后验合法性（`_ALLOWED_STATUS`）承担。`TRANSITIONS` 反而已有消费者（`summary()` → `k3dge status --json` 观测件）⇒ 表留、`resolve()` 留（删无收益；补“两处相等”类守卫是同义反复） | 同上 |
| PRE-03 | **跨仓自限定引用不再被引用闸校验**：`k3dge ADR-NNNN`（`where ADR-NNNN` 同）视为指向 k3dge 仓，下游编号从 0001 起 ⇒ 不解析、不报（否则 k3dge 自己下发的文档永远过不了自己的 hook）。代价：本仓里带 `k3dge ` 前缀的引用写错号也不会红。Reopen：出现一次写错号的实例 | [2026-09-21-hookization-surface-inventory.md](../memo/archive/2026-09-21-hookization-surface-inventory.md) |
| PRE-04 | **根文件（`AGENTS.md`/`README.md`）里的路径引用不在任何闸面**（pre-commit 只扫 `docs/**`）。实测 4 处"缺落点"全是约定/引文：`engine/audit_trigger.py`（域相对写法）、`.agent/gates.toml`（历史引文）、`../k3dit/...`（跨仓）。直接设闸≈高误报（同 INTRO-01 结论）⇒ 有意留，只记账 | 同上 |
| PRE-06 | `DOCS_TOML_KEY_UNKNOWN` **只看键、不看文件**：`= true` 而文件未生成是收尾流程常态（`generate-docs.sh` 收尾才落桩）⇒ 不报；"配了却没生成"目前无人管（收尾清单 advisory）| 同上 |
| PRE-05 | **`INIT_DELIVERED_DOCS` 是手维护清单**（init 下发件的排查面豁免）：新增下发文档时要手动加，否则下游第一次提交会被 `DOC_NEW_UNSCREENED` 拦。Reopen：出现一次"新下发件把下游首次提交拦了"的实例 | 同上 |
| FACTS-01 | **`gate_facts.fix_kind` 生产侧无调用**（只在 `test_gate_facts` / `test_doc_fix` 里用）：它服务一条**真实的交叉核对守卫**——`doc_fix.FIXABLE_RULES` ⇔ 声明里 `fix=="deterministic"`。⇒ **有意留，别再当死代码删**（2026-09-21 悬空设计盘点时被误判过一次） | [2026-09-21-M11-fix-dangling_design.done.md](../tasks/2026-09-21-M11-fix-dangling_design.done.md) |
| EVENT-01 | **`events.read_events` 仓内零读者**（只有测试 + `docs/generated/api.md` 的接口块）：`.k3dge/events.jsonl` 是**对外事实供给**（ADR-0026 §2.6 的 D 线闭集之一：状态可见/事实供给/幂等步进），消费者在仓外（席位/agent）⇒ 有意留，别删 | 同上 |
| AUDIT-01 | **`milestone_audit` 的 oneshot 形状当前不可达**（`.agent/pipeline.toml` 是 `[roles.audit].mode="ratchet"`，而声明面允许切回 `oneshot`）⇒ 配置相关路径，非死代码；**有意留**（切模式即启用） | 同上 |
| value-22 | `cli/main.py` 单模块超千行（原 0003，已并入 `ADR-0018 §2.12`）：体积属实，按 A-1 分块逐程消化，本轮有意留 | [2026-09-20-M10-audit.md](archive/M10/2026-09-20-M10-audit.md) |


## RATCHET-01 ✅ 已收口（2026-09-26）：棘轮残余清完

- **已做**：`_ratchet_audit_leg`/`_ratchet_audit_step` 删除；`mode="ratchet"` 改为**显式拒绝**（带迁移指引）；
  `k3dge audit` 的六个对等动词（submit/status/show/advance/materialize/close）改为**拒绝并指路**；棘轮测试类删除，
  换成"退休拒绝"用例；ADR-0025 §2.9.6 amend 🅰3。
- **残留（代码在、无人用）**：`engine/audit_flow.py` 里那六个 verb 的实现仍在（测试已删，仅 CLI 入口拒绝）；
  `open_ratchet_jobs` + `[NEXT] ratchet_open` 状态（既无写入者）与 `docs/protocols/peer_contract.md` §1.4 的棘轮协议。
- **下一步（要一次做完，别分半）**：删 `audit_flow.py` 的六个 verb 与其私有件（`_load_state`/`_save_state`/`_state_path`/
  `_find_awaiting`/`_parse_envelope`/`_recent_downgrades`/`STATE_REL`）→ 删 `open_ratchet_jobs` 与 `ratchet_open` 状态
  （同步 `nextstep.STATE_OPTIONS` + `docs/architecture/overview.md` §6 状态表，闸 `ARCH_STATE_DOC_DRIFT` 会逼你一起改）
  → 改 `peer_contract.md` §1.4 → 删 AGENTS 该行。
- **本次两次自伤（如实记）**：① 用 `sed 's/k3ge/k3dge/'` 式**子串**正则删"含 audit_flow 的行"时，连带删掉了
  `import audit_evidence` 与 `import persist_external_audit_report`（`run_audit_flow` 含该子串）⇒ 由测试当场抓出并修；
  ② 更早一次替换把 `_attest` 别名/`_rel_within_workspace` 一起删掉（`commit-attest` 崩）。教训：删行用**词边界**，改完立刻跑全量。
### 收口（RATCHET-01 / ADAPTER-01）

- `audit_flow.py` 的六个 verb 与其私有件（`_load_state`/`_save_state`/`_state_path`/`_find_awaiting`/`_parse_envelope`/
  `_recent_downgrades`/`STATE_REL`）已删（模块 593 → 131 行，只留判据面：`audit_evidence`/`audit_call_result`/
  `audit_result_of`/`SEALABLE_AUDIT_RESULTS`）；活口 `audit_evidence`/`result_of` 的导入点核对无误。
- `open_ratchet_jobs` + `[NEXT] ratchet_open` 状态退役：`cli/status.py` 产出口删除、`nextstep.STATE_OPTIONS` 去掉该态、
  `seal_flow` 的 inflight 元组同步、架构总览 §6 表与时序图同步、AGENTS 该行删除（资产字节锁同步）。
- `peer_contract.md` §1.4 标"已退休（历史/对等 harness 参考）"；ADR-0006 amend 🅰4（传输链只留对等 harness）。
- k3dit 侧 ADAPTER-01 同轮完成：`envelope.py` 删除、CLI 动词改"拒绝并指路"、5 个测试驱动器改直调
  `jobs.create_job`/`collect_job`（副作用 `ingest_prior`/`maybe_run` 显式调）、k3dit 仓 0008 §2.8、spec/指南同步。

## LINE-M10-01 残留 worktree 已清，但线内 5 个提交**没进主干**（待人工判）

- **已做**：`git worktree remove .k3dge/wt/M10`（此前 worktree 干净、无未提交改动）；分支 `k3dit/M10` 与
  救援 tag `rescue/M10-line-20260926 → eb67efb` **都保留**（内容可随时取回）。
- **证据**：`git cherry -v main k3dit/M10` ⇒ 5 个 "round work M10" 提交**全部带 `+`**（未进主干）；
  线落后主干 33 个提交；`main...k3dit/M10` 13 文件 +256/−185（含 `milestone_audit.py` 183 行）。
- **为什么没删分支**：这与先前 `k3dit/M0` 的退役不同——那次线内内容已被主干取代；这次 `git cherry` 说
  **没有一条进主干** ⇒ 可能是未合并的 M10 审计产物。删线＝丢工作，须人判（合 / 弃 / 只看某几个文件）。
- **下一步（人）**：`git diff main...k3dit/M10` 逐文件过一遍；要合就 `git merge`/挑提交；要弃就
  `git branch -D k3dit/M10`（救援 tag 仍在）。

## C 验收（2026-09-27，k3dit 上走 `milestone audit M0`）：链路已通，途中修掉 3 个真缺陷

**做法**（自审边界见 k3dit 仓 0008 §2.11）：k3dit 侧 `[roles.audit]` 改 `k3dit_mode = "audit-only"`、
`k3dit_pins = "artifact"`、`k3dit_scope = "src/k3dit/windows"` ⇒ 自审只出证据、不封板、不动被审树业务码。

**链路证据（末次真跑）**：腿产包 → `--verify` ok → 消费（`fix.patch`/`pins.patch` 按 `apply_order`）→
报告落 `docs/reviews/2026-09-27-M0-k3dit-bundle-audit.md` → **提交 `164f9bf`**（job `ebc3a0d6f86a`，
包 `634c944c5465`）→ `refused(audit_evidence_only)` → `[NEXT] pending_findings pending=17`（钉留树可见）。
更早一轮（scope=tools，2.29M prompt）因 dirty tree 被拒 ⇒ 现已能跑到提交。

**途中修掉的 3 个真缺陷**（都由真跑暴露、单测没抓到）：
1. **k3dge `milestone audit` 入口悬空**：棘轮退休（`94c8f37`/`e5ff5df`）删了 `run_audit_flow` 调用，
   只留 `print(msg)` ⇒ `UnboundLocalError: msg`，审计腿根本没跑（修 `fde4654`，含回归测试）。
2. **k3dge 落树后不重生投影 ⇒ 提交注定被自家闸拦**：腿往 `docs/reviews/` 写报告 ⇒ `docs-index` 过期 ⇒
   `DOC_INDEX_STALE` 拦下；且 `commit_applied` 把 git 报错**吞成空 sha**（腿只表现为"没提提交"，树留 staged）
   ⇒ 修 `065dd66`：提交前 `write_docs_index` 重生投影并并入同一提交；`commit_applied` 返回 `(sha, 错误)`，
   失败即 `refused(audit_bundle_commit_failed)` 并提示人工处理。
3. **k3dit 钉行判据是子串版**：`pack.PIN_LINE = k3dit:(pending|…)` 把窗卡里**文档举例的钉**
   （「落成的行是：`# k3dit:pending code-1 …`」）当钉 strip ⇒ 语义层哈希与 `pins.patch` 都错 ⇒
   消费侧 `APPLY_CHECK_FAILED:pins.patch`。修 `d82121b`：判据与 `pins.py`（契约 §8 机械手）**同形**
   （行首 `#`/`//`/`<!--` + `k3dit:<state> <id>`），含"用本仓真卡片断言"的回归测试。

**顺序教训（已写进提交信息）**：先提交声明改动，再跑审计——否则消费相位的 `DIRTY_TREE` 守卫会拒
（守卫行为正确，错的是顺序）；`milestone audit` 前请确认工作区干净。

**留**：k3dit 侧现有 17 枚 `k3dit:pending` 钉（自查产物，钉留树）⇒ 处置归人/后续轮；要封板须显式把
`k3dit_mode` 改回 `full` 再跑（那次才落补丁+提交）。

## 消费侧独立验收已落地（2026-09-27）：闸从"产出方自证"移到 **k3dge 自己验**

**改前**（`git show HEAD~N` 可核）：`audit_bundle.verify_bundle()` 直接调 `k3dit audit --verify`；`consume`
的闭环闸读**产出方自报的** `manifest.status` ⇒ 等于"自己批自己"（违 ADR-0012 的"消费者"环）。

**改后**：新模块 `engine/audit_verify.py::verify_bundle_local`（k3dge 自己读包的**文件**）：
① 包完备性（`bundle_version` 白名单 / 输入身份 / `apply_order` 补丁存在非空 / 必需文件齐）；
② **报告完备性**（12 列**精确**表头顺序、行 ↔ `findings` 一一对应、必需格非空、状态闭集、`已修`必带「验证」）；
③ **本地闭环**（未关＝`pending`/`fixnote`/`disputed` 或终态未背书；产出方 `status` 只作交叉核，
   不一致**报出来**且以本地为准）；
④ **内容哈希链**（在临时副本按 `apply_order` **反序**反向应用后逐文件比 `baseline`；去钉用契约 §8 语法单源
   `engine/markers`；**含钉文件不豁免**——先前的写法整份跳过，等于在含钉文件里任何篡改都抓不到）。
过了闸才由 k3dge 落补丁（`apply_bundle`）。

**真包控制证据**（`/tmp/ctl`＝修好后的 k3dit 产的 14 钉包）：
正面对照 `ok=True`（findings 14＝报告 14 行、哈希链 **281 文件 0 不匹配**）；三类伪造全部**拒**：
报告删一行（"报告漏行"）、含钉文件里追加代码（"内容哈希链不通过"）、伪造 `status=closed`（"闭环事实不一致…以本地为准"）。

**顺带发现（旧包不可消费）**：2026-09-27 之前产出的**全部**包，其 `baseline`（语义层）受产出方旧版**子串 strip**
影响（把"提到钉的文档行"也去掉）⇒ 新的反向重放会**如实拒收**。要消费请用修好后的 k3dit **重新产包**。

## 流程体检（2026-09-27）：绕路/无实效项清单（逐条带证据）

**已修**：
1. **同一序列写两遍、第三处没有** —— `落报告 → 重生 docs 投影 → 提交` 此前写在腿的正常路与 `_land_report_even_on_refusal`
   两处，而**手动入口 `k3dge audit bundle` 两处都没有**（跑完报告不落盘、不提交 ⇒ 判定面看不到产物，"同一模块同一参数"
   只是形式）。现在三处共用 `audit_bundle.land_report`（报告 + 已落补丁 **同一次提交**，投影并入）。
2. **模板注释过时** —— `pipeline.toml.template` 写着"形状切换＝`oneshot`（缺省）/`ratchet`/`bundle`"：
   `ratchet` **已退休**（声明即拒）、`oneshot` 也不是审计角色的缺省（缺省＝无外部步的本地工具）。已改。

**记录不拆（有实效但只对另一种形状）**：
3. **verify 预算 / `escalated` / `degraded-manual`**：`bump_verify_attempt` 的唯一调用点在 **oneshot 腿**
   （`milestone_audit.py:263`），bundle 腿不碰 ⇒ 对常态（bundle）**无实效**。但 oneshot 是 ADR-0006 🅰3
   明确保留的"对等 harness 扩展位"（有测试覆盖、无配置声明）⇒ 拆它属策略变更，需人拍；此处只记清"它只对 oneshot 有效"。
4. **`k3dit audit --verify`（产出方自证）**：消费路径已不调（改本地验收）；它仍是产出方自己的 CLI 动词（产出方自测/人工用），
   不算悬空，但**不再构成任何闸**。

## REVIEWS-LAND-01（更正登记，2026-09-27）：落地必须满足**被落地仓**的评审登记规则

**先更正框架**：我先前把它写成"跨仓/与 k3dit 有关"的流程问题，是**登记错了**——k3dge 作为消费仓时，
要满足的是 **k3dge 自己的**评审规约；k3dit 的仓规与 k3dge 无关。事实核对：
- k3dge `docs/reviews/` 只有 `README.md` + `AUTHORING.md`（通用受管文档规约）+ 历史 closure 报告，**没有**
  "索引登记 / 已结归档"那套闸 ⇒ 对 k3dge 而言这条**不存在**；
- k3dit 有那套（`test_reviews_format.py` 两条：README 索引须列全且机器状态/待修计数相符；已结须入
  `archive/<M>/`）⇒ 所以只有"落到 k3dit"那种验证跑会踩到，且该修法**归 k3dit**（口径是它的，不该由 k3ge 另抄）。

**泛化后的规则（判据，留在 k3dge 一侧）**：落报告/落补丁后，**被落地仓自己的格式闸必须绿**；若它红了，
按"确定性修复"原则应由**该仓**提供规整器（k3ge 按声明调用），而不是 k3ge 复刻它的登记规则。
真跑实测：k3dit 那轮踩了 3 次，均手工补（k3dit `7ac5f51` / `63eb81c`）。**k3dit 的修法登记在它自己的
`docs/reviews/LEFTOVERS.md`**（甲＝加 `check-report --fix`；乙＝把归档挪到 seal，使文闸一致）。

## 消费侧独立验收已落地（2026-09-27）：闸从"产出方自证"移到 **k3dge 自己验**

**改前**（`git show HEAD~N` 可核）：`audit_bundle.verify_bundle()` 直接调 `k3dit audit --verify`；`consume`
的闭环闸读**产出方自报的** `manifest.status` ⇒ 等于"自己批自己"（违 ADR-0012 的"消费者"环）。

**改后**：新模块 `engine/audit_verify.py::verify_bundle_local`（k3dge 自己读包的**文件**）：
① 包完备性（`bundle_version` 白名单 / 输入身份 / `apply_order` 补丁存在非空 / 必需文件齐）；
② **报告完备性**（12 列**精确**表头顺序、行 ↔ `findings` 一一对应、必需格非空、状态闭集、`已修`必带「验证」）；
③ **本地闭环**（未关＝`pending`/`fixnote`/`disputed` 或终态未背书；产出方 `status` 只作交叉核，
   不一致**报出来**且以本地为准）；
④ **内容哈希链**（在临时副本按 `apply_order` **反序**反向应用后逐文件比 `baseline`；去钉用契约 §8 语法单源
   `engine/markers`；**含钉文件不豁免**——先前的写法整份跳过，等于在含钉文件里任何篡改都抓不到）。
过了闸才由 k3dge 落补丁（`apply_bundle`）。

**真包控制证据**（`/tmp/ctl`＝修好后的 k3dit 产的 14 钉包）：
正面对照 `ok=True`（findings 14＝报告 14 行、哈希链 **281 文件 0 不匹配**）；三类伪造全部**拒**：
报告删一行（"报告漏行"）、含钉文件里追加代码（"内容哈希链不通过"）、伪造 `status=closed`（"闭环事实不一致…以本地为准"）。

**顺带发现（旧包不可消费）**：2026-09-27 之前产出的**全部**包，其 `baseline`（语义层）受产出方旧版**子串 strip**
影响（把"提到钉的文档行"也去掉）⇒ 新的反向重放会**如实拒收**。要消费请用修好后的 k3dit **重新产包**。

## 流程体检（2026-09-27）：绕路/无实效项清单（逐条带证据）

**已修**：
1. **同一序列写两遍、第三处没有** —— `落报告 → 重生 docs 投影 → 提交` 此前写在腿的正常路与 `_land_report_even_on_refusal`
   两处，而**手动入口 `k3dge audit bundle` 两处都没有**（跑完报告不落盘、不提交 ⇒ 判定面看不到产物，"同一模块同一参数"
   只是形式）。现在三处共用 `audit_bundle.land_report`（报告 + 已落补丁 **同一次提交**，投影并入）。
2. **模板注释过时** —— `pipeline.toml.template` 写着"形状切换＝`oneshot`（缺省）/`ratchet`/`bundle`"：
   `ratchet` **已退休**（声明即拒）、`oneshot` 也不是审计角色的缺省（缺省＝无外部步的本地工具）。已改。

**记录不拆（有实效但只对另一种形状）**：
3. **verify 预算 / `escalated` / `degraded-manual`**：`bump_verify_attempt` 的唯一调用点在 **oneshot 腿**
   （`milestone_audit.py:263`），bundle 腿不碰 ⇒ 对常态（bundle）**无实效**。但 oneshot 是 ADR-0006 🅰3
   明确保留的"对等 harness 扩展位"（有测试覆盖、无配置声明）⇒ 拆它属策略变更，需人拍；此处只记清"它只对 oneshot 有效"。
4. **`k3dit audit --verify`（产出方自证）**：消费路径已不调（改本地验收）；它仍是产出方自己的 CLI 动词（产出方自测/人工用），
   不算悬空，但**不再构成任何闸**。

## A 路 ✅ 已达成（2026-09-27）：审计返回的修复**并进了主干**（三路合并），不是"不落"

用户指出"k3dge 消费报告、把审计返回的修复并进主干"是**既定目标** ⇒ 本轮把缺的那一环补齐并跑通：
**k3dit `5c2c8cc`**（手动入口一条命令）：`consume ok` → `strategy=three-way-merge` → **11 个文件**并进主干
→ 落库后校验（声明 `.venv/bin/k3dge sync && index && pytest`）**通过** → 报告+契约哈希+投影+修复**一次提交**。

**为此补的四件事**（此前"打不上就整包落不下"）：
1. **三路合并**（`engine/audit_merge.py`）：base＝包的可重放基线（`code/` 反序反向应用，抽成
   `audit_verify.replay_to_baseline`，与哈希闸同源）、theirs＝包 `code/`、ours＝当前主干。
   **按两层语义分手**：`fix.patch`（代码）走 `git merge-file`；`pins.patch`（钉，纯增量）正向应用、
   打不上就按文件**并集**（两边都加钉 ⇒ 两枚都留）。冲突如实报文件（fail-clear）。
2. **落库后校验**（声明面 `[roles.audit] post_apply_check`）：先在**工作区**跑（venv/钩子都在那），
   不过就回滚刚写的文件 **＋ `docs/generated/*`** ⇒ 把"落进主干必须过消费仓测试"从人的习惯变成流程一步。
3. **显式漂移接受**（`--accept-baseline-drift <理由>`）：旧包 `baseline` 受产出方旧 strip 规则影响（文档面必然
   对不上，实测 10 个 `.md`）。两条硬条件：有理由 + 漂移文件**不被任何补丁触及**；接受事实记入
   `accepted_drift`（写进报告/账）。
4. **写入面收口**：落地提交的收集面＝整个 `docs/`（漏到 `docs/specs/` 的**契约哈希**会让钩子拦下，实测踩到）；
   补丁未落 ⇒ **不落报告**（否则"24 已修"落进判定面＝误导证据，实测踩到）；无内容可提交＝no-op 不是失败。

**本轮的排除项（需人工重做）**：`src/k3dit/tools/flowlint.py`（其修复与**我们后来**在同一函数里的条次归因
改动真冲突）与 `src/k3dit/tools/cleanup.py`（其修复与**当前**测试期望冲突）——`--exclude` 显式给、写进报告说明。

**纠正一处误登记**：我先前把"落地破消费仓评审登记规则（索引/归档）"写成跨仓流程问题 `FLOW-REVIEWS-01`——
框架错了。**k3dge 作为消费仓没有那套闸**（`docs/reviews/` 只有 README+AUTHORING 通用规约），那是 **k3dit 的仓规**，
修法也归 k3dit（已登记在它的 `LEFTOVERS.md`）。泛化后的判据见上面 `REVIEWS-LAND-01`：落地后**被落地仓的格式闸必须绿**；
它红了 ⇒ 由**该仓**提供规整器（k3ge 按声明调用），k3ge 不复刻别仓的登记规则。

## M11 首轮包**不可落**（2026-09-27）：审计之后又改了同文件 ⇒ 包过期（教训，非缺陷）

- **事实**：那轮（`/tmp/k3ge_m11c`，21 行：已修 11 + 待修 3 + 有意留 7）产包后，我为了修流程又改了
  **`audit_bundle.py` 与 `audit_merge.py`**——恰好就是该包 `fix.patch` 触及的**全部两个文件**。用新的
  hunk 级部分落地去落时，三路合并对这两个文件**都报真冲突**（`git merge-file` rc=2＝2 处冲突；此前
  把 `>1` 当错误码 ⇒ 一度误报"合并失败"，已修 `e5370ce`）⇒ **该包落不进**（不是"未关项"问题）。
- **教训（流程面）**：包是对**审计当时基线**生成的；**同一批文件在审计后又被改动 ⇒ 包即过期**。
  两条可行纪律：① 审计出包后**尽快落**（或先不动被审文件）；② 若要继续改同文件，就**别指望旧包**，
  以报告（`验证`列/升级标记）为准由人重做，或（需要时）重跑一轮——**重跑不是默认动作**（用户已明确"不重跑"）。
- **证据留存**：`/tmp/k3ge_m11c`（report/findings/pins/fix.patch 完整）+ 本文件 + 工具状态目录
  `<cache>/k3dit-state-<subj12>/`（席日志/账本；运行摘要机制见 `audit_bundle.write_run_digest`）。

## M11 报告**人工重做**（2026-09-27）：按报告逐条修进今天的代码（不靠落包）

用户裁定："既然落不了，你根据 review 报告来修"。**已修**（每条都有测试或既有测试覆盖）：

| 报告 ID | 动作 |
|---|---|
| code-1 | `apply_bundle` dry-run **前后取 (HEAD, status) 快照比对**，不一致 ⇒ `TREE_MOVED` 不真打 |
| code-2 | `_escaping_rels` 越界路径闸 ⇒ `APPLY_PATH_ESCAPE:<patch>`（并进"结构性失败"白名单，不退合并） |
| code-3 | `files` 由**补丁声明**推出（`patch_rels` 单源），不再拿 `git status --porcelain` 全量当审计产物 |
| code-4 | 删掉恒真谓词 `... or True`（过滤曾完全失效） |
| code-5 | `union_pins` 的 base 改**纯基线**（原为"基线+fix"⇒ 与 ours/theirs 不同基；顺带删 `if True`） |
| code-6 | base 在而 ours 缺 ⇒ 记 `missing`（fail-clear），不再以空文件三合出"成功但内容为空" |
| code-7 | 半落 ⇒ 降级合并前**逆序反向应用回滚**（`_rollback_applied`） |
| code-8 | 兑现契约另一半：暴露 `pins_rels` 单源 + 文档写清"钉由落盘方应用"（照原意再做一遍＝两份实现） |
| code-9 | （原"转 tasks"）**状态目录加固**：`mkdir 0700`、拒符号链接/非目录；不安全 ⇒ `K3GE_STATE_UNSAFE` + 拒绝启动 |
| code-10 | 失败面**不再硬编码 `applied: []`**：带真实 `applied/rolled_back/files` |
| code-11 | `_run` 改 `Popen(start_new_session=True)` + 超时 **`killpg` 进程组**；`OSError`＝127 与超时＝124 分开 |
| value-4 | `touched_files` 走 `patch_rels` 单源（送检面内曾三份同规则实现） |
| value-6 | 权威口径写清：`audit_verify.verify_bundle_local` 是**唯一实现**，`verify_bundle` 是稳定门面 |
| value-8 | `_owned_replay`：重放树**所有权显式**（本模块自建、调用方清理），`owner` 字段标出 |
| value-10 | 产物清单**显式化**：只认 `docs/generated` 与 `docs/specs`，不再盲扫整个 `docs/` |

**仍留（审计原判"有意留"，属结构性重构，需带测试面的独立批次）**：value-1（`apply_bundle` 相位拆分）、
value-2（with-worktree 上下文管理器，两处脚手架合并）、value-3（落盘重复单点化）、value-5（replay 结果缓存，
避免 O(补丁×钉文件) 次全量重放）、value-7（`audit_bundle` 四层拆文件）、value-9（`merge-file` 脚手架重复，原"待复验"）。

**注意**：那轮 M11 的**包本身仍不可落**（其 `fix.patch` 只触及的两个文件此后又改过 ⇒ 真冲突）；上面是
**以报告为规格的人工重做**，与"落包"是两条路。报告原文与包留档在 `/tmp/k3ge_m11c`。

## M11 k3dit bundle 审计轮（2026-09-28）：抢救包（超时 `hall export`）判 28 条 pending

本轮审计腿跑到墙钟被掐 ⇒ `entry=export` 抢救包，`待修=28`（全 pending，fix/review 窗未裁到闭环）。
干活侧逐条处置如下（ID 是 `2026-09-28-M11-k3dit-bundle-audit.md` 的行号，与 09-27 老批次同号不同事）。

**已修（有测试或既有覆盖）**：

| ID | 处置 | 消费者 / 证据 |
|---|---|---|
| code-1 / code-11 | 前提有误：缺 grammar 时 `extract()` `raise ImportError` **被 `engine/contract.py` 的 `except ImportError: pass` 当整语言 skip 信号**（never fatal）——docstring/README 的"silently skipped / broken plugin never reds the gate"与行为一致，只是两条规则缺先后声明。补 precedence 一句，不改行为。 | `.agent/extractors/README.md` L67；生成插件 docstring；`test_extractor_gen.py::test_skip_is_documented_as_gate_caught` |
| code-4 | 构造 `Language(ptr)` vs `Language(ptr,name)` 的 arity 差异只该 `TypeError` 兜；真实故障（ABI/import）不得被吞成降级分支（fail-silent→fail-closed）。 | `extractor_gen.py` 模板 `except TypeError:`；`test_language_arity_fallback_narrows_except` |
| code-6 | 忽略集补 `node_modules`/`vendor`/`coverage`/`out`/`.next`；`can_handle` 排除生成物 `.d.ts`/`*.generated.*`/`*.min.js`；`_PARSER` 模块级缓存，去掉每文件重复构造语法库。 | `test_generated_filtering::test_can_handle_skips_deps_and_generated` |
| code-9 | `_slice` 净化：丢 `\r`/控制字符、仅留 `\n\t`+可打印，消除 `decode(replace)` 的 U+FFFD/换行造成的 hash 漂移与被反向按行读入的注入面。 | `test_generated_filtering::test_slice_strips_control_and_cr` |
| code-7 | 声明面 `seal_record` `on_rerun=append` 担心的"两套基线"已被 git 事实幂等兜住：`tag_audit_baseline` 同指→绿/异指→拒、`_commit_all` 干净树不造空提交、judged 只读 tag+trailer（本地账＝投影）。补一条重入幂等证据测试，把"声明的失败分支"转成可复算凭据。 | `test_seal_record.py::test_reentrant_seal_record_is_idempotent` |
| code-3 | `rules/12` 裸名 `engine/doc_fix.py` / `test_doc_fix.py` → 全路径（与同段 `src/k3dge/engine/nextstep.py` 精度一致）。copy + template 同改。 | `.agent/rules/12-introduction-discipline.md` L71/L76 |
| code-12/13/14 | `.ua/.trash-1789420608/tmp/*.py` 是 understand skill 的一次性垃圾（`.ua` 已 gitignore、不入库、不属版本化契约）。审计 stage 复制整树才会扫到。删除该 trash 目录，三随消。 | 工作树删除（gitignore，零契约影响） |
| doc-1 | `extractors/README.md`「## 2. Hand-written」示例缺开栏围栏 ⇒ 补。 | `.agent/extractors/README.md` L47 |
| doc-4 | `rules/01` item2 短名 `AUTHORING.md`/`_template.md` → `docs/<type>/…`（与同行 `.schema.json` 一致）。copy+template。 | `.agent/rules/01-docs-structure.md` L2 |
| doc-6 | `extractors.toml` 头注释与生成头 `engine/extractor_gen.py` → `src/k3dge/engine/extractor_gen.py`。 | `.agent/extractors.toml` L1；`extractor_gen.py` 渲染行 |
| doc-7 / doc-8 | `rules/04` 同文件内指针风格不一：`LEFTOVERS.md`/`audit_jobs.json`/`audit_checklist.json`/`pipeline.toml`/`nextstep`/`audit_trigger` 裸名 → 全路径；`peer_contract` → `docs/protocols/peer_contract.md`。`SUMMARY.md` 不动（ADR-0018 反指它不该存在）。copy+template 同步。 | `.agent/rules/04-milestone.md` L12/L15/L21/L39 |
| doc-10 | `AGENTS.md` 路由句 `AUTHORING.md` → `docs/<type>/AUTHORING.md`。 | `AGENTS.md` §路由 |
| doc-13 | `docs/README.md` 把 AGENTS §Docs 的 write/find/schema 四条**逐条重写**＝双写漂移源（doc-7/8/9 的悬空裸名正出在这份副本）。收敛为"目录角色表＋一行指向 `AGENTS.md`"（规则 10：下沉单一源，别复写散文）。 | `docs/README.md` |
| doc-14 | `AGENTS.md` 审计建议触发行只写"账齐/C2≥5/体积≥8"无口径。补**指针**（不复写定义）：口径见 `src/k3dge/engine/audit_trigger.py` 模块 docstring，阈值取 `[gates.audit_trigger] c2_nesting_max/volume_max`——改数改这一处。 | `AGENTS.md` §12 表；`src/k3dge/engine/audit_trigger.py` |

**仍留（有意保留，附判据）**：

- **code-2 / code-5 / code-8 / code-10（TS 抽取精度）**：brace-language 启发式的已知失效面（第一个 `{` 一刀切会截 `Record<string,{a:number}>`、lexical 分支靠 `"function"` 子串嗅探、只走顶层一层、`_container_signature` 不对 `ERROR/MISSING` 告警）。**不臆改**：生成器纪律明写"node types 必须实测、绝不猜"，本环境无 `tree-sitter` 且仓库 **0 个 `.ts/.tsx/.js`** ⇒ 零实际面、改了也无法证伪。已在 `src/k3dge/engine/extractor_gen.py` 模块 docstring 逐条写明失效面＝把限制沉到事实源。正解归一个装了 grammar + golden TS 样本的独立批次。
- **doc-2 / doc-3（`.agent/README.md` 相对名 "Rule 02"/"docs.toml"）**：该 README 通篇在 `.agent/` 目录语境下列本目录成员（`manifest.json`/`rules/*.md` 同样相对名），且文件自声明「不要把这里当 Agent 入口 / 由 AGENTS.md 给出具体路径」（ADR-0010）。补 `.agent/` 前缀反而与全表不一致，属设计。
- **doc-5（`rules/00` `src/<domain>/` vs `package_root`）**：`src/<domain>/` 是模板对**下游任意 package_root** 的示意写法（`templates/assets/rules/00` 与本仓 copy 同源）；把 `src/k3dge/` 焊进模板会破坏 scaffold 可移植性。本仓真实包根由 `manifest.json` `package_root` 定义、不变量由 `k3dge check` 强制。示意≠缺陷。
- **doc-9（rules 04-11 缺"Protocol slice…AGENTS.md wins"头）**：该 precedence 已在 `AGENTS.md` 全局声明（"`.agent/rules/*` are slices; this file wins"）。往 8 份文件各贴一遍＝把全局规则复制成散文，正是规则 10（结构优先于散文）要避的。00-03 上的头是历史遗留，非须补齐的不变量。
- **doc-11（`AUDIT-QWEN-STATUS.md` 引用外部 `models.json`）**：根级一次性排障笔记，非 `docs/<type>/` 受管面；删/移入库文件归仓主裁定，不由审计轮动。
- **doc-12（`CHANGELOG.md` 引用已删 `scripts/lib/schema_check.py`）**：CHANGELOG 条目是**历史事实**（当时存在），裸名是当时的写法；改历史条目不如让下一版封版由提交区间重生。

## M11 封板二跑（2026-09-29）：外层墙钟再掐 + `DIRTY_TREE`（记账）

**事实**：`k3dge milestone seal M11` 二跑约 2h 被 k3dge 自家墙钟掐断，`hall export` 抢救出 `incomplete`
包（31 条全 `pending`，`fix/review` 未裁到闭环），消费侧判 `refused`、落包又撞 `DIRTY_TREE`。报告落 `4bff983`。

**根因（两条，皆结构性）**：
- **k3dge 外层墙钟 ≠ k3dit 探针**：`[roles.audit] k3dit_timeout`（full 缺省 `7200`s）是 `audit_bundle._run`
  对整条 `k3dit audit` 子进程的平铺 `communicate(timeout=)`，到点 `killpg`；与 k3dit 席位层
  `stall_after_sec` 探针是两层——探针只判单席死活，管不到外层天花板。整仓审计（`k3dit_scope=""`）
  仅 doc 窗就 59 片 ≈ 2h，`code/value/fix/review` 根本没跑。
- **`DIRTY_TREE`**：`.agent/audit_checklist.json` 是 **tracked** 运行态投影，`run_audit_flow` 开跑即重写
  （`src/k3dge/engine/milestone_audit.py:567` → `audit_checklist.reset_for_audit`），`apply_order` 非空时
  `audit_bundle.apply_bundle` 的 `git status --porcelain` 必然看见它 ⇒ 有补丁可落的封板必被挡。
  （M10 能封，是因为其包 `apply_order` 为空、`apply_bundle` 在脏树判据之前就早返回。）

**本轮处置**：`k3dit_timeout = "21600"`（6h）兜住整仓一轮（`.agent/pipeline.toml` + `templates/assets/pipeline.toml.template` 同步，漂移闸要求两者一致）。

**仍留（需独立批次；reopen 条件见各条）**：
- **外层墙钟改探针口径**：把 `_run` 的平铺超时换成**认探针的活性上限**（盯 `K3DIT_HALL_ROOT`/`K3DIT_LEDGER`
  的 mtime 或账本 `events[].ts`；静默超阈值才 `killpg`，否则续等），另留一条可选硬上限当成本天花板。
  与 k3dit 的 `stall_after_sec` 同口径。配 ADR + 测试（慢但推进不杀 / 真静默才杀）。
- **`audit_checklist.json` 运行态投影不该 tracked**：应像 `.agent/audit_jobs.json` 一样 gitignore（AGENTS.md
  已称其"运行态投影，非判据"）；否则只要审计要落补丁，封板必撞 `DIRTY_TREE`。或让 `apply_bundle` 的脏树
  判据显式豁免该投影。

---

## 符号索引陈旧判定的成本（2026-09-30，OCR 中批 ocr-316 有意留）

**事实**：`search._is_stale_cheaply` 每次 `where` 都要遍历域 src 树取「文件集 + 最新 mtime」；
函数名叫「廉价」，实为 O(树大小) 的 readdir + stat。本轮已把它从 `rglob`+逐文件 `stat()` **两趟**
并成 `os.walk` **一趟**，并加了文件集签名侧车 `.k3dge/symbol-index.meta.json` 解决删除/重命名
看不见的问题（ocr-315）。

**仍留**：再往下只有**增量化**（目录签名/树 hash + 只 stat 可疑目录）。不做进程内 memo——
freshness 判定**不能跨决策缓存**：内容编辑不改索引 mtime，memo 会把"已改"判成"未改"，
正是本轮要修的错。增量化是新机制，按 `.agent/rules/12-introduction-discipline.md` 需先有
实测消费者（万级文件仓的 `where` 延迟数据）再动。

**reopen 条件**：出现真实消费者（MCP/长驻进程反复 `where` 的 profiling 显示 stat 遍历占大头）。

---

## 兜底搜索的正则没有回溯保险（2026-09-30，OCR 中批 ocr-320 残留）

**已修的部分**：`search._python_search`（rg 缺席时的兜底）以前**没有任何截止时间**
——`_run_ripgrep` 的 30s 超时也返回 `None` ⇒ 立刻接一次无上限全仓扫描。本轮加了
遍历预算（`_FALLBACK_BUDGET_SEC`，到点即停并 WARN"结果可能不完整"）与单行探测上限
（`_FALLBACK_LINE_CAP`，超长行只喂前 4000 字符给正则）。

**仍留**：`re` 本身没有回溯保险，`(?=(a+))+` 一类查询在**单行 4000 字符内**仍可长时间挂住。
彻底解法要么换成线性时间引擎（`re2`/`google-re2`，引入外部依赖 ⇒ 需 ADR），要么把兜底
降级为**只做子串**（放弃与 rg 的正则等价性，会退回 code-7 那类命中集分歧）。

**reopen 条件**：出现真实消费者（无 rg 环境下由恶意/失手 query 造成的挂死报告），
或决定引入 re2（那时按 `.agent/rules/12-introduction-discipline.md` 配完整实测正向作用）。

