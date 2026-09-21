---
status: done
milestone: M10
priority: P2
date: 2026-09-20
---

# 报告降级为可选产物：`audit_closed`/`evidence_chain` 不再卡门、`audit-submit` 只补证据、运行态明标投影

- **可检索摘要**: ADR-0004 §2.1.3/§2.1.10/§2.1.11 定：报告＝**可选产物**（存在则须合格：12 列 + `审计人`/`透镜来源`/`基线`；不存在不卡流程）；`audit_closed`（报告存在 ∧ 待修=0）与 `evidence_chain` **不再是封板前置**；`audit-submit` 只**补证据**，不推进版号、不触发封板；`.agent/audit_jobs.json` 与 `.agent/audit_checklist.json` 是**运行态投影**（冲突以 git 为准）。现状是本会话刚加的两条闸（`audit_fresh` + `[checks.audit].fresh_ignore`）方向相反：把"基线之后有未审改动"当阻断。

## Intent

封板资格不能靠"文件存在性"（旧报告就能满足，M10 实测）；也不能靠"基线 vs HEAD 的相对新鲜度"（边界已改由 tag=B 表达）。报告的价值是**审计证据**，不是**通行证**。

## 证据（实测）

```
audit_trigger.audit_closed = 报告存在 ∧ 待修=0 ∧ 无 `<!-- k3dge:incomplete -->`
seal._audit_fresh_error    = 基线须为 HEAD 祖先 ∧ 基线..HEAD 无未审改动（豁免 fresh_ignore）
                             ⇒ M10 实测 189 处未审改动 ⇒ 永久阻断（而"审哪版封哪版"下这不是问题）
audit_flow.submit_audit    锁 baseline + 建分支；persist_external_audit_report 落盘即被当闭环入口
```

## 方案

```
① audit_trigger.audit_closed：改用途 ⇒ 仅"报告合格性"检查（存在则须合格），不进封板前置
② seal：删 `audit_fresh` 与 `[checks.audit].fresh_ignore`（被 tag 边界取代，§2.1.9）
③ audit-submit / persist_external_audit_report：明写"只补证据"，**不推进版号、不触发封板**
④ audit_jobs / audit_checklist：代码注释 + spec 明写"运行态投影、不作判据、可重建、
   **冲突以 git 为准**"（例：job.state=collected 但仓里无 trailer/tag ⇒ 以 git 为准）
⑤ evidence_chain 的"已入库"要求：降为 advisory（不作为封板前置）
```

## 边界与拆分（refactor 类）

- 事实归属：**报告合格性**归 `process_audit`（`_SIGN_KEYS`，含 `基线`）；**封板判据**归 `seal.py` 唯一构造点；**运行态**归 `.agent/*.json`（本地，投影）。
- 边界检查：不把"报告不存在"变成错误（可选产物）；不让 seal 读 k3dit 的内部（轮次/透镜数）；不新建第二份状态账。
- 桩子先行：先改 `audit_closed` 的用途与删闸（可单测），再改 submit 的语义，最后补"冲突以 git 为准"的判定。

## 验收

```
有旧报告但本轮 skip ⇒ 不得凭报告判闭环（由 `fix-audit_no_noop` 的 refused 拦住）
删 audit_fresh/fresh_ignore 后：基线之后有大量未审改动**不再阻断** seal（边界由 tag 表达）
audit-submit 一份报告 ⇒ 版号不动、无 trailer、无 tag
rm .agent/audit_jobs.json ⇒ 判据不受影响（结论可从 git 重建）
```

## Notes

- `_SIGN_KEYS`（含 `基线`）保留：报告一旦存在就必须合格。
- 与 `refactor-seal_phases` 同轮落最省（都改 `[checks.seal]` 声明面）。

## 落地（2026-09-20）

| 项 | 落点 | 实测 |
| --- | --- | --- |
| ① `audit_closed` 改定性 | `audit_trigger` 文档明写"报告**合格性**，不是封板前置"；消费面只剩 `audit_checklist`（投影）与 `compute_audit_suggestion`（提醒） | `test_report_presence_is_never_a_seal_precondition`（缺省面 + 仓内声明面都验 `audit_closed`/`evidence_chain`/`audit_fresh` 不在任何 preconditions） |
| ② 删 `audit_fresh`/`fresh_ignore` | T2 已随之落地（同一批声明行）；本票补守卫测试 | 同上 |
| ③ `audit-submit` 只补证据 | `persist_external_audit_report` / MCP 文档 + MCP 回包新增 `advances_version: false, triggers_seal: false`；CLI 打印同句 | MCP 回包字段可断言；`audit-submit` 前后版号/`tag` 不变（`TestAuditEvidence::test_absent_tag_means_not_sealed`） |
| ④ 运行态明标投影 | `audit_flow` 模块头 + `audit_checklist` 模块头：本地账可重建、**不作判据**、冲突以 git 为准；新增 `audit_flow.audit_evidence()`（读**边界 tag + 封版提交 trailer**，tag 注解为第二载体） | `TestAuditEvidence`（4 条）：无 tag ⇒ 未封；tag+trailer ⇒ 已封；**tag 无 trailer ⇒ 未封**；**本地账说 collected 但仓里无 tag ⇒ 判未封（git 优先）** |
| ⑤ `evidence_chain` 降级 | 其唯一函数 `evidence_chain_error` 在 src 已无消费者（纯死码）⇒ **删除**；报告合格性留在审计侧用 `_SIGN_KEYS`（T1 的降级署名判据）。`process_audit` 模块头改述"不是封板前置" | `tests/unit/engine/test_process_audit.py` 重写为只测 `_SIGN_KEYS`/`_field`（5 条）；旧 4 条"缺报告/未入库 ⇒ 拒"随判据退休而删 |
| ⑥ `[NEXT]` 判据换源 | `cli/status.lifecycle_next` 与 MCP `align` 分支：`seal_ready` 改由 `seal.unmet_seal_preconditions`（预审＝形式闸）决定，**审计状态不参与** | `test_seal_ready_when_precheck_green` / `test_align_payload_no_checkpoint` 改为断言 `seal_ready` |
| ⑦ `seal-check` 展示证据 | `k3dge milestone seal-check <id>` 追加 `[EVIDENCE]` 行（边界 tag / 封板记录齐否 + "本地账不作判据"），**不影响退出码**（报告是可选产物） | `test_seal_check.test_unmet_exits_one_and_lists_reason` 断言 `[EVIDENCE]` |
| ⑧ 散文同步 | `AGENTS.md` §12 + `.agent/rules/04-milestone.md`（+镜像）：只补证据、可选产物、`audit_closed` 新定性、运行态投影、git 优先 | PAIRS `diff` 一致 |

测试：**668 passed, 2 skipped**；`k3dge check` 绿。

### 顺带补的洞（T3 收尾发现）

「封版记录挂在提交上」在**零改动**时不成立（`_commit_all` 不造空提交 ⇒ 干净树没有载体）。
补法：tag 的**注解正文**同样写 trailer，`audit_evidence` 先沿历史找带 `Seal-milestone` 的提交、
找不到再读注解 ⇒ 两条路都可读回。证据：`test_tag_with_trailers_is_sealed`（干净树 ⇒ 仍 `sealed=True`）。
