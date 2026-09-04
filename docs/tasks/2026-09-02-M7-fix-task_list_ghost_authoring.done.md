---
status: done
milestone: M7
priority: P3
date: 2026-09-02
---

# task list 把 docs/tasks/AUTHORING.md 当幽灵任务

- **Status**: done
- **Milestone**: M7
- **Priority**: P3
- **可检索摘要**: `milestone.list_tasks` 的排除集只有 `README.md`/`_template.md`，漏 `AUTHORING.md`，导致 `k3dge task list` / `status` 报一条不存在的 task
- **Date**: 2026-09-02

## 已确认意图

living-task 计数是 milestone 与 `[NEXT]` 判定的输入，混入非 task 文件会让"全 done"这类闸门口径失真。

## 上下文/切入点

- 现场：`src/k3dge/engine/milestone.py:466` `if p.name in ("README.md", "_template.md"): continue`
- 同文件 `:304` 已有一份 aux 集 `{"README.md", "AUTHORING.md", "_template.md", "LEFTOVERS.md", "leftovers.md"}`（reviews 扫描用）——两处各持一份、口径不一致，才是根因。
- 复现：`k3dge task list --json` → `{"path":"docs/tasks/AUTHORING.md","title":"Authoring","status":"unknown"}`；`k3dge status` 的 `Unfinished tasks (1)` 即此幽灵。
- `docs/*/AUTHORING.md` 由 `templates/scaffold.py:220+` 写入，是常驻结构件，永不是 task。

## 验收

- 单一事实源：task 扫描与 reviews 扫描共用同一 aux/排除常量；`AUTHORING.md`（及后续新增结构件）只登记一次。
- 单测：建 `docs/tasks/AUTHORING.md` 后 `list_tasks()` 返回 `[]`；`k3dge status` 显示 `Unfinished tasks: none`。

## Related

- `docs/tasks/2026-09-02-M7-fix-status_nameerror_next.done.md`
