---
type: CON
severity: P2
target_milestone: M6
discovery_date: 2026-08-27
status: closed
root_cause_harness: k3dge
action_task_ref: docs/tasks/2026-08-27-M6-fix-fix_AGENTS_route_05_branches_misroute.done.md
---

# INCIDENT REPORT: [k8d3e-a78-01] AGENTS.md 路由表规则编号错位

## 1. 现象与证伪证据 (B-T-D Evidence)

- **预期行为 (Baseline)**: `AGENTS.md:20` `Task intake/recall` 行应仅指向 `.agent/rules/00-core-discipline.md`，任务快筛为命令 `k3dge task list --json`，不綁规则编号 `05`。
- **现存破损 (Treatment 前)**: `AGENTS.md:20` 写 `00-core-discipline.md + 05 任务快筛`，但 `.agent/rules/05*` 实际为 `05-branches.md`（思维分支裁剪），`grep -n "Task intake" AGENTS.md` 命中 `05`，误导 Agent 寻址 `05` 找任务。
- **复现路径**:
  ```bash
  grep -n "Task intake" AGENTS.md
  # => | Task intake/recall | `.agent/rules/00-core-discipline.md` + `05` 任务快筛（`k3dge task list --json`） |
  ls .agent/rules/05* # => 05-branches.md
  diff AGENTS.md src/k3dge/templates/assets/agents.md && echo "drift"
  # => 仅路由行不一致，PAIRS 未拦（因 assets 也含 +05）
  ```

## 2. 根因剖析 (5 Whys)

1. 为什么路由错位？ → `AGENTS.md:20` 文案把 `05` 当任务快筛编号，与 `05-branches.md` 冲突
2. 为什么 `assets` 也错？ → `src/k3dge/templates/assets/agents.md:20` 同步含 `+05`，`PAIRS` 字节锁未拦（双端同错）
3. 为什么夹带编号？ → 早期 `00` 为纪律，`05` 为分支，误将分支编号作任务索引
4. 为什么未拦截？ → `test_template_sync` 仅验 `PAIRS` 字节一致，不验语义

## 3. 防退化动作清单

- [x] **物理测试加固**: `AGENTS.md:20` → `00-core-discipline.md（快筛用 k3dge task list --json）`，双写 `assets/agents.md:20`（`PAIRS` `agents.md↔AGENTS.md`）
- [x] **契约补强**: `grep -n "Task intake" AGENTS.md` → `00` 无 `05`，`diff AGENTS.md assets/agents.md` ok
- [x] **关联修复 Task**: `2026-08-27-M6-fix-fix_AGENTS_route_05_branches_misroute.done.md` 已 `done`，`align M6 PASS`
- [x] **规则升级**: `AGENTS.md:20` 路由不綁编号，`05` 仅 `branches`

## 4. 经验灌入

- `AGENTS.md` 路由行不綁规则编号，任务快筛是命令 `k3dge task list --json`，不是 `05`
- `rg "05" AGENTS.md` 应 0 误导，`PAIRS` 双写需同改

## 5. 双向回链

- **Audit**: `docs/reviews/archive/untagged/2026-08-27-k8d3e-a78-5pass.md: 01`
- **Branch**: `docs/branches/2026-08-27-k8d3e-a78-repro.md: 01`
- **Task**: `docs/tasks/2026-08-27-M6-fix-fix_AGENTS_route_05_branches_misroute.done.md`
- **Review 回填**: `docs/reviews/archive/untagged/2026-08-27-k8d3e-a78-5pass.md: 回填 01 已修`
