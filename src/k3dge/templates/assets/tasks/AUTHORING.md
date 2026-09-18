# Authoring

Copy `_template.md`. Status ∈ {idea, deferred, in-progress, done}; Priority ∈ {P0…P3}. Filename `YYYY-MM-DD-<type>-<slug>.md`; on `done` append `.done` to the stem. Optional `milestone: M1` in the frontmatter.

**Frontmatter is the only source for task metadata** (`status` / `milestone` / `priority` / `date` / `report` / `blocking`). Do not repeat those fields as body bullets (`- **Status**: …`) — every consumer (`task list`, `milestone status`, the seal gate, the schema gate) reads the frontmatter, so a body copy is a second source that can only drift. Machine-gated: `TASK_BODY_META_REDUNDANT`. Body bullets carry what has no frontmatter field (e.g. `- **可检索摘要**:`).

Optional `blocking:` (frontmatter) = comma/space-separated task stems this task is blocked by. `k3dge status` observes cycles + critical path under `task_dag` (facts, non-blocking); `check` does not gate on it.

User says "write this down" → file it this turn. Do not invent a second backlog.

Structure gate is `.schema.json` (`k3dge check`).
