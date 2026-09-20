---
type: REG
severity: P0
target_milestone: M2
discovery_date: 2026-08-26
status: closed
root_cause_harness: k3dge
action_task_ref: docs/tasks/2026-08-26-M2-audit-audit_triage_truncate.md
---

# INCIDENT REPORT: [M2 回归] 审计转任务截断致任务失自包含

## 1. 现象与证伪证据 (B-T-D Evidence)
- **预期行为 (Baseline)**: `M2` 的 `13` 条审计任务应如 `M1` 的 `14` 条人读任务般自包含（`可检索摘要` 人话因果 + 位置）
- **现存破损 (Treatment)**: `M2` 的 `13` 条 `audit` 任务 `可检索摘要` 仅复读标题 `slug[:30]`，`M2` 封板后 `archive/M2` 亦 `15` 行空壳，`k3dge check` 仍 `PASS`（`engine` 不验摘要长度）
- **复现路径**:
  ```bash
  k3dge task list --json --milestone M2 | python -c "import json,sys; d=json.load(sys.stdin); print([t['path'] for t in d['tasks']])"
  # 复现：13 条 M2 任务的 可检索摘要 仅标题
  ```

## 2. 根因剖析 (5 Whys)
1. 为什么 M2 任务失自包含？ → `k3dge audit triage` 批量脚本按 `slug[:30]` 截断
2. 为什么脚本会截断？ → `AGENTS.md §5` 未强 `可检索摘要` 需人话，`audit triage` 未读 `reviews` 全文
3. 为什么单测未拦截？ → `M2` 的 `audit` 任务无摘要长度校验，`k3dge check` 不验自包含
4. 为什么审计未发现？ → `k3dit` 透镜的 `Pass 4` 未覆盖 `audit triage` 的落盘转译路径

## 3. 防退化动作清单
- [x] **物理测试加固**: `docs/tasks/2026-08-26-M2-audit-audit_triage_truncate.md` 已回填人话，`k3dge check` 增 `TASK_NOT_SELF_CONTAINED` 轻拦（` mil estone.py`）
- [x] **契约补强**: `docs/specs/cli/spec.md` 的 `audit triage` 矩阵已补 `可检索摘要` 人话校验
- [x] **规则透镜升级**: `k3dit` 的 `Pass 4` 增 `audit triage` 落盘自包含检查
- [x] **关联修复 Task**: `docs/tasks/2026-08-26-M2-audit-audit_triage_truncate.md` 已 `done` 并 `seal` 至 `M2`

## 4. 经验灌入
- `k3che` 的 `BranchThrottler` 已记录"批量截断"反模式，`k3dge` 的 `M3` 起 `audit triage` 改读 `reviews` 全文
