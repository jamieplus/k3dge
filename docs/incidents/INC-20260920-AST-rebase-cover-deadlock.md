---
type: AST
severity: P1
status: closed
---

# Incident: rebase 合线后本轮审计被判成旧单——seal 再建单死锁

## 1. 现象与证伪证据 (B-T-D Evidence)

- **预期行为 (Baseline)**：棘轮工单 collect 且 `待修=0`、`merge_ok` 之后，同一轮 `k3dge milestone seal` 相位 2 应认 `closed`，不得因合线改了 commit hash 再开新单。
- **现存破损 (Treatment)**：M10 真跑（2026-09-20）。job `1e408cbd4c78` 已 collected（待修 0，报告在盘，署名齐，报告基线=`d0def7f` = 单基线）。`merge_back` rebase 后 HEAD=`9d8f218`，与 `d0def7f` **互不为祖先**。`_baseline_covers` 返回假，文案写成「早于本轮基线」。相位 2 再建单 `0d0dee1dcad0`，新票 `idea` 挡 `tasks_all_done`。
- **复现路径**：
  ```
  # collect 走 rebase 合线（主干已有提交，无法 ff）
  k3dge milestone audit M10          # 认 closed
  k3dge milestone seal --yes M10     # 相位 2：旧内容 ⇒ 新单 ⇒ 预审红
  ```
- **与 INC-20260920-AST-stale-report-closed-audit 的关系**：那次是「旧报告充闭环」（60 提交之后仍接受）。修法加了「单基线必须覆盖本轮 B」。本事故是同一判定的反面：rebase 重写 hash 后本轮报告被当成旧内容。不是同一事件，不并入。

## 2. 根因剖析 (5 Whys)

1. 为什么判成旧单？→ `_baseline_covers(fresh, job_baseline)` 只认相等或「B 是 job 基线的祖先」。rebase 后两 hash 无关。
2. 为什么文案说「早于」？→ 失败分支把所有「不覆盖」写成「早于」，未区分无关 vs 真祖先。
3. 为什么会再建单？→ `_ratchet_audit_step` 在 collected 不被接受时无条件 `submit_audit`。
4. 为什么再建单就封不了？→ submit 建 `idea` 票；seal 预审 `tasks_all_done` 含该票；inflight 还压过已闭环单。
5. 为什么 INC-20260920 的测试没拦住？→ `test_stale_collected_job_is_not_accepted` 造的是「旧 commit 是 HEAD 祖先 + 其上再有 feat 提交」，测不到 rebase 后无关 hash。

封版提交 `dea69ca` 先加了 `landed_head` 相等覆盖。M11 续：机械件区间仍覆盖；collected 优先于误 inflight。`k3dit/<milestone>` 共线未改（死锁不依赖它）。见 `fix-seal_rebase_cover`。

## 3. 防退化动作清单

| 动作 | 落点 | 证据 |
| --- | --- | --- |
| 合线后记下主干头 | `audit_flow.collect_audit` → `job["landed_head"]` | 已落 `dea69ca` |
| B==landed_head 视为覆盖 | `milestone_audit._baseline_covers` | `test_rebased_collected_job_covers_landed_head` |
| 主干再走非本单提交仍拒 | 同上测试后半 | 已落 |
| 合线后树未变仍覆盖（不看作者/标题） | `_git_tree(landed_head)==_git_tree(fresh)` | `test_same_tree_after_landed_head_covers_content_change_does_not` |
| collected 优先于误 inflight | `_ratchet_audit_step` 先认 done | `test_collected_covers_even_with_inflight_false_submit` |

## 4. 经验灌入

- 「覆盖」用 commit 祖先表达，在 rebase 合线模型里会把本轮改写成无关 hash。合线必须留下 **landed_head**（或重写 tip）作为第二覆盖键，不能只拿报告里的 pre-rebase oid。
- 拒旧和认新是两个方向，要分开测：祖先+后续 feat（INC-20260920）与 rebase 无关 hash（本事故）。
- 判定失败去「再建单」之前，先问 inflight 会不会把刚认过的闭环挡死。
