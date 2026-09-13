# Authoring

Copy `_template.md`. Status ∈ {idea, deferred, in-progress, done}; Priority ∈ {P0…P3}. Filename `YYYY-MM-DD-<type>-<slug>.md`; on `done` append `.done` to the stem. Optional `Milestone: M1` in the name.

Optional `blocking:` (frontmatter) = comma/space-separated task stems this task is blocked by. `k3dge status` observes cycles + critical path under `task_dag` (facts, non-blocking); `check` does not gate on it.

User says "write this down" → file it this turn. Do not invent a second backlog.

Structure gate is `.schema.json` (`k3dge check`).
