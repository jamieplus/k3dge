# M8 真审计（escalated）发现记录

- **Date**: 2026-09-11
- **审计线**: `k3dit/M8`（消费仓 k3dge），基线 `847e253`（round 4）
- **席位**: `deepseek/deepseek-flash`（DeepSeek V4.1 Flash）真 opencode 席位
- **结论**: `escalated`（bounce-cap ×3）；审计线被 verify 否决（`TEMPLATE_DRIFT` + `test_cache_consumer`），不可合主干，已收摊。
- **性质**: 半成品台账，**不是闭环报告**；`待修>0`，不计入 `audit_closed`。放 `archive/` 使其对 `_find_report`（只扫 reviews 顶层）不可见，避免冒充 M8 审计报告。

## 发现（13）

| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| code-1 | 2026-09-11 | 高 | P1 | 缺陷 | `k3dge milestone audit-submit` 调未定义的 `ms` → NameError，恢复路径不可用 | src/k3dge/cli/main.py:777 | 已修 | 已修：导入 `persist_external_audit_report` 并直调；加回归测试 | 源码复核 + test_milestone_audit_submit_persists 通过 | 通过 | 2026-09-11 |
| code-2 | 2026-09-11 | 中 | P2 | 安全 | `search --path` 用户 glob 未收敛，含 `..` 可越界并在 relative_to 抛未捕获 ValueError | src/k3dge/cli/main.py:913 | 待修 | 需人工核（修席称已过 `_rel_within_workspace`） | 修席/复核称已收敛，但审计未闭环 | 待复审 | 待验收 |
| code-3 | 2026-09-11 | 中 | P2 | 正确性 | `collect` 返回 open（待修>0）时棘轮在此不查 pending 即 return closed，疑把未清零审计误报闭环 | src/k3dge/engine/milestone.py:1469 | 待修 | 开 fix task 复核（下方） | 待复现 | 待复审 | 待验收 |
| doc-1 | 2026-09-11 | 中 | P1 | 悬空指针 | `incidents/AUTHORING` 让抄 `_template.md`，但 assets/incidents 无该模板 | src/k3dge/templates/assets/incidents/AUTHORING.md:3 | 有意留 | 模板侧已自包含；剩余 paired repo 文件在 scope 外 | 交主干同步票 | 待复审 | 待验收 |
| doc-2 | 2026-09-11 | 中 | P2 | 悬空指针 | 指向不存在的 `docs/incidents/README.md`，模板集无 incidents README | src/k3dge/templates/assets/rules/07-audit.md:8 | 有意留 | 模板侧改指实存文件；剩余 paired repo 文件在 scope 外 | 交主干同步票 | 待复审 | 待验收 |
| doc-3 | 2026-09-11 | 中 | P1 | 冲突 | `reviews/AUTHORING` 仍写「必须转 tasks」，与 ADR-0022 冲突 | src/k3dge/templates/assets/reviews/AUTHORING.md:21 | 待修 | 修席称已改；待复核 | 待复现 | 待复审 | 待验收 |
| doc-4 | 2026-09-11 | 中 | P2 | 悬空指针 | 引 `AGENTS.md §8 Paired-Artifact Discipline`，assets/AGENTS.md 无 §8 | src/k3dge/templates/assets/rules/02-simplification.md:36 | 有意留 | 模板侧改指 §12；剩余 paired repo 文件在 scope 外 | 交主干同步票 | 待复审 | 待验收 |
| doc-5 | 2026-09-11 | 低 | P3 | 悬空指针 | 指 `overview.md §8`，脚手架 architecture.md.template 只 §0–§5 | src/k3dge/templates/assets/protocols/audit_default.md:25 | 有意留 | 交主干同步票 | 待复现 | 待复审 | 待验收 |
| value-1 | 2026-09-11 | 中 | P2 | 复杂度 | `cmd_mcp` 复杂度 29>10，与 `cmd_milestone align` 重复 | src/k3dge/cli/main.py:525 | 待修 | 开结构票（修席称已抽公共子函数） | 待复现 | 待复审 | 待验收 |
| value-2 | 2026-09-11 | 中 | P2 | 复杂度 | `_check_domain` 复杂度 22>10，三段职责混居 | src/k3dge/engine/evaluator.py:455 | 待修 | 开结构票 | 待复现 | 待复审 | 待验收 |
| value-3 | 2026-09-11 | 中 | P2 | 复杂度 | `mark_task_done` 复杂度 30>10，多职责堆叠 | src/k3dge/engine/milestone.py:586 | 待修 | 开结构票 | 待复现 | 待复审 | 待验收 |
| value-4 | 2026-09-11 | 中 | P2 | 复杂度 | `seal_milestone` 复杂度 34>10，闸机内联堆叠 | src/k3dge/engine/milestone.py:771 | 待修 | 开结构票 | 待复现 | 待复审 | 待验收 |
| value-5 | 2026-09-11 | 中 | P2 | 结构 | `main.py` 1320 行 >1000，路由与实现混居 | src/k3dge/cli/main.py:1 | 有意留 | 迁移全局引用+全量回归，另立结构票 | 修席有意留 | 待复审 | 待验收 |

## 根因与后续
- **verify 假红根因（结构）**：审计 `scope=src` 只拷 src；修席改了 `templates/assets/**`（在 scope 内），但其 paired repo 文件（`.agent/rules/*`、`docs/incidents/*`）在 scope 外，`TEMPLATE_DRIFT` 必红。已开 task 跟踪。
- 被否的 `k3dit/M8` 线已删；本记录取代其价值。
