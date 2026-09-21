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

