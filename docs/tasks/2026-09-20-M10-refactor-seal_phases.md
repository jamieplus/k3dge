---
status: idea
milestone: M10
priority: P1
date: 2026-09-20
---

# 封版三相位重排：预审（align+形式闸）→ 审计 → 审核后自动；`full_matrix` 移出封板动作、删 `satisfies`

- **可检索摘要**: ADR-0004 §2.1.9 把封版定义为"唯一入口 `seal` + 三相位：预审（进审计的门槛）→ 审计 → 审核后自动"。现实现方向相反：`[checks.seal].actions` 里的 `full_matrix` 把 align 放在**封板末段**跑，`nodes` 里还有 `full_matrix → satisfies align_pass` 的"动作满足闸"耦合；同时 `[checks.seal].preconditions` 把 `audit_closed`/`evidence_chain`/`audit_fresh` 当卡门（与 §2.1.3 脚注相抵）。本票只做**相位与闸位重排**（删/移/改述），不碰审计返回语义（`fix-audit_no_noop` 票）与 trailer/tag（`feat-seal_boundary_tag` 票）。

## Intent

让"预审失败 ⇒ 人修完再 seal"成为一种**可实现的形态**：预审是进入审计的门槛，不是封板的收尾动作；封板末段只做"审核后自动化"（提版/归档/收摊/记录）。

## 证据（实测）

```
gates.py  [checks.seal].preconditions = tasks_all_done, audit_closed, evidence_chain, align_pass,
                                        guides_filled, adrs_all_accepted, adr_landed, docs_normalized, audit_fresh
gates.py  [checks.seal].actions       = full_matrix, archive, closure_note, prune
nodes.py  full_matrix 的 satisfies → align_pass（动作 → 闸 的耦合）
seal.py   _seal_gate_registry() 是 seal 前置闸唯一构造处；seal_checklist() → (gid, ok, msg, auto)；
          unmet_seal_preconditions() 只含"需人办"；auto_pending_seal_gates() 列 ⚙️
worktree.py _run_landing_gate = sync + check + doc-gate + pytest（**不含**形式闸）
```

## 方案

```
① seal 命令内相位顺序固定为：预审 → 审计 → 审核后
   预审 = tasks_all_done + Full Matrix 绿（写 align 报告含 align-pass）
          + 形式闸（guides_filled / adrs_all_accepted / adr_landed / docs_normalized）
② [checks.seal].actions 去掉 full_matrix（移入预审相位），保留 archive / closure_note / prune
③ nodes：删 full_matrix 的 satisfies（相位不再是"动作满足闸"，run_phase 直接表达顺序）
④ 前置闸重排：audit_closed / evidence_chain **不再卡门**（降为"报告若存在则须合格"，
   细化见 `refactor-report_demote` 票）；audit_fresh 删除（边界改由 tag=B 表达，
   见 `feat-seal_boundary_tag` 票）
⑤ 落点闸补齐形式闸：审计修复可能破坏 guides/ADR/docs 形式项而今天无人验
⑥ [NEXT] 改述：audit_needed ⇒ "seal 会去做审计"（不是"不可封"）；
   seal_ready ⇒ 提醒人可发起 seal（名字可留，语义从判据变提醒）
⑦ seal-check 清单随闸同步（保留三态 ✅/⚙️/❌ 与 auto 标记）
```

## 边界与拆分（refactor 类）

- 事实归属：**相位表**归 `engine/nodes.py`（`NODE_DEFAULTS` + `run_phase`）；**闸清单**归 `engine/gates.py`（声明面）；**seal 前置闸构造**只许在 `engine/seal.py`（唯一构造点）；**`[NEXT]`** 归 `nextstep.py`（单一入口）。
- 边界检查：不新建第二套相位表（下游可配只认 `pipeline.toml` 声明面）；不动 `audit_flow` 的基线/分支/合流语义；不把 closure 人判项塞硬闸。
- 桩子先行：先改声明面（闸清单/相位表可单测），再改 seal 命令内顺序，最后对齐 `[NEXT]` 与 `seal-check` 清单。

## 验收

```
seal-check <id> 的清单＝重排后的集合：audit_fresh 消失、full_matrix 不在封板相位
预审失败 ⇒ seal 直接退出（不进入审计）；修完再 seal 可继续（幂等重入）
落点闸含形式闸：造一个 guide-stub ⇒ 合并被拒且主干 reset 回滚
nodes 表：无 full_matrix.satisfies；run_phase 相位顺序与 §2.1.9 一致
```

## Notes

- 建议顺序：`fix-audit_no_noop` → 本票 → `feat-seal_boundary_tag`；`refactor-report_demote` 可与本票同轮落。
