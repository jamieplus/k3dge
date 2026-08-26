# Tasks — 工作登记处

唯一的工作项容器。所有条目都是 **Agent 提炼出的具体方案**（intake 闸门保证不收模糊
想法）。**Status** 表达工作流状态（这件事到哪一步了），与可选的 **Priority**（多件
待办谁先做）是两个独立维度。扫描时机见 AGENTS.md §5。

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
