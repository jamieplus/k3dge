---
status: done
milestone: M11
priority: P3
date: 2026-09-21
---

# SYNC-01 文案不实 + task 状态词表双源 + 落点闸 docstring 错名

- **可检索摘要**: 三处"报告面/声明面 ≠ 事实"（2026-09-21 memo 复核产出）：① `k3dge sync` 在只重生 `docs-index.json` 时打印 `Contracts already up to date.`（MCP 同源报 `up_to_date:true`）；② `task_index._ALLOWED_STATUS` 与 `state_machine.TaskState` 是同一词表的两份副本、且 `resolve()` 在生产里零消费者；③ `worktree.merge_back` docstring 把 `_run_landing_gate` 写成不存在的 `run_landing_gate`。

## 来源（memo 复核）

`docs/memo/2026-09-21-hookization-surface-inventory.md` 候选 D（判决：收敛而非钩子化）、
`docs/memo/2026-09-21-sync-docs-updated-flag.md` 选项 3（只改文案）+ `docs/reviews/LEFTOVERS.md` `SYNC-01`。

## 证据（可复跑）

```
$ git diff --stat docs/generated/docs-index.json      # 干净
$ k3dge sync
[SYNC] Contracts already up to date.                  # ← 说"无改动"
$ git diff --stat docs/generated/docs-index.json
 docs/generated/docs-index.json | 8 ++++++++           # ← 实际写了盘
```
（同会话复现两次；机制：`sync_docs_index` 写盘但不置 `docs_updated`，而该标志只由 `sync_manual_docs` 置。）

状态词表：
```
state_machine.py:37  注释「消费者不得另写 match/if 分支，一律 resolve()」
state_machine.py:48  def resolve(...)        ← src/ 里零调用（仅 cli/status.py 取 summary() 展示）
task_index.py:13     _ALLOWED_STATUS = frozenset({"idea","deferred","in-progress","done"})  ← 真正拦合法性的
align.py:82 / seal.py:465  用 _ALLOWED_STATUS 判 invalid_task_status
```

## 方案（三件，均"收敛/更正"而非加机制）

1. `_ALLOWED_STATUS` 改为从 `TaskState` **派生**（词表拥有者归 `state_machine`）。
2. `cmd_sync` 的"无变化"分支改为**陈述事实**：契约无变化 ≠ 没写盘（`ADR-0026 §2.2` 纯打印面要求）。
3. docstring 错名改回真实符号。

## 边界与拆分

- 事实归属：task status 词表 → `state_machine`（`TaskState`）；sync 投影语义 → `sync` 域；落点闸 → `worktree`。
- 不动：`docs_updated` 标志语义与 MCP `up_to_date` 字段（改字段语义要走 ADR；reopen 条件见 memo）。
- 不加测试守卫：派生后「两处相等」类断言是同义反复（写的就是那个表达式）；FSM 侧真实守卫是既有的
  `check_completeness`（终态/死锁/可达）。

## 结案

- `src/k3dge/engine/task_index.py`：`_ALLOWED_STATUS = frozenset(s.value for s in TaskState)` + 注释点明拥有者。
- `src/k3dge/cli/main.py`：无变化分支改打印 `[SYNC] No spec contract changes (derived docs/index are rewritten only when stale).`，日志同改。
- `src/k3dge/engine/worktree.py`：docstring `run_landing_gate` → `_run_landing_gate`（真名）。
- 闸：`k3dge sync`（契约哈希 + api.md 重生）→ `k3dge check --with-tests` 绿（cli/engine）→ `pytest -q` 701 passed, 2 skipped。
- 有意留（未做，理由）：`docs_updated`/`up_to_date` 字段语义（等到有 consumer 实例）；不等性守卫测试（同义反复）。
