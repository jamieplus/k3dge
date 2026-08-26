# Reviews — 审计报告归档

Agent 对本仓的代码审计/评审结果的**唯一存放地**。点时快照，append-only：
原文不改写，后续进展以追加"情况"列或新小节记录。

## 索引

| Date | Scope | 报告 | 摘要 | 发现 | 处置 |
| --- | --- | --- | --- | --- | --- |
| 2026-08-21 | 全仓逐行三轮 | [2026-08-21-line-by-line.md](2026-08-21-line-by-line.md) | L1 签名缺参/TS 兼容等15项已修，3项冗余有意留 | 18 | 15 已修 / 3 有意留 |
| 2026-08-23 | 一致性+逻辑冗余 | [2026-08-23-consistency-logic.md](2026-08-23-consistency-logic.md) | 双轨门禁/状态机/架构图等5项 + 死代码/双重AST等3项已修，2项有意留 | 10 | 8 已修 / 2 有意留 |
| 2026-08-23 | 5-Pass 合并版 | [2026-08-23-5pass-audit.md](2026-08-23-5pass-audit.md) | 15 项全闭环（13 已修/2 有意留，合并 #7q3d9-a19 + #8d4m2-a1） | 15 | 13 已修 / 2 有意留 |
| 2026-08-24 | 5-Pass 全量复核 | [2026-08-24-5pass-audit.md](2026-08-24-5pass-audit.md) | 封板子串误放行+manifest崩栈已修；MCP全量语义/align复制L2/TS哈希等转 tasks | 12 | 2 已修 / 8 转 tasks / 2 有意留 |
| 2026-08-24 | 8维+Vibe 增量 | [2026-08-24-8dim-vibe-audit.md](2026-08-24-8dim-vibe-audit.md) | 新发现：L2 None崩栈/路径逃逸/假回滚/封板绕过/无测试即缺陷；无密钥与注入 | 12 | 0 已修 / 10 转 tasks / 1 并入0001 / 1 有意留 |
| 2026-08-24 | 更新后 8 维 | [2026-08-24-post-update-8dim.md](2026-08-24-post-update-8dim.md) | version/ADR；回记 U-01..U-07 已修 | 7 | 7 已修 |
| 2026-08-24 | 脚手架门控锁 | [2026-08-24-scaffold-gate-lock.md](2026-08-24-scaffold-gate-lock.md) | TEMPLATE_DRIFT 进 check；下游误伤未关 | 4 | 2 已修 / 1 部分修 / 1 已修 |
| 2026-08-24 | M0 对齐验收 | [2026-08-24-M0-align.md](2026-08-24-M0-align.md) | 19 条 done 任务 Full Matrix PASS，准予封板 | 19 | 封板 |
| 2026-08-25 | M1 对齐验收 | [2026-08-25-M1-align.md](2026-08-25-M1-align.md) | 14 条 08-25 审计任务 Full Matrix PASS，准予封板 | 14 | 封板 |
| 2026-08-25 | Pass 1 健壮性 | [2026-08-25-pass1-robustness-security.md](2026-08-25-pass1-robustness-security.md) | 空 ignore/`UnicodeDecode`/路径绕过/`rglob` 符号链接等 9 项 | 9 | 7 转 tasks / 2 有意留 |
| 2026-08-25 | Pass 2 架构 | [2026-08-25-pass2-architecture-dag.md](2026-08-25-pass2-architecture-dag.md) | `engine→templates` 逆孤岛、`audit triage` 违 ADR 0005 | 10 | 2 转 tasks / 7 并入 / 1 有意留 |
| 2026-08-25 | Pass 3 设计 | [2026-08-25-pass3-design-abstraction.md](2026-08-25-pass3-design-abstraction.md) | `D-04` 文件名哈希污染等 12 项 | 12 | 1 转 tasks / 11 有意留 |
| 2026-08-25 | Pass 4 一致性 | [2026-08-25-pass4-consistency-alignment.md](2026-08-25-pass4-consistency-alignment.md) | 矩阵缺列等 9 项 | 9 | 3 转 tasks / 5 有意留 / 1 通过 |
| 2026-08-25 | Pass 5 简洁 | [2026-08-25-pass5-simplicity-performance.md](2026-08-25-pass5-simplicity-performance.md) | MCP 双取等 8 项 | 8 | 1 转 tasks / 6 有意留 / 1 通过 |
| 2026-08-25 | k8d3e-a4 穿透 | [2026-08-25-k8d3e-a4-fix.md](2026-08-25-k8d3e-a4-fix.md) | 5 项 P1 已修（`diff`/`generator`/`version`/`milestone`/`scaffold`） | 8 | 5 已修 / 3 有意留 |
| 2026-08-25 | Pass 3 设计 | [2026-08-25-pass3-design-abstraction.md](2026-08-25-pass3-design-abstraction.md) | `D-04` 文件名哈希污染；其余抽象债有意留 | 12 | 1 转 tasks / 1 并入 / 10 有意留 |
| 2026-08-25 | Pass 4 一致性 | [2026-08-25-pass4-consistency-alignment.md](2026-08-25-pass4-consistency-alignment.md) | 矩阵缺列/`VERSION_MISSING` 误引；P4-04 并入 D-04 | 9 | 3 转 tasks / 1 并入 / 4 有意留 / 1 通过 |
| 2026-08-25 | Pass 5 简洁 | [2026-08-25-pass5-simplicity-performance.md](2026-08-25-pass5-simplicity-performance.md) | MCP 双取；其余规模阈值未到 | 8 | 1 转 tasks / 6 有意留 / 1 通过 |

> 新增报告时在此表与 `SUMMARY.md` 同步追加；Agent 先读 `SUMMARY.md` 定相关性，再按需读单篇。

## 命名与结构

`YYYY-MM-DD-<scope>.md`（如 `2026-08-21-line-by-line.md`）

```markdown
# 审计：<范围>

- **Date**: YYYY-MM-DD
- **基线**：commit/tests 状态快照
- **审计人**：...

## 发现

| ID | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R1-1 | 高 | P0 | 缺陷 | ... | `file:line` | 已修 | ... | `gate PASS` |
| R1-2 | 中 | P1 | 冗余 | ... | `file:line` | 有意留 | ... | 本报告为证 |

## 结论
```

## 纪律

- **处置三选一**：已修 / 转为 `docs/tasks/` 条目（链接回本文）/ 有意留（必须写否决理由）
- 未修且未否决的发现不得只留在报告里——必须转 tasks，否则丢
- 新一轮审计前先读本目录，避免重复报告同一问题或重提已被否决的项
- **现行有意留的否决理由与失效条件**以 [`docs/architecture/overview.md`](../architecture/overview.md) §5.1 为唯一常驻表；`SUMMARY.md` 顶部有 ID 索引。单篇报告只保留当时的点时快照，不替代 §5.1
- 本目录不进门禁、不要求 Status/Priority（它是证据档案，不是工作项）
