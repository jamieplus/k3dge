---
Status: Accepted
Supersedes: -
Amended-by: -
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
- 某 `Milestone` 下 `docs/tasks/` 顶层条目全部 `Status: done` → 当轮 `k3dge milestone align <id>`（Full Matrix，无人问）。
- align 通过不等于可封：下一步是建议审计（§2.1.4），不是建议封板。

### 2.1.3 封板闸机
- 机器闸（reviews 文件）：含 `align-pass`、不含 `align-stub`、正文列出该里程碑全部任务、`docs/guides/` 无 `guide-stub`。
- 资格闸：由 `audit_trigger.audit_closed` 判（审计闭环、`待修=0`，§2.1.4/§2.1.7）；未闭环时 `seal` 返回 `audit_needed`。
- 不读 `docs/reviews/SUMMARY.md`（禁止手维护类型索引，ADR-0018）；有意留只在 `docs/reviews/LEFTOVERS.md`。

### 2.1.4 两问拆分：审计是界限，封板只是收摊
- **封板没有尺子**：全 done、硬闸绿、甚至零 task 都能被说成"可封"；封板只是归档+版本+指针，不构成界限。
- 真正的界限是**审计闭环**（定义见 §2.1.6）；之后问封不封，是在问"要不要压缩上下文收摊"。
- **问题一·要不要审（可量化触发，§2.1.5）**：
  - `check`(绿) / `task done` / `align` / `status` 命中定量信号 → `[NEXT] audit_suggested` + reasons；人只答要不要审。
  - 答是 → `k3dge milestone audit <id>`：必审 → `待修>0` 问 agent 修（倒计时默认修）→ 重审；`>3` 次未闭环 → `escalated` 转人工。
- **问题二·要不要封（仅审计闭环后唯一一次）**：
  - `待修=0` 且有报告 → `[NEXT] seal_ready`；`k3dge milestone seal <id>` 才问"封板？(y/N，无倒计时)"。
  - 未审计先调 → `audit_needed` 指回 audit；答是 → align → 归档+版本+指针 + `*-closure.md` 收摊清单；答否 → 不封。
- **空窗 / 零 task / 只是硬闸绿**：不建议审、也不建议封。
- **有意留不算待修**：进 `docs/reviews/LEFTOVERS.md` 即可往下走。
- **k3dge 只调透镜、不自己审**：sidecar 与署名见 ADR-0006 §2.3.6，审计模块见 ADR-0025 §2.2；同一 agent 不得自审自封（fallback 到 `manual` 由人工复核除外）。
- **倒计时只出现在"有待修、agent 是否动手"**：超时默认"开修"，不跳过审计。
- **封板动作＝收摊/上下文压缩**：`seal` 机械部分只做归档+版本+指针。
  - `run_seal_flow` 写 `docs/reviews/<date>-<id>-closure.md` 清单，指引补齐落盘失败/未采用方案、清理上下文、更新设计文档、提交里程碑。

### 2.1.5 审计建议的量化尺子（§2.1.4 的触发条件）
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
- **闭环界定**：报告 `待修=0` 即 `audit_trigger.audit_closed`；改后由 `verify` 核该报告。
- **`[NEXT] pending_findings`**：
  - `scan_pending_findings` 扫 `src/`+`docs/`（跳 archive/reviews/generated）的 `k3dit:pending` 钉（语法见 `peer_contract §8`）。
  - `check`/`status` 以最高优先报 `pending=N`——修的人打开文件就看见。
  - 往配对模板里插注释仍会误触 `TEMPLATE_DRIFT`。

### 2.1.7 人工入口 / Checklist 缓存 / 自动 loop 上限
- **人工主动入口**：`k3dge milestone audit <id>` 与 `k3dge milestone seal [--yes] <id>` 走同一套 `run_audit_flow` / `run_seal_flow`。
  - `--yes` 仅跳过"要不要封"提问，不跳过审计（未闭环时 `seal` 返回 `audit_needed`）。
  - 自动探测（`[NEXT] audit_suggested` / `seal_ready`）与人工入口收敛到同一条流程。
- **审计条件 Checklist 缓存（非封板 checklist）**：`.agent/audit_checklist.json` 记条件快照（账齐/C2/体积 + reasons）、报告的 `待修`、`verify_attempts`、`audit_started_at`，以任务状态 hash 为键。
  - `check` 只读缓存、任务集不变不重算；`milestone audit` 发起时重置（预算归零 + 打 `audit_started_at`），人工/自动重跑各拿一个新的 3 次预算。
- **自动 loop 上限**：`run_audit_flow` 里 `verify` 连续 >3 次未闭环 → `escalated`，停止自动 loop、转人工。

### 2.1.8 外来审计源落盘
- 人把报告贴进对话框（或 agent 转发）＝**外部审计源**，不能直接被流程解析。
- 必须落盘为 `docs/reviews/YYYY-MM-DD-<id>-external-audit.md`：`k3dge milestone audit-submit <id> [--file <报告.md> | -]`（CLI）或 MCP `k3dge_submit_audit_report`。
- `persist_external_audit_report` 缺 12 列表头时自动补；最新一份覆盖旧的。
- 落盘后 `audit_closed` 即可判闭环，进入"问题二·要不要封"；外部源与 peer 产出走同一条路径。

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
- **seal 联动**：`seal` 成功自动 `patch` bump + CHANGELOG 条目（`Seal milestone <id>.`）；`--no-version-bump` 可跳过；CLI 与 MCP 行为一致。
- **失败语义**：`bump_version` 原子；`seal` 后自动 bump 失败**不回滚已归档 tasks**，仅 stderr / MCP `version_bump_failed` 告警——禁止"归档成功、版本一半"被静默忽略。
- **不引入** hatch-vcs / setuptools_scm（自举期 `pip install -e` 已满足）。重开条件：需 `git tag` 驱动或 PyPI 发布。

## 3. 产生后果 (Consequences)
- **正面**：确定性验收 + 防过度工程 + 上下文经济性闭环；`engine` 扩展为"门禁判定与生命周期治理核心"（边界见 `overview.md` / `engine/spec.md`）。
- **负面**：`engine` 引入文件生成/移动副作用，需与 `sync` 的 spec 回写职责保持边界（`engine` 管归档，`sync` 管契约）。
