---
id: INC-20260827-CON-k8d3e-a78-5pass
type: CON
severity: P2
target_milestone: M6
discovery_date: 2026-08-27
status: closed
root_cause_harness: k3dge
action_task_ref: docs/tasks/2026-08-27-M6-fix-fix_AGENTS_route_05_branches_misroute.done.md
---

# INCIDENT REPORT: [k8d3e-a78] 5-Pass 穿透 01-05 一致性悬空与 PAIRS 缺口

## 1. 现象与证伪证据 (B-T-D Evidence)

- **预期行为 (Baseline)**: `k3dge-audit` 快照 `0.1.7/M6` 的 `AGENTS.md` 路由应指向 `00-core-discipline.md` 纯净，`07-audit` 应 `../k3dit/... → audit_default.md`，`architecture.md` 应 `§8+SUMMARY`，`mcp-bridge` 应 `../k3dit`，`PAIRS` 应含 `protocols/audit_default.md`，下游 `init` 不漏 `docs/protocols/audit_default.md`。
- **现存破损 (Treatment 前)**: `AGENTS.md:20` 仍 `+05 任务快筛` 但 `05` 实为 `branches`；`07-audit.md:3` 仍 `docs/guides/protocol.md` 悬空；`architecture.md:13` 仍 `§5/§5.1`；`mcp-bridge.md:69` 仍 `k3dit/docs/...` 缺 `../`；`pairs.py:19` 无 `protocols`，`assets/protocols/` 不存在，`test_template_sync` 22 项。
- **复现路径**:
  ```bash
  grep -n "Task intake" AGENTS.md # => 00 +05
  ls .agent/rules/05* # => 05-branches.md
  cat .agent/rules/07-audit.md | head -3 # => docs/guides/protocol.md
  cat docs/guides/architecture.md # => §5 / §5.1
  grep -n "k3dit" docs/guides/mcp-bridge.md # => k3dit/docs (缺 ../)
  grep -n "protocols" src/k3dge/engine/pairs.py # => 0
  pytest tests/unit/templates/test_template_sync.py -q # => 22 expected
  ```

## 2. 根因剖析 (5 Whys)

1. 为什么 `AGENTS.md` 错位？ → `05` 任务快筛文案与 `05-branches.md` 编号冲突，`assets/agents.md` 未同步剥离
2. 为什么 `07-audit` 悬空？ → `docs/guides/protocol.md` 已按 Diátaxis 迁 `docs/protocols/audit_default.md`，`07-audit` 未跟随
3. 为什么 `architecture` 悬空？ → `overview §5/§5.1` 已迁 `SUMMARY.md`+`§8`，`guides/architecture.md` 未更新
4. 为什么 `mcp-bridge` 缺 `../`？ → `k3dit/docs/guides/...` 与 `../k3dit/docs/guides/...` 混用，`grep` 未统一
5. 为什么 `PAIRS` 缺 `protocols`？ → `docs/protocols/audit_default.md` 新增时未同步 `资产+PAIRS+scaffold+expected` 四件套（`TEMPLATE_DRIFT` 漏）

## 3. 防退化动作清单

- [x] **物理测试加固**: `AGENTS.md:20` → `00（快筛用 ...）`，`assets/agents.md:20` 同步（`PAIRS`）
- [x] **契约补强**: `07-audit.md:3` → `../k3dit/...，否则 audit_default.md`，`assets/rules/07-audit.md:3` 同步
- [x] **文档链路**: `architecture.md:11` → `§8+SUMMARY`，`mcp-bridge.md:69` → `../k3dit/...`，`assets/mcp-bridge.md.template:69` 同步
- [x] **成对锁**: `mkdir assets/protocols && cp docs/protocols/audit_default.md`，`pairs.py:47` + `protocols/audit_default.md`，`scaffold.py:60/225` + `PROTOCOL_TEMPLATE`，`test_template_sync:46` +1 → `65 subtests`
- [x] **关联修复 Tasks**: `2026-08-27-M6-fix-fix_AGENTS_route_05_branches_misroute.done.md` 等 5 项已 `done`，`align M6 PASS`，`Gate SUCCESS`
- [x] **规则升级**: `.agent/rules/07-audit.md:7` 已指 `docs/incidents/INC-...`（`incident` 单数废弃），`AGENTS.md:46` / `branches/README.md:5` 同步

## 4. 经验灌入

- `AGENTS.md` 路由不綁编号，`05` 仅 `branches`，`grep -r "05" AGENTS.md` 0 误导
- `docs/guides/` 人读，机器 SOP 必 `docs/protocols/`，`grep -r "guides/protocol" .agent` 0
- `overview §8` 仅索引，`SUMMARY.md` 单一事实源，不再 `§5`
- 外部路径统一 `../k3dit`，`grep -r "k3dit/docs/guides" docs` 全含 `../`
- 新增 SOP 必四件套：`assets` + `PAIRS` + `scaffold` + `expected`，否则 `TEMPLATE_DRIFT`

## 5. 双向回链

- **Audit**: `docs/reviews/2026-08-27-k8d3e-a78-5pass.md: 01-05`
- **Branch**: `docs/branches/2026-08-27-k8d3e-a78-repro.md:1`（`incident` 为主，`branches` 镜像）
- **Tasks**: `docs/tasks/2026-08-27-M6-fix-*.done.md` 5 项
- **Review 回填**: `docs/reviews/2026-08-27-k8d3e-a78-5pass.md: 回填` 已 `已修`
- **ADR**: `ADR 0002` Diátaxis / `ADR 0005` 本地优先
