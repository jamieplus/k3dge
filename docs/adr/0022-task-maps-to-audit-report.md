---
Status: Accepted
# Append-only after Accepted. Revise via `Amended by` / `Superseded by` below — do
# NOT rewrite this decision's prose in place, and never reuse a number (see README).
Supersedes: -
Amended-by: -
Landed-by: src/k3dge/engine/task_write.py
Date: 2026-09-02
Deciders: Core Maintainer (待 k3dit/人 复核后转 Accepted)
Note: ①-⑥ 修订痕迹见 git 历史（2026-09-10 至 2026-09-12：钉=写源/报告=投影对齐 ADR-0025 §2.7、正交去重/收尾、人读化改写、合并原 0021「doc-audit 后置非阻断」入 §2.2、转 Accepted）；新格式自 🅰1 起生效（`Amended-by`），迁移口径同 ADR-0006。
      `Landed-by` 指针 2026-09-19 由已删的 `engine/milestone.py`（兼容门面）改指叶子 `engine/task_write.py`（`mark_task_done`：report-task 闭环闸）——引用面修正，决策未变，故不进 `Amended-by`。
---

# ADR-0022: 审计报告的收口（1 report = 1 task；doc-audit 后置非阻断）

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

### 2.2 doc-audit 后置、非阻断（原独立 ADR，合并入本条）

- **doc-audit 在 `check` 之后，不在 `check` 之内**（T-01 边界；`check` 恒静态，定义见 ADR-0006 §2.3.2）：check 绿后经 `[NEXT] state=doc_audit` 指一条**非阻断**后续步 `k3dge doc-audit`。
- **只出两样**：
  1. **报告**：路由 `k3dit.actions.audit`（`mcp→cli→manual`），做 **authoring 合规**；k3dit/人产 12 列，k3dge 不伪造发现。
  2. **task**：`k3dge` 机械建一个带 `Milestone: <当前>` 的 `doc-audit` task（同里程碑幂等，仅一个未关闭）。
- **耐久 = task 归里程碑**：封板闸要求任务全 `done`（ADR-0004 §2.1.3）；故本轮不改、里程碑闭环轮也得改——"不阻断"却不丢。
- **范围切分**：doc-audit 只管 authoring 合规；**ADR 冲突/覆盖留在里程碑审计**（`k3dge_adr_index` 事实 + k3dit 判），不在每次 commit 做。
- **非阻断 ≠ 无后果**：命令恒返回 0；产出的 task 进 backlog，由既有 seal 闸兜底。
- 非目标：不把 k3dit/MCP/LLM 塞进 `check`；不在 `check` 里写 review/task；doc-audit 不判"值不值得写"（soft review）。

## 3. 产生后果 (Consequences)

- **Up**：task 数量 ~ 审计轮数而非 findings 数；钉是唯一写源、报告是其投影，杜绝双写漂移（ADR-0025 §2.7）。
  - 关 task 即证报告闭环；与 doc-audit 的"一报告一 task"一致。
- **Down**：`create_task` 签名新增 `report` 参数（契约变更，需 `k3dge sync`）。
  - `task done` 对 report-task 变严（报告没清空就关不掉）；旧 per-finding task 需按遗留兜底继续工作或人工归并。
- **Reopen when**：若某域 finding 天然需要独立排期/独立里程碑（sub-task 不足以表达），再议把 task 建模成可持有 finding 的层级。
