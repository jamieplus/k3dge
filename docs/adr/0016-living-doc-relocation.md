---
Status: Accepted
Date: 2026-08-24
Deciders: Core Maintainer
---

# ADR 0016: 活文档搬走或删除时，扫描入口和指针必须同轮接上

## 1. 上下文 (Context)
`docs/protocols/audit_default.md` 按口令记下 8 维审计规程。同日写成 `harnesses/audit/PROTOCOL.md`，memo 标「已晋升」进 archive（§6：顶层扫描不再读 archive）。约 17 分钟后 ADR 0008 把 audit 迁出，删掉 PROTOCOL，本仓只留指向 k3dit 的指针。k3dit 随后被删、再空 init，没有 `docs/guides/protocol.md`。晋升目标没了，memo 仍在 archive。Agent 视界丢了现行透镜。README / MCP prompt 还指向已删路径。

§6 原来只写 memo → `docs/tasks/` → archive。这次晋升目标是 PROTOCOL，不是 task；也没有「目标被删则搬回顶层」。§12 没有「删仍被点名的文件」这一行。`k3dge check` 不解析 markdown 链接，拦不住。这是协议盲区，不是门禁盲区。

用户确认：漏掉的是文档接续，要补进 harness。

## 2. 决策 (Decision)

1. **活文档** = 当前扫描入口或被 AGENTS.md / README / MCP / ADR **点名为事实源**的文件（memo 顶层、PROTOCOL、guide、spec 等）。
2. **搬走或删除活文档，同一轮必须**：(a) 改所有点名指针到新位置，或标明「未接上、暂读何处」；(b) 若该文件是某 memo 的晋升目标且目标已不存在，把 memo **搬回** `docs/memo/` 顶层。禁止只删目标、留 archive。
3. §6 收紧：memo 进 archive 仅当新活文档**已经在磁盘上**。晋升到 task 以外（guide / PROTOCOL / 并列仓）可以，但目标路径必须存在；目标消失则撤销归档。
4. 不把「所有 md 链接是否 404」做成 `k3dge check` 规则。那是文档质量，进并列 harness 再说。本条只约束 Agent 在搬/删时的同轮接续。
5. §8 成对物：归档 memo 与晋升后的 PROTOCOL 是成对物。删其一前必须看另一份是否还承担扫描入口。

## 3. 产生后果 (Consequences)

- **正**：再删 `PROTOCOL.md` 时必须把 8 维 memo 拉回顶层，或当时就写好 k3dit 的 protocol。
- **负**：Agent 删文件前要搜谁点名了它，多一次 grep。
- **何时重开**：若要机器扫悬空链接，走 quality/audit 仓，不进 `src/k3dge`。
