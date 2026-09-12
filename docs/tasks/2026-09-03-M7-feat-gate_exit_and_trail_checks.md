---
status: idea
milestone: M9
priority: P2
date: 2026-09-03
---

# 把出口同构与日志只追加变成机验

- **Status**: idea
- **Milestone**: M9
- **Priority**: P2
- **可检索摘要**: `ADR-0008` 的「三出口同构」与「审计痕迹只可追加」目前只靠人写测试守；本任务把它们变成闸：命令级同构断言 + 静态禁对 `logs/**` 覆写
- **Date**: 2026-09-03

## 已确认意图

`INC-20260902-CON-exit-and-trail-blindspot` 的四个现存破损都已修，但修法全是"加了几条测试"。要让同类问题不再靠某次自查发现，只有两条路：断言覆盖到**所有**带路由出口的命令，以及让"覆写审计痕迹"在结构层就不可能。

## 上下文/切入点

- 已存在的样板（照抄形状即可）：`tests/unit/cli/test_main.py::test_status_next_is_isomorphic_across_exits` 用一条 `k3dit:pending` 钉出确定状态，比较人类 `[NEXT]` 行、`status --json.next`、MCP `k3dge_status.next` 三者字典相等。
- 未覆盖的出口（同源风险）：`cli/main.py` 里 `_emit_lifecycle_next` / `_emit_workspace_hints` 的调用点 —— `cmd_check`（绿时三行提示）、`cmd_task`（done 后）、`cmd_milestone`（align/seal/audit 各分支）；**实测仍有两处同构破口未修**（本任务的主要工作对象）：
  - `k3dge_check()` 返回键 = `changed_files/force_full/modified_domains/ok/passed/render_output/violations`，**无 `next`**；而 CLI `cmd_check` 绿时会往 stderr 打 `[NEXT]` + hints + doc-audit 提示 ⇒ MCP 消费者看不到任何路由。
  - `k3dge_task_list()` 返回 `count/ok/tasks`，**无 `next`**；而 CLI `k3dge task done` 实测会打 `[NEXT] state=audit_suggested`。
  - `k3dge_milestone_control` 已带 `next`（`cli/mcp.py:371/394/418/439/452`）⇒ 说明这不是做不到，只是**没人对表**。
- 痕迹契约现场：`src/k3dge/engine/pipeline_runner.py` 已改为 `_append_log()` 追加；`cli/main.py:18 _append_log` 也是追加。风险是**将来有人再写一处** `write_text` 到 `logs/`。
- 闸落点候选（择一，别三处都写）：
  - (i) `engine/evaluator.py` 新增一条静态违规 `AUDIT_TRAIL_APPEND_ONLY`：扫 `src/**` 中对 `logs/` 目标的覆写式写入（`write_text` / `open(...,"w")`）；属结构闸，判盘上事实，不跑进程（不违 T-01 / `ADR-0006` §2.3.2）。
  - (ii) `k3dge doc-audit` 的 authoring 合规项（非阻断）—— 太软，挡不住。
  - 倾向 (i)，但它是**新增判定规则**，`ADR-0012` §2 明写"不增加 k3dge check 规则"是既有取向 ⇒ **动手前需维护者点头**，或退而用 lint 配置（若有 ruff `flake8-open` 类规则）。
- 出口同构断言的实现障碍（实测事实）：`cmd_check` 把提示写到 **stderr**，`cmd_status` 写到 **stdout**（`cli/main.py` 两处 stream 不同），三出口比较测试要按命令各自约定，不能一刀切。这条本身是否要统一，属可讨论项（先记录，不轻改输出面）。

## 验收

- 每个带路由提示的命令有一条"跑到末尾 + 三出口字典相等"断言：`check`、`task done`、`milestone align|seal|audit`、`status`（已有）。缺 `next` 的出口即测试红。
- 对 `logs/**` 的覆写式写入被机验拦下（闸或 lint，按上面择一），并有一条负例测试（写一处临时违规 → 报 `AUDIT_TRAIL_APPEND_ONLY`）。
- `k3dge check --force-full --with-tests` 绿；不新增运行时连接（`ADR-0006` §2.3.2 不破）。

## 边界与拆分

- 事实归属：NextStep 计算 → `cli/status.lifecycle_next`（单一来源）；出口渲染 → 各命令；痕迹文件 → 只追加契约。
- 边界检查：断言比较字典等价而非文案字符串；静态扫描只判 `logs/**` 的写入模式（覆写/追加），不判内容。
- 桩子先行：先写三口等价 / 痕迹覆写负例 / 追加正例三条断言，再推广到其余命令。

## Related

- 事故：`docs/incidents/INC-20260902-CON-exit-and-trail-blindspot.md` §3 后三条未勾项
- 席位侧的互补方案（制度化验收复核，不进闸）：`docs/memo/2026-09-02-peer-wiring-and-seat-options.md` §2.1
