# Rule 03: Self-Contained Documents

> Protocol slice for tools that look under `.agent/rules/` (ADR 0012).
> Live agent protocol is repo-root `AGENTS.md`. If this file disagrees, `AGENTS.md` wins; fix this file in the same task.

Every document (spec, ADR, guide, memo, task, architecture overview) MUST be
self-contained: a future reader (human or agent with no prior conversation
memory) can understand it from the file alone.

- Include the *what*, *why*, and *when to revisit* in the file itself.
- Do not rely on chat history, external context, or "as discussed above" without
  restating the essential facts.
- For memos: list what was considered, what was decided, and the trigger for
  revisiting.
- For ADRs: the authoring & governance contract lives in `docs/protocols/adr_default.md` (frontmatter schema, three-section Context / Decision / Consequences, anti-narrative lint). Read it via `k3dge protocol resolve adr` before writing one.
- For specs: include In/Out of Scope and Verification Matrix.

Violations are not blocked by `k3dge check` (hard to machine-verify), but are
reviewed via `k3dge check`'s human companion: code review. When in doubt,
write as if the next reader has no memory of this conversation.
