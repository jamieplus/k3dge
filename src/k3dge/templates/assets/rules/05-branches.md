# Rule 05 — Branches (思维分支裁剪)

> Protocol slice for tools that look under `.agent/rules/` (ADR-0010).
> Live agent protocol is repo-root `AGENTS.md`. If this file disagrees, `AGENTS.md` wins; fix this file in the same task.

* `k3dge check` 红且将重试 → 先归档 `docs/branches/YYYY-MM-DD-<slug>.md`（路径/假设/失败原因/学到什么），再 `git stash` 重读 `spec`。
* 重试前必读 `docs/branches/` 避重蹈覆辙。
