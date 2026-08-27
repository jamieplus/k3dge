---
id: INC-20260827-CON-arch-guide-links
type: CON
severity: P3
target_milestone: M6
discovery_date: 2026-08-27
status: closed
root_cause_harness: k3dge
action_task_ref: docs/tasks/2026-08-27-M6-fix-fix_architecture_guide_dangling_overview_links.done.md
---

# INCIDENT REPORT: [k8d3e-a78-03] 架构导读悬空链接

## 1. 现象与证伪证据 (B-T-D Evidence)

- **预期行为**: `docs/guides/architecture.md:13` 应指向 `docs/architecture/overview.md §8`（决策索引）及 `docs/reviews/SUMMARY.md`（有意留单一源）及 `docs/adr/README.md`。
- **现存破损**: `cat docs/guides/architecture.md` → `* 已定案决策与有意留：overview §5 / §5.1`；`grep -n "§5.1" docs/architecture/overview.md` → 0（已迁 `SUMMARY.md`+`§8`，`overview §5/§5.1` 已删）
- **复现路径**:
  ```bash
  cat docs/guides/architecture.md
  # => * 已定案决策与有意留：overview §5 / §5.1
  grep -n "§5.1" docs/architecture/overview.md # => 0
  grep -n "§8" docs/architecture/overview.md # => 118
  ```

## 2. 根因剖析 (5 Whys)

1. 为什么悬空？ → `overview §5/§5.1` 已按 ADR 迁移至 `SUMMARY.md` 顶部常驻表 + `overview §8` 索引，`guides/architecture.md` 未更新
2. 为什么未拦截？ → `guides/architecture.md` 非 `PAIRS` 资产，`k3dge check` 不验 `docs/guides/` 人读指针

## 3. 防退化动作清单

- [x] `docs/guides/architecture.md:11` → `已定案决策：overview §8 + adr/README.md / 有意留：SUMMARY.md / 本地自用：adr/0005`
- [x] `cat docs/guides/architecture.md` → `§8 + SUMMARY.md`
- [x] `grep §5.1 docs/guides/architecture.md` → 0

## 4. 经验灌入

- 决策/有意留单一事实源 `SUMMARY.md`，`overview §8` 仅索引，不再 `§5`

## 5. 双向回链

- **Audit**: `docs/reviews/2026-08-27-k8d3e-a78-5pass.md: 03`
- **Branch**: `docs/branches/2026-08-27-k8d3e-a78-repro.md: 03`
- **Task**: `docs/tasks/2026-08-27-M6-fix-fix_architecture_guide_dangling_overview_links.done.md`
