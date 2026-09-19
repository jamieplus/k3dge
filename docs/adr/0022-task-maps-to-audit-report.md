---
Status: Accepted
Supersedes: -
Amended-by:
  - 🅰1 | Core Maintainer | 2026-09-19 | §2.2 重划：doc 合规从「后置审计+报告+票」改为「提交时硬闸 + 新建首次排查 + seal 轮规约化」，耐久从票改闸；报告+票路径退休
Landed-by: src/k3dge/engine/task_write.py
Date: 2026-09-02
Deciders: Core Maintainer (待 k3dit/人 复核后转 Accepted)
Note: 修订痕迹见 git 历史。
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

### 2.2 doc 合规：提交时硬闸 + 新建首次排查 + seal 轮规约化[^🅰1.1]

- **格式在提交时硬闸**（不变）：`docs/<type>/.schema.json` + `scripts/pre-commit`（结构、名实一致、悬空引用、markdown 完整性）。`check` 恒静态（T-01，定义见 ADR-0006 §2.3.2）。
- **新建受管文档首次排查**[^🅰1.2]：主观撰写类（adr / memo / guides / architecture / protocols / incidents / branches）新增时**阻断一次**（`DOC_NEW_UNSCREENED`），要求先排查是否与既存文档冲突/覆盖/只是其子项。
  - **判定与执行归 agent**（进程判不了语义覆盖）；闸只负责把排查送到动手那一刻，回执后同文件不再拦。
  - 确定性流程生成物（`docs/generated|specs|tasks|reviews`）与 aux（README/AUTHORING/_template）不在排查面——它们有权威生成源，不存在"值不值得建"。
- **内容规约化在 seal 轮，不在每次提交**[^🅰1.3]：**外部透镜优先**；降级（peer 不可达）才由 k3dge 按**闭集规则**确定性修（幂等、每条一测、`--dry-run` 可预览）。
  - 可确定修的对象是**硬闸检出项**（已枚举的闭集码），不是软规则；`gate_facts` 的 `fix` 字段是唯一源（实测 10 个确定性可修 : 32 个需判断）。
- **耐久 = 闸，不是票**[^🅰1.4]：`[checks.seal].preconditions` 增 `docs_normalized`（detector 零偏差才过）。
- **不可机检的语义项留里程碑审计**（不变）：「Context 无 timeline」「Decision 只写不变量与 non-goal」「无过程叙述」要读懂语义，**不进自动修**，由里程碑审计的透镜判。
- **范围切分**（不变）：**ADR 冲突/覆盖留在里程碑审计**（`k3dge_adr_index` 事实 + k3dit 判），不在每次 commit 做。
- 非目标（不变）：不把 k3dit/MCP/LLM 塞进 `check`；不在 `check` 里写 review/task；不判"值不值得写"（soft review）。

## 3. 产生后果 (Consequences)

- **Up**：task 数量 ~ 审计轮数而非 findings 数；钉是唯一写源、报告是其投影，杜绝双写漂移（ADR-0025 §2.7）。
  - 关 task 即证报告闭环；与 doc-audit 的"一报告一 task"一致。
- **Down**：`create_task` 签名新增 `report` 参数（契约变更，需 `k3dge sync`）。
  - `task done` 对 report-task 变严（报告没清空就关不掉）；旧 per-finding task 需按遗留兜底继续工作或人工归并。
- **Reopen when**：若某域 finding 天然需要独立排期/独立里程碑（sub-task 不足以表达），再议把 task 建模成可持有 finding 的层级。

---

[^🅰1.1]: 修改：本节原标题「doc-audit 后置、非阻断」，机制为"路由透镜 → 产 12 列报告 → 建里程碑 task"。改为三层（硬闸 / 首次排查 / seal 轮规约化）。理由：该机制实测未走通——`run_doc_audit` 丢弃 `run_action` 返回值（透镜说明、报告落点、脚手架全部蒸发），`_find_report(mid,"audit")` 又把票绑到里程碑**代码**审计报告；唯一真走通的一次（`docs/reviews/2026-09-10-doc-audit-docs.md`，7 条发现全已修 + 独立回填）是**绕开该命令**由席位跑的。按 AGENTS.md §13，没人收到的审计不算证据（缺"到达"环）。

[^🅰1.2]: 新增：原决策只有"改文档 → 后置审计"，没有"新建文档 → 先排查是否该建"。用户裁定（2026-09-19）：值不值得建**是判断但不是软闸**——不值得建就直接并入，由 agent 执行；闸的职责是让 agent 知道要做这件事并拦第一次（制造排查动力），做不做由 agent 定。与 ADR-0026 §2.1 一致（k3dge 不编排 agent 的工作流，只给事实 + 合法选项）。

[^🅰1.3]: 修改：原为"每次文档改动都提示跑 doc-audit（非阻断）"。改为 seal 轮做，且降级时才由 k3dge 自己动手。理由：文档变更是高频事件，用里程碑级透镜接（棘轮链要 bundle + 派席 + collect；M10 那次审计各 pass 合计 3182s）频率/成本不匹配。确定性规约化属**形式层**（闭集规则、幂等、可复跑），不违 ADR-0005 §2.7「k3dge never merit」——merit 仍归外部透镜。

[^🅰1.4]: 修改：原为「耐久 = task 归里程碑」（封板闸要求任务全 done）。实证不足：票能被无意义关掉——`docs/tasks/2026-09-14-M10-audit-doc_audit_adr_guides_memo_4.done.md` 自述「过期空壳：触发时的 4 个文件未记录（建票时只写标题），无可执行内容」，且其 `report:` 绑到 `2026-09-14-M10-audit.md`（待修=0）⇒ 关票不需要任何实际工作。改为闸（detector 零偏差），关不掉。
