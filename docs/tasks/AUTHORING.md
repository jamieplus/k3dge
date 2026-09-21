# Authoring

Copy `_template.md`. Status ∈ {idea, deferred, in-progress, done}; Priority ∈ {P0…P3}. Filename `YYYY-MM-DD-<type>-<slug>.md`; on `done` append `.done` to the stem. Optional `milestone: M1` in the frontmatter.

**Frontmatter is the only source for task metadata** (`status` / `milestone` / `priority` / `date` / `report` / `blocking`). Do not repeat those fields as body bullets (`- **Status**: …`) — every consumer (`task list`, `milestone status`, the seal gate, the schema gate) reads the frontmatter, so a body copy is a second source that can only drift. Machine-gated: `TASK_BODY_META_REDUNDANT`. Body bullets carry what has no frontmatter field (e.g. `- **可检索摘要**:`).

**done 票必须留结案记录**（`## 结案` / `## 落地` / `## 关闭理由` / `## 收尾` / `## 回填` / `## 进度` / `## 回收记录` 之一，且其后有内容）。Machine-gated: `TASK_CLOSURE_MISSING`（标题可带限定词）。闸**只验有没有写**，内容对不对归人/k3dit——票是自包含事实源，关票时不写落地痕迹，后续就会出现「票里说待办、实际已做」的漂移（实测：三张票的 `blocking` 与验收段全漂，全靠人工扫才发现）。`k3dge task done` 若缺段会补一行关票日期。

**仓库级也验**：`k3dge check` 对 `docs/tasks/**` 跑一致性（status↔文件名、milestone↔文件名、正文复写元数据、结案记录），不再只在 pre-commit 对 staged 文件验。

Optional `blocking:` (frontmatter) = comma/space-separated task stems this task is blocked by. `k3dge status` observes cycles + critical path under `task_dag` (facts, non-blocking); `check` does not gate on it.

User says "write this down" → file it this turn. Do not invent a second backlog.

Structure gate is `.schema.json` (`k3dge check`).
