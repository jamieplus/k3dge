---
status: done
milestone: M11
priority: P2
date: 2026-09-20
---

# 棘轮 collect 不调 `_ensure_leftovers`，有意留不进 LEFTOVERS.md

- **可检索摘要**: `_ensure_leftovers` 只在 oneshot `_oneshot_audit_leg` 里调。ratchet `collect_audit` 落盘 12 列后不登记有意留。M10 报告 value-22 有意留=1，collect 后 LEFTOVERS 无该行，封板前手补。

## 已确认意图

有意留的唯一事实源是 `docs/reviews/LEFTOVERS.md`。collect 待修=0 且有意留>0 时必须幂等写入，不靠人记。

## 证据

```
job 1e408cbd4c78 counts: 待修 0 / 有意留 1 / 已修 11
报告行 value-22 状态=有意留
collect 后 rg value-22 docs/reviews/LEFTOVERS.md ⇒ 无
oneshot 路径：milestone_audit._oneshot_audit_leg → _ensure_leftovers
ratchet 路径：audit_flow.collect_audit 只 append ## 回收记录
```

## 方案

```
① collect_audit 在落盘且解析到 有意留>0 时调 _ensure_leftovers（注意 audit_flow ↔ milestone_audit 循环 import，函数放到 report 侧或 leftovers 小模块）
② 单测：临时仓 collect 一份含 有意留 行的报告 ⇒ LEFTOVERS 出现该 ID；再 collect 不重复
```

## 边界与拆分

- 事实归属：有意留表归 `docs/reviews/LEFTOVERS.md`；写入动作归 collect（唯一落盘点）。
- 边界检查：k3dge 只按 12 列「状态=有意留」抄 ID，不解释描述。
- 桩子先行：不连 peer，喂报告文件即可。

## 结案

- collect_audit 落盘后调 _ensure_leftovers。
