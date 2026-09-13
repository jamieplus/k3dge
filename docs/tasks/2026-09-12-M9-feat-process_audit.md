---
status: done
milestone: M9
priority: P2
date: 2026-09-12
---

# 过程审计面（SQA）：里程碑证据链时间序/完整性入硬闸契约

- **Status**: done
- **Milestone**: M9
- **Priority**: P2
- **可检索摘要**: 补 SQA 语义的"过程审计"——不只查"声明↔代码"，还查"声明↔流程"（审计在改码之后、报告被验收过）；作硬闸契约里一条 gate rule。
- **Date**: 2026-09-12

## Intent
里程碑证据链的**时间序/完整性**成为一条闸：报告 `provenance.baseline`==线头、审计发生在 `fix_base` 之后、report 被 review 署名；并查**已修缺陷是否有 RCA 回灌记录**（industry §2.3 过程审计侧，消费 k3che `record_rca`）。

## 上下文/切入点
- 来源：memo `docs/memo/archive/2026-09-05-industry-benchmark-vs-4-harness.md` §2 缺项1。
- 现状：`check` 只查契约哈希/spec 结构/证据存在，**不查时序**。
- 落点：硬闸契约 gate（如 `[checks.seal]` 加 `evidence_chain_ordered`），执行器读契约跑。

## 边界与拆分
- 事实归属：时序事实来自账本 `events`/`provenance`（k3dit 账 + k3dge job state）；闸归 k3dge。
- 边界检查：只验时间序/存在性，**不判审计质量**（归 k3dit）。
- 桩子先行：先用现有 events/provenance 造 fixture，断"乱序红 / 正序绿"。

## 验收
- 契约多一条 gate；乱序或缺验收的里程碑 `seal` 被拒；正序过。

## 收尾（2026-09-13 已落·确定性子集）
- 新增 `engine/process_audit.py :: evidence_chain_error`：里程碑闭环 12 列报告**署名完整**（`审计人`/`透镜来源` 非空）＋**已入库**（git 跟踪）→ 否则拒。
- 接入硬闸契约：`[checks.seal].preconditions` 增 `evidence_chain`（`gates.DEFAULTS` + `.agent/gates.toml`），`seal_preconditions_error` 加该闸。
- 测试 `test_process_audit.py`（完整+入库过 / 缺署名拒 / 未入库拒）＋ `test_gates` 预期更新。293 passed。
- **未落（归 k3dit，k3ge 无事实源、显式不臆造）**：①审计线强时序（`provenance.baseline`==线头、`lens_version`==当前、审计在 `fix_base` 之后）；②"已修缺陷 RCA 回灌"检查（消费 k3che `record_rca`）。待 peer 落地后扩展。
