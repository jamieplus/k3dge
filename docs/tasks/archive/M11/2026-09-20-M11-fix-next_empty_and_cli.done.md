---
status: done
milestone: M11
priority: P2
date: 2026-09-20
---

# 空里程碑报 seal_ready；失败双 NEXT；audit status 把里程碑当 job_id

- **可检索摘要**: M10 封完立刻 `[NEXT] state=seal_ready milestone=M11`「票已齐、预审待办：全绿」（零 task）。相位 2 拒时先打 `ratchet_open` 再打 `rejected`。`k3dge audit status M10` 把 M10 当 job_id → NOT_FOUND。ADR-0004：空窗不建议封。

## 已确认意图

`[NEXT]` 只给合法下一步。零 task 不是可封；一次命令只投影一个 state；status/show 对里程碑 id 与 job id 要分清。

## 证据（M10 真跑）

```
k3dge status  （封板后）
[NEXT] state=seal_ready milestone=M11
  fact: 里程碑 M11 形式闸与票已齐；…预审待办：全绿

审计刚闭环、票未 done 时也曾：
[NEXT] state=seal_ready … reason: tasks_all_done：Cannot seal…
  fact: …票已齐…；预审待办：tasks_all_done
（NEXT-01：state 与 blockers 不同源）

相位 2 拒：
[NEXT] state=ratchet_open …
[NEXT] state=rejected …
（agent 不知道听哪条）

k3dge audit status M10
{"ok": false, "job_id": "M10", "error": "NOT_FOUND", "message": "no such job: M10"}
help 写 job_or_milestone，实现只当 job_id
```

## 方案

```
① 零 task / 空窗 ⇒ 不得投影 seal_ready（ADR-0004 §2.1.4 空窗不建议封）
② seal_ready_for：有 unmet 前置时 state 不要仍叫 seal_ready，或 fact 不得说「票已齐」
③ run_seal_flow 拒绝路径只 persist/打印一条 [NEXT]（外层覆盖内层，或内层不 persist）
④ `k3dge audit status <id>`：先当 job_id，NOT_FOUND 再当 milestone 列该里程碑的单
```

## 边界与拆分

- 事实归属：state 投影归 `nextstep`；CLI 参数归 `cli`；工单索引归 `audit_flow`。
- 边界检查：CLI 不解析 peer 内部 state，只问本地账 + 对端 status 信封。
- 桩子先行：空 milestone 指针 + 零票 ⇒ `next_for` 不是 seal_ready。

## 结案

- 零 task ⇒ seal_ready_for 回 normal；status 同样；有 unmet 时 fact 不说票已齐；seal 在办态不覆盖 rejected；peer_status 里程碑 id 回落到该里程碑最新单。
