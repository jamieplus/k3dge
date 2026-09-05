---
status: done
milestone: M7
priority: P0
date: 2026-09-02
---

# k3dge status 抛 NameError 致 [NEXT] 永不输出

- **Status**: done
- **Milestone**: M7
- **Priority**: P0
- **可检索摘要**: `cmd_status` 非 `--json` 分支引用未定义名 `workspace`，`k3dge status` 结尾必崩，`ADR-0008` 的 `[NEXT]` 路由在 status 上全线失效
- **Date**: 2026-09-02

## 已确认意图

`k3dge status` 是 `AGENTS.md` 要求每个 agent 第一个跑的命令，其 `[NEXT]` 行是软路由的唯一常驻出口；崩溃即路由失效。

## 上下文/切入点

- 现场：`src/k3dge/cli/main.py:1014-1015`
  ```
  _emit_lifecycle_next(workspace, sys.stdout)
  _emit_workspace_hints(workspace, sys.stdout)
  ```
  同一函数体内工作区变量名是 `status_obj = workspace_status(_find_workspace())`（`:987`），从未绑定 `workspace`。
- 复现：`.venv/bin/python -m k3dge.cli.main status` → 正常打印四行后 `NameError: name 'workspace' is not defined`，`[NEXT]` 与 hints 均不可见。
- 该路径无测试覆盖（`tests/unit/cli/test_main.py` 未跑非 json status 分支的 `[NEXT]` 断言）——否则不会带病通过。

## 验收

- 修 `workspace = _find_workspace()` 一次绑定，供两处使用。
- 新增断言：非 `--json` 的 `status` 输出含 `[NEXT] state=` 一行；`status --json` 的 `next` 字段同构（`ADR-0008` 双出口一致）。
- `k3dge check --force-full --with-tests` 绿。

## Related

- 同批扫出的另一处 cli/engine 现状缺陷：`docs/tasks/2026-09-02-M7-fix-task_list_ghost_authoring.done.md`（不同根因，各自独立）

## 回填（同轮自查：验收曾有一条未达成就被标 done）

`task done` 之后复核本文件验收，发现第二条**没做到**：我只断言了 `status` 不崩，而「`status --json` 的 `next` 字段同构」并未实现——`workspace_status()` 的返回里根本没有 `next` 键，即**人类出口有 `[NEXT]`、JSON 与 MCP 出口什么都没有**（`ADR-0008` 双出口同构被破）。已补做，不是收回 done 标记而是把缺口填平：

- `cli/status.py` 新增 `lifecycle_next(workspace)`：NextStep 单一来源从 `cli/main.py` 迁入，`workspace_status()` 输出加 `next` 键（None 或 `render_mcp()`）。
- `cli/main.py::_lifecycle_next` 改为委托，人类出口与机读出口共用一次计算（不重复扫描）。
- 新测试 `test_status_next_is_isomorphic_across_exits`：同一 temp 仓钉一条 `k3dit:pending T-ISO-1`，断言三出口一致 —— 人类 `[NEXT] state=pending_findings`、`status --json` 的 `next.state` 同值、MCP `k3dge_status` 的 `next` **字典相等**。
- 契约面：`cli` 域新增公开符号 `lifecycle_next` ⇒ 已 `k3dge sync`（`[SYNC] Updated spec contract: cli`）。
- 实测：`status --json` 键集含 `next`；`next={"state":"audit_suggested","milestone":"M7",...}`；`pytest -q` 全绿。

教训记一行：`task done` 的自动动作是改状态与归档，它**不会**替你验收获据；本仓把"标 done 前逐条复述验收"留给审计席位判（k3dit），而不是再加一条闸。
