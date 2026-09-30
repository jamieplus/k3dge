# Rule 06 — Memo (灵光收件箱)

> Protocol slice for tools that look under `.agent/rules/` (ADR-0010).
> Live agent protocol is repo-root `AGENTS.md`. If this file disagrees, `AGENTS.md` wins; fix this file in the same task.

* 收三类暂不成事的念头：模糊概念/暂无法落地/弱相关闪念，与 `tasks` 互补。
* 触发：用户"memo一下"或 Agent 提议"先 memo？"点头后写 `docs/memo/YYYY-MM-DD-<slug>.md`。
* 晋升：成熟后 `mv` 至 `docs/memo/archive/`（扫描仅顶层），`archive` 不再读；目标被删则同轮搬回顶层（ADR-0018）。
