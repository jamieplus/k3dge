---
status: done
milestone: M11
priority: P1
date: 2026-09-20
---

# 合线 rebase 后 `_baseline_covers` 把本轮审计判成旧单，再建单死锁封板

- **可检索摘要**: M10 真跑 seal：棘轮 collect 走 rebase 合线后 job.baseline=`d0def7f` 与 HEAD=`9d8f218` 无祖先关系；相位 2 判「旧内容」再建单 `0d0dee1dcad0`，新票 idea 再挡 `tasks_all_done`。`landed_head` 只覆盖「合线后立刻 seal、HEAD 未动」。

## 已确认意图

INC-20260920-AST 修法（接受已闭环前验「单基线覆盖本轮 B」）过冲：挡住了 60 提交之后的旧报告，也挡住了「刚 rebase 合进来的本轮报告」。封板唯一入口因此死锁。

## 证据（M10 真跑）

```
collect 后 job 1e408cbd4c78 baseline=d0def7f  state=collected merge_ok=true 待修=0
HEAD=9d8f218（rebase 重演的 round work M10）
git merge-base --is-ancestor 两边都不成立
k3dge milestone seal --yes M10
⇒ 审计未正常返回（status=ratchet_open）
⇒ 「该单基线 d0def7f 早于本轮基线 9d8f218 ⇒ 需要本轮新单」
⇒ 棘轮工单已建 0d0dee1dcad0
⇒ tasks_all_done 红：2026-09-20-M10-audit-audit_job_0d0dee1dcad0.md
```

同文件相邻洞：

- `_ratchet_audit_step` 优先 inflight：误建单在办时，已闭环单再也走不到 `_closed_job_evidence`
- `submit_audit` 用 `milestone_id` 当 worktree key（`k3dit/M10`），不是 `job_id`——连续两单抢同一条线

封版提交 `dea69ca` 已落 `landed_head`（B 等于合线瞬间主干头才覆盖）。**不够**：合线后再有一次提交（含为修死锁本身而提交）⇒ `fresh != landed_head` ⇒ 死锁回来。

## 方案

```
① `_baseline_covers`：rebase 后 pre-rebase oid 不在主干祖先链上时，
   用合线结果（landed_head / refs/audit-baseline/<job> 对应的重写 tip）判覆盖；
   主干上若还有非本单机械件提交 ⇒ 仍拒（保住 INC-20260920 的 60 提交案）
② 误 submit 必须可作废：inflight 不得永远压过 collected+merge_ok
③ worktree/branch key 用 job_id，或同里程碑复用线时不得为「判陈旧」再 lock 新基线
④ 单测：rebase 后 landed_head==B 接受；B 再走 feat 提交则拒；inflight 误建不得挡住本轮 collected
```

## 边界与拆分

- 事实归属：覆盖判定归 `milestone_audit._baseline_covers`；线/合线归 `worktree.merge_back`；工单态归 `audit_flow` 账。
- 边界检查：不把 Hall 内部席位轮次引进覆盖判定；只认 git 祖先 / 合线记下的主干头。
- 桩子先行：`test_rebased_collected_job_covers_landed_head` 已有相等/再提交两分支；补「误 inflight 优先」与「非 round-work 提交仍拒」。

## 结案

- 覆盖看 `landed_head^{tree} == fresh^{tree}`，不看作者/标题；树变了即拒。collected 优先于误 inflight。
- 测试：`test_same_tree_after_landed_head_covers_content_change_does_not`、`test_collected_covers_even_with_inflight_false_submit`。
