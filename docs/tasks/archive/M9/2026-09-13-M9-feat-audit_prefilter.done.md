---
status: done
milestone: M9
priority: P2
date: 2026-09-13
---

# §7 审计复用预筛：milestone audit 人工入口短路

- **Status**: idea
- **Milestone**: M9
- **Priority**: P2
- **Date**: 2026-09-13

## 已确认意图
`k3dge milestone audit <id>`（**人工入口**，非自动）在满足三条件时告知"无审计需要执行"并提示 `--force`；痕迹 `PRE-FILTER` 落 `logs/k3dge.log`。自动入口不预筛（`peer_contract §7`）。

## 可检索摘要
沿用 `ratchet_real_run_backlog` 剩余项①：`peer_contract §7` 有规范、代码无实现。三条件＝①闭环报告存在；②其 `provenance.baseline` == 线上基线；③其 `provenance.lens_version` == k3dit 当前发布值。

## 上下文/切入点
- 规范源：`docs/protocols/peer_contract.md` §7（CAS 复用与锁）。
- 痕迹格式：`PRE-FILTER action=audit verdict=closed|run key=<baseline>@<lens_version> src=<报告路径>`。
- **卡点（跨仓）**：条件③需 k3dit 发布"当前 `lens_version`"的取数源（契约称"peer 只新增这一项义务、无需新 RPC"）——须先在 k3dit 侧定该值从何而来。
- 边界：预筛只做**形式短路**、不解释 peer 内部（`ADR-0006`）；不制造新状态（闭环仍由 `audit_closed()` 判）；`--force` 随时可破。

## 边界与拆分
- 事实归属：报告 `provenance` 拥有 baseline/lens_version；预筛逻辑归 `engine/audit_flow.py`（人工入口）；k3dit `lens_version` 发布值归 peer。
- 桩子先行：先落"报告存在 + baseline 相等"的形式短路（条件①②）＋ `--force`＋`PRE-FILTER` 痕迹；条件③待 k3dit 侧就绪再接，未就绪则**不短路**（保守＝照跑）。

## 收尾（2026-09-13 拆出跨仓）
- 拆出 k3dit `feat-report_provenance`（前置：报告落 `baseline`/`lens_version`）；本票待其就绪后在 k3ge `run_audit_flow` 实现预筛。
