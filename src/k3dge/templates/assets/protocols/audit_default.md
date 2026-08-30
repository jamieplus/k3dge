# Audit Protocol — Default (5-Pass / 8 维)

> **事实源**：`k3dge` 仅验"报告有无"（`k3dge check`），透镜判断在本文件；`k3dit` 的 `protocol.md` 优先于本文件。

## 交付

`docs/reviews/YYYY-MM-DD-<scope>.md`，表头 12 列 `ID|日期|严重度|优先级|类型|问题描述|位置|状态|处置|验证|复审|验收`（`状态∈{已修,待修,有意留}`；`复审∈{待复审,通过,驳回}`；`验收` 为 `验收人 YYYY-MM-DD [#reason]`）。

## 5-Pass 透镜（一次一轮）

**Pass 1 — 健壮性与安全**：边界/空值/正则/子进程超时/事务回滚/注入/密钥 + Vibe `SQL/eval/pickle`
**Pass 2 — 架构与边界**：`DAG` 单向/内聚/分层/违 `ADR` + Vibe 分层割裂
**Pass 3 — 设计与契约**：策略多态/入出参/展示与核心解耦 + Vibe 过度设计
**Pass 4 — 一致性与验证**：状态/缓存/跨平台/时序 + Vibe 幻觉 `API`/`try/pass`，**无测试即缺陷**
**Pass 5 — 性能与简洁**：死代码/重复 `IO`/热循环/`N+1` + Vibe 循环内 `IO`

> 8 维叠于对应轮，不另起互斥清单；`k3dge check` 指纹/多轨同构等仍按 `Pass 4` 原条目。

## 前置

`docs/reviews/SUMMARY.md` 顶部常驻表 + `docs/architecture/overview.md` §8 先读，不重提已修/有意留。

## Constraints

L2 入场券须逐条确认（agent 进车间前绑定到任务）：

- 交付物写入 `docs/reviews/YYYY-MM-DD-<scope>.md`，表头 12 列 `ID|日期|严重度|优先级|类型|问题描述|位置|状态|处置|验证|复审|验收`
- 5-Pass 透镜逐轮独立执行（健壮安全 / 架构边界 / 设计契约 / 一致验证 / 性能简洁）
- 前置先读 `docs/reviews/SUMMARY.md` 顶部常驻表与 `docs/architecture/overview.md` §8
- 每行 `状态 ∈ {已修, 待修, 有意留}`；`复审 ∈ {待复审, 通过, 驳回}`；`验收` 为 `验收人 YYYY-MM-DD [#reason]`
