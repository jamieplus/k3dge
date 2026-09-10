---
Status: Accepted
# Append-only after Accepted. Revise via `Amended by` / `Superseded by` below — do
# NOT rewrite this decision's prose in place, and never reuse a number (see README).
Supersedes: -
Amended-by: -
Date: 2026-08-24
Deciders: Core Maintainer
Note: ① 就地修订（正交去重：后继 harness 名单不再复述，名单以 ADR-0025 §2.4 为准）2026-09-10，经 Core Maintainer 本轮显式授权，依 `docs/adr/AUTHORING.md`；过闸口径 = manual fallback（实测 `command -v k3dit`/`k3dge` 无输出，no live lens）。
      ② 人读化改写（按 AUTHORING「人读优先」：决策先行、一行一点、长条拆子项；不变量与编号不变）2026-09-10，经 Core Maintainer 本轮显式授权，依 `docs/adr/AUTHORING.md`；过闸口径同上。
---

# ADR-0009: k3dge 的目的是给后续项目收住 Agent 的常见失败态

## 1. 上下文 (Context)
开发 k3dge 不是为了列一张「Agent 会犯的错」清单；用户说不了、也不必一一列举。
典型失败态（跨会话漂移、乱改抽象、代码与文档分手）见 ADR-0001。
还有修局部坏整体、幻觉接口等，属同一类问题。
k3dge 存在，是为了 **后面开发的项目**（含后继 harness）少踩这些，而不是给 k3dge 自己玩一套仪式。

## 2. 决策 (Decision)
- 目的：用目录契约 + 哈希硬闸 + `AGENTS.md`，让常规 Agent 在用户说出的任务上保持一致。
  - 失败态不必穷举；闸和协议是总称。
- 自举成功的标准：同一套东西能罩住 **下一个仓**（k3dit 已是第一个），而不是只在 k3dge 仓里自洽。
- 不把「减少幻觉/减少局部破坏」做成新的 check 规则或新域。
  - 那是目的语言；实现仍是 ADR-0001 的 L0/L1/L2 与协议条款。

## 3. 产生后果 (Consequences)
- 评价 k3dge 有没有用：看 k3dit 等后继仓上 Agent 是否更难漂、更难默默改契约，而不是看清单覆盖了几种失败。
- 用户只需说做什么。不必为每一种漂移再发明一条门禁。
