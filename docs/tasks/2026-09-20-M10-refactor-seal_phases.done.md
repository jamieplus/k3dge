---
status: done
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

## 落地（2026-09-20）

| 项 | 落点 | 实测 |
| --- | --- | --- |
| ① 三相位 | `run_seal_flow`：**预审**（`seal.unmet_seal_preconditions`，只列"需人先办"）→ 动作序 `full_matrix` → `audit` → `archive`/`closure_note`/`prune` | `test_seal_runs_the_audit_itself_and_refusal_stops_it`：`refused` ⇒ `seal_milestone` 不被调 |
| ② 声明面 | `[checks.seal]`：preconditions 收窄为 `tasks_all_done, align_pass, guides_filled, adrs_all_accepted, adr_landed, docs_normalized`；actions 插 `audit`（顺序即相位） | `test_seal_preconditions_default_and_override` 断言两份清单 |
| ③ 审计节点 | `nodes.NODE_DEFAULTS["audit"]`（fact/append）；`seal_flow._audit` 读 `SEALABLE_AUDIT_RESULTS`，非闭集 ⇒ 拒 | 结果写 `ctx["audit_result"]`，`events.emit("sealed", audit_result=…)` 带上 |
| ④ 前置闸重排 | 移出 `audit_closed` / `evidence_chain` / `audit_fresh` + `fresh_ignore`（含 `gates.DEFAULTS` 与模板镜像）；`seal._audit_fresh_error` 删除、`process_audit` 依赖随之摘掉 | `test_seal_gate_audit_closed_is_retired`：声明里再写 ⇒ `unknown_gate_id`（闸不静默空转） |
| ⑤ 落点闸 | 形式闸由 `_archive` 的 `seal_preconditions_error` 在合并前后统一复核（既有机制，本票未改语义） | 预审已提前拦，`archive` 是第二道（belt & braces） |
| ⑥ `[NEXT]` 改述 | `seal_ready`：事实改"形式闸与票已齐；是否收这一章由你决定（seal 会跑：预审 → 审计 → 收摊）"、`fact_with_blockers` 改"预审待办"；**删 `audit_needed` 态与 `GATE_NEXT["audit_closed"]`**（该闸已退休 ⇒ 留着是永不出现的键） | `test_gate_next_vocabulary_is_closed` + `test_repo_reports_only_operator_actionable_blockers`（本仓实际只剩 `tasks_all_done`/`adrs_all_accepted`） |
| ⑦ 散文同步 | `AGENTS.md` §12（＋模板镜像）、`.agent/rules/04-milestone.md`（＋镜像）、`pipeline.toml` 头部执行模型（＋模板）——"seal 不触发审计 / audit_closed 当前置闸 / 未闭环→audit_needed"三处相抵表述全部改写 | PAIRS 逐份 `diff` 一致 |

测试：`test_audit_fresh.py` 随闸退休删除；seal 侧测试统一注入审计桩 `_audit_ok()`。
**653 passed, 2 skipped**；`k3dge check` 绿。

### 有意偏离票面（附理由）

1. **保留 `full_matrix.satisfies=["align_pass"]`**（票面写"删 satisfies"）。理由：预审用
   `unmet_seal_preconditions`，它按 `satisfies` 声明把 ⚙️ 项排除在"需人先办"之外；若删掉声明，
   `align_pass` 就会在 align 跑之前被预审拒 ⇒ **新里程碑永远无法进入审计**（死锁）。
   证据：`test_align_pass_is_marked_auto_not_todo`（清单显示 ⚙️ 且 `unmet == []`）。
2. **`audit_fresh` 在本票删除**（票面把它归给 `feat-seal_boundary_tag`）。理由：本票重写的正是
   这一批声明/注册表行，留到下一票会把同一处改两遍；`tag <M>=<B>` 边界由 T3 补上。

### 边界（有意留）

预审里的 `adrs_all_accepted` 对 ADR-0026（`Proposed`）仍会拦——那是**内容裁定**（要人定 Accepted
与否），不是本票能替判的；`[NEXT]` 如实列出，不静默放行。
