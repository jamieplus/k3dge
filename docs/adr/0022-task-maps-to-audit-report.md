---
Status: Draft
# Append-only after Accepted. Revise via `Amended by` / `Superseded by` below — do
# NOT rewrite this decision's prose in place, and never reuse a number (see README).
Supersedes: -
Amended-by: -
Date: 2026-09-02
Deciders: Core Maintainer (待 k3dit/人 复核后转 Accepted)
Note: ① 就地修订（钉=写源、报告=投影，对齐 ADR-0025 §2.7；原"报告是唯一明细事实源"句作废）2026-09-10，经 Core Maintainer 本轮显式授权，依 `docs/adr/AUTHORING.md`；过闸口径 = manual fallback（实测 `command -v k3dit`/`k3dge` 无输出，no live lens）。
      ② 正交去重（钉收钉细节改指 ADR-0025 §2.7）2026-09-10，经 Core Maintainer 本轮显式授权，依 `docs/adr/AUTHORING.md`；过闸口径同上。
      ③ 正交收尾（seal 全 done 闸复述改指 ADR-0004 §2.1.3）2026-09-10，经 Core Maintainer 本轮显式授权，依 `docs/adr/AUTHORING.md`；过闸口径同上。
      ④ 人读化改写（按 AUTHORING「人读优先」：决策先行、一行一点、长条拆子项；不变量与编号不变）2026-09-10，经 Core Maintainer 本轮显式授权，依 `docs/adr/AUTHORING.md`；过闸口径同上。
---

# ADR-0022: task 对应审计报告（1 report = 1 task），不再一条 bug 一个 task

## 1. 上下文 (Context)

- ADR-0017 的 12 列报告里每条发现（finding）是一个带 ID 的行，`处置` 旧约定为「`待修` 必已转 `docs/tasks/`」。
- 于是**每条 bug 一个 task**，且 `mark_task_done` 用**标题模糊匹配**回填报告行（`_auto_backfill_reviews`）。
- 后果：task 数量随 findings 线性膨胀；task 与报告行靠脆弱启发式配对，形成"task 改了 / 报告没改"的双记账漂移。
- 真正的工作清单是**钉/报告**（写源/投影语义见 ADR-0025 §2.7）。
- task 应是**可追踪单元**，不该是 finding 的影子。

## 2. 决策 (Decision)

- **1 report = 1 task。** 一份审计报告（含 doc-audit）对应**恰好一个** `audit` task。
  - task frontmatter 加指针 `report: docs/reviews/<file>.md`；body 镜像 `- **Report**: …`。
  - findings 只活在钉里（报告是其投影），**不再逐条建 task**。
- **task-done ⇔ 报告闭环。** `mark_task_done` 遇到带 `report:` 的 task 时，**要求该报告 `待修==0` 才允许 done**。
  - 否则拒绝并列出剩余待修 ID。
  - 于是"关 task"和"审计闭环(`audit_closed`)"收敛为同一闸，不再两套记账。
  - `有意留` 不计待修，允许随报告闭环进 LEFTOVERS。
- **关一条 finding = 改树上的钉**：删钉=已修、翻 `leftover`/`disputed`=留/议；不落 task。
  - 收钉语义见 ADR-0025 §2.7。
- **逃生口（默认不拆）**：某条特别大的 finding，可在报告行 `处置` 写 `转 sub-task <id>`，为其单独开一个 task。
  - 这是例外，不是默认；sub-task 与 report-task 无强制关系。
- **`_auto_backfill_reviews`（标题匹配）降为遗留兜底**：仅对**无** `report:` 指针的旧 task 生效。
  - report-task 的闭环以"报告 待修==0 + 人/agent 改钉（报告随之重生成）"为准，不靠标题猜。
- **seal 闸语义收敛**：所有 report-task done 即所有关联报告 `待修=0`（`audit_closed`），少一个会漏的环节。
  - 闸条件见 ADR-0004 §2.1.3。

### 2.1 明确非目标

- 不取消 task——task 仍是里程碑闸与 `task list` 的可见单元（`ADR-0004 §2.1.3`）；只是单元从 finding 上移到 report。
- 不在 task 里复制 finding 明细（那会成第三份事实：报告改了、task 没改）；task 只存 `report:` 指针 + 一行摘要。

## 3. 产生后果 (Consequences)

- **Up**：task 数量 ~ 审计轮数而非 findings 数；钉是唯一写源、报告是其投影，杜绝双写漂移（ADR-0025 §2.7）。
  - 关 task 即证报告闭环；与 doc-audit 的"一报告一 task"一致。
- **Down**：`create_task` 签名新增 `report` 参数（契约变更，需 `k3dge sync`）。
  - `task done` 对 report-task 变严（报告没清空就关不掉）；旧 per-finding task 需按遗留兜底继续工作或人工归并。
- **Reopen when**：若某域 finding 天然需要独立排期/独立里程碑（sub-task 不足以表达），再议把 task 建模成可持有 finding 的层级。
