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

`docs/reviews/LEFTOVERS.md` + `docs/architecture/overview.md` §8 先读，不重提已修/有意留。

## Constraints

L2 入场券须逐条确认（agent 进车间前绑定到任务）：

- 交付物写入 `docs/reviews/YYYY-MM-DD-<scope>.md`，表头 12 列 `ID|日期|严重度|优先级|类型|问题描述|位置|状态|处置|验证|复审|验收`
- 5-Pass 透镜逐轮独立执行（健壮安全 / 架构边界 / 设计契约 / 一致验证 / 性能简洁）
- 前置先读 `docs/reviews/LEFTOVERS.md` 与 `docs/architecture/overview.md` §8
- 每行 `状态 ∈ {已修, 待修, 有意留}`；`复审 ∈ {待复审, 通过, 驳回}`；`验收` 为 `验收人 YYYY-MM-DD [#reason]`

## Doc Audit（文档审计，per-type，文档变动时）

> **与 5-Pass 同源**：本节是同一份 k3dit 审计协议的一个 **scope**——代码走 5-Pass，文档走本节。二者由同一 peer（k3dit）执行、同一 12 列报告、同一 `on_pre_seal` verify，不是第五域、不另起 harness（ADR-0020）。`k3dge` 只**指路**（同一个审计 prompt，按 `target_scope` 路由到本节）并**提供事实**（`k3dge_adr_index`），不执行、不判。

**触发**：文档改动时（非里程碑），与代码改动走同一条 `k3dit.actions.audit` 链；`target_scope` 为文档类型时即套用本节。不审"思想打分"（那归 k3lity，里程碑软审）。

**per-type 透镜**：
- **ADR — 集合自洽（冲突 / 覆盖）**：两篇 *未 superseded* 的 ADR 不应无声共享 scope / decision-topic（冗余）；指针须完整——`Supersedes`/`Related` 不悬空、被取代的 ADR 不再被当现行引用。事实来自 `k3dge_adr_index`（AdrIndex + O(n) 重叠/指针 findings，**非判断**）；冲突/冗余由 k3dit 判。
- **通用 — AUTHORING 规则合规**：改动文档须符合其类型 `AUTHORING.md`（结构已由 `.schema.json` 硬闸；此处审"是否真按软规则写"）。

**不审**：文本质量（写得好不好 → k3dit LLM 部分）、思想是否值得（→ k3lity 里程碑软审）。文档审查 ≠ 给思想打分。

**k3dge 提供的事实工具**：`k3dge_adr_index`（ADR 索引 + 重叠/指针 findings JSON，**非判断**；冲突/冗余由 k3dit 判）。

> **k3dit 可达时**：k3dit 应使用含本节的同源协议（其 `protocol.md` 须含本节，与本文同源）；k3dit 不可达时回退到本仓 `docs/protocols/audit_default.md`（即本节所在文件）。
