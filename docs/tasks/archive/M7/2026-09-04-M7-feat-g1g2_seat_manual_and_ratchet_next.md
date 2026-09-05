---
status: done
milestone: M7
priority: P1
date: 2026-09-04
---

# 真跑前置：席位工单棘轮化 + ratchet_open 路由

- **Status**: done
- **Milestone**: M7
- **Priority**: P1
- **可检索摘要**: 十单收口后清点"真正跑一次审计"的缺口：G1 k3dit seat_prompt 还是 v2 一次性报告口径（真席上岗即拿错误说明书）；G2 编排对 .agent/audit_jobs.json 在办单不吭声（流程停尸）；本任务补这两件
- **Date**: 2026-09-04

## 已确认意图

- 席位拿到工单即可独立完成契约 §1.4 一圈（claim-round→落钉→complete-round→修程→清零→audit-report→sign-report），说明书内嵌在 seat_prompt 里且指向权威源，不另造第二真相。
- 在办棘轮单在 `check`/`status`/MCP 三出口同一 `[NEXT]`（单一源 lifecycle_next）；优先级 pending_findings > **ratchet_open** > seal_ready > audit_suggested——单没关不催封板。

## 边界与拆分

- 路由只读**本地账**（open_ratchet_jobs），不为提示去打对端网络；对端实况归 `k3dge audit status`。
- 不在本单：G3（seal 判定换源到工单态）、G4（号段发放/席位注册）——真跑首案验证兼容后再立单。

## 验收

- k3dit：seat_prompt 断言 `claim-round/sign-report/不同席`（46 绿）；k3dge：open_ratchet_jobs 过滤 collected/failed + STATE_OPTIONS 含 ratchet_open + 三出口同源（242 绿）；AGENTS 触发表加行且模板镜像同批（守卫测绿）；check ✅。
