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
| PRE-01 | 引用闸（悬空 ADR / 名实一致 / markdown 完整性）**只在提交时**生效（`ADR-0022 §2.2 🅰1`：`pre-commit` 是格式硬闸、`check` 恒静态）；机械提交（审计线/封版的 `--no-verify`，`worktree.py:104`/`seal.py:408`）与 CI 的 `check` 都不跑它。有意留：判定归“提交那一刻”，不因此在 `check` 里长第二份判据面 | [2026-09-21-hookization-surface-inventory.md](../memo/2026-09-21-hookization-surface-inventory.md) |
| FSM-01 | `state_machine.resolve()` 无生产消费者：状态转移在生产路径上由 `task done` 直写 status + align/seal 事后验合法性（`_ALLOWED_STATUS`）承担。`TRANSITIONS` 反而已有消费者（`summary()` → `k3dge status --json` 观测件）⇒ 表留、`resolve()` 留（删无收益；补“两处相等”类守卫是同义反复） | 同上 |
| value-22 | `cli/main.py` 单模块超千行（ADR-0003）：体积属实，按 A-1 分块逐程消化，本轮有意留 | [2026-09-20-M10-audit.md](archive/M10/2026-09-20-M10-audit.md) |
