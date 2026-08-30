# Tasks — 工作登记处

本目录是 k3dge 的**工作登记处（Tasks）**：唯一的工作项容器，所有条目都是 Agent 提炼出的具体方案（intake 闸门保证不收模糊想法）。

- **用途**：把"要做什么、为何做、做到哪步"固化下来，使跨会话可检索、可追踪；不与 `docs/memo/`（闪念）或 `docs/branches/`（试错）混淆。
- **组织**：按 `YYYY-MM-DD-<type>-<slug>.md` 命名；`Status` 表达工作流状态，`Priority` 表达优先级，两维独立。
- **怎么写**：新增 / 修订 task 的写法与机检契约见本页 `## 文档编撰规则` 段。
- **怎么读**：开工前 + 模糊召回必扫本目录全量（`k3dge task list --json`）做匹配，不凭记忆空想。

## 文档编撰规则 (Document Authoring Rules)

> **事实源**：`k3dge` 仅验"文件存在 / 注册一致"（`k3dge check`）；本文件载 task 的机检契约，叙事质量由评审保证。

### 交付

`docs/tasks/YYYY-MM-DD-<type>-<slug>.md`（`type` ∈ {audit, feat, fix, docs, chore, refactor}），含 `Status` / `Priority` 表头与「可检索摘要」。

### 格式契约

- `Status` ∈ {idea, deferred, in-progress, done}；`Priority` ∈ {P0, P1, P2, P3}
- 首段含「可检索摘要」段或 `可检索` 关键词，确保跨会话可检索
- `Status: done` 时文件名追加 `.done` 后缀

### Constraints

L2 入场券须逐条确认：

- 文件名满足 `^\d{4}-\d{2}-\d{2}-[\w-]+\.md$`
- 含表头 `Status`（上述枚举）与 `Priority`（上述枚举）
- 首段含「可检索摘要」段或 `可检索` 关键词
- 不得声明与既有 task 完全相同的 `Status: done` 重复闭环

## 命名与终态

`YYYY-MM-DD-<type>-<slug>.md`（`type` ∈ {audit, feat, fix, docs, chore, refactor}，`slug` 内用 `_` 分隔）；`Status: done` 时文件名追加 `.done` 后缀（如 `2026-08-24-audit-foo_bar.done.md`），非 `done` 不加后缀（`audit` 的 `done` 指 auditor 已验证改动无误，方可 archive）。

里程碑编码（可选）：有 `Milestone: M1` 时文件名中加入 `M1`（如 `2026-08-24-M1-audit-foo_bar.md`）。筛该里程碑用 `k3dge task list --json --milestone M1`。无 Milestone 的 `done` 人工搬进 `docs/tasks/archive/untagged/`，不计入 align/seal。

**快筛**：`k3dge task list --json`（`--milestone` / `--status` 过滤）。只返回索引字段；Agent 仅对命中文件 `read`。归档 `docs/tasks/archive/` 不在扫描面。

## 单条模板（自包含，未来失忆的自己也能看懂）

```markdown
# <标题>（Agent 已给出的方案，用户确认做但暂缓 / 明确工作项）

- **Status**: idea | deferred | in-progress | done
- **Milestone**: M1（可选；无则不计入任何 `align/seal`，需人工清）
- **Priority**: P0（最高）| P1 | P2 | P3（可选；条目少时可省略）
- **可检索摘要**：可独立理解的版本（不依赖聊天上下文）
- **上下文/切入点**：在聊哪域时提出；回头从哪文件/哪段接上
- **触发条件**（deferred 时）：满足什么条件再启动
- **原话备查**："..."（可选）
- **Date**: YYYY-MM-DD
```

## 纪律

- 用户"先记下来 / 放这里" → 当轮必落盘，不许口头应承
- 开工前 + 模糊召回时 → 必扫本目录全量做匹配，不许凭记忆空想
- Status 流转：idea → deferred/in-progress → done（做完归档或转 ADR）
