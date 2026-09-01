---
Status: Accepted
Date: 2026-08-23
Deciders: Core Maintainer
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

* **Micro Gate**（日常提交）：`L0/L1` 快速阻断（`k3dge check`）。`k3dge check --with-tests` 是 **selective L2**（只跑 git 触及域的矩阵测试），不是 Full Matrix。
* **Macro Gate**（里程碑对齐）：`k3dge milestone align` 对 `manifest.domains` 做 **Full Matrix** 全域结构 + 契约 + 矩阵测试。
* **重构准入**：仅当命中 `C1 扩展硬阻塞 / C2 坏味道严重超标 / C3 契约漂移未愈`
  时才允许定向微调；否则严禁大重构。

### 2.1.1 修正（2026-08-24）
原稿把 Macro Gate 写成「`k3dge check --with-tests` 的全量触发」。实现上 Full Matrix 只在 `milestone align`；`--with-tests` 始终是增量域。以本节现稿为准，勿按旧句实现。

### 2.1.2 触发（Agent，无需用户提醒）
某 `Milestone` 字段下，`docs/tasks/` 顶层条目全部 `Status: done` → 当轮 `k3dge milestone align <id>`。align 通过后：去掉 align-stub、保留 align-pass。接着 `HUMAN_CHECKPOINT`：`y` 走审计，`N`/60s 在无 `k3dge:guide-stub` 时 `seal`。见 AGENTS.md §12 / ADR-0008。

### 2.1.3 封板闸机（2026-09-01）
`seal` 机器闸是：对应里程碑的 reviews 文件含 `align-pass`、不含 `align-stub`、正文列出该里程碑全部任务、`docs/guides/` 无 `guide-stub`。不读 `docs/reviews/SUMMARY.md`（禁止手维护类型索引，ADR-0018）。有意留只在 `docs/reviews/LEFTOVERS.md`。

### 2.2 为什么通过文件系统物理移动实现上下文压缩
`k3dge milestone seal` 将 `docs/tasks/*.md` 物理移入 `docs/tasks/archive/<id>/`。
`k3dge task list` 只扫顶层活跃文件，`archive/` 不在扫描面——Token 零浪费的上下文重置，且符合 `docs/tasks/archive/` 的 append-only 审计需求。

同一次 `seal` 把本里程碑的 `docs/reviews/*.md`（文件名含该 id，或正文含 `<!-- k3dge:align-pass:<id> -->`；文件名属其他里程碑的不动）移入 `docs/reviews/archive/<id>/`，并把 `docs/reviews/LEFTOVERS.md` 里的相对链接改写成 `archive/<id>/…`。失败则回滚文件移动并还原 LEFTOVERS.md。`k3dge doc list` 默认不扫 `archive/`。

### 2.2.1 修正（2026-09-01）
原稿只归档 tasks。reviews 同属 append-only 证据，顶层堆积会把 leftovers 寻址和当前里程碑报告混在一起。以本节现稿为准。

## 3. 产生后果 (Consequences)
- **正面**：确定性验收 + 防过度工程 + 上下文经济性闭环；`engine` 域由纯判定
  扩展为"门禁判定与生命周期治理核心"，职责边界在 `overview.md` 与 `engine/spec.md`
  中显式更新。
- **负面**：`engine` 引入文件生成/移动副作用，需与 `sync` 的 spec 回写职责保持
  清晰边界（`engine` 管任务归档，`sync` 管 spec 契约）。
