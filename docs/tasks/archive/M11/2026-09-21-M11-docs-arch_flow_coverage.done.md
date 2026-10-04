---
status: done
milestone: M11
priority: P2
date: 2026-09-21
---

# 架构总览补全流程与状态变迁 + 状态集覆盖闸 `ARCH_STATE_DOC_DRIFT`

- **可检索摘要**: `overview.md`/`encyclopedia.md` 缺 k3dge 的若干**流程与状态变迁**：task 状态机（两文件 0 命中）、`[NEXT]` 12 态闭集（只零星出现 4–5 个名字）、审计线/棘轮两态与结果闭集、sync 链五步（`extractors`/`reconcile` 零命中）、seal 动作闭集与失败/重入语义、提交门禁的四层实现面（doc-gate/schema/screen/check + commit-msg + CI 三 job）、事件面。另发现两处**文档与代码不符**：`[NEXT]` 优先级顺序写错（`ratchet_open` 实为 priority 5，低于 `seal_ready`/`audit_suggested` 的 4；且缺 `escalated`/`doc_fix`/`audit_open`/`rejected`）。

## 证据

```
grep -cE "TRANSITIONS|in-progress" docs/architecture/{overview,encyclopedia}.md          ⇒ 0 0
grep -cE "extractors|reconcile"    docs/architecture/{overview,encyclopedia}.md          ⇒ 0 0
python -c "from k3dge.engine import nextstep; print(sorted(nextstep.STATE_OPTIONS))"      ⇒ 12 态
overview §7 旧句：优先级 pending_findings > ratchet_open > seal_ready > audit_suggested   ⇒ 与 STATE_OPTIONS.priority 不符
```

## 方案

1. `overview.md` 扩成「状态机与流程总览」：§3.1 同步链五步（性质/写什么/失败语义）、§3.2 提交门禁实现面（hook 四层 + commit-msg + 落点闸 + CI 三 job）、§6.1 Milestone、§6.2 Task FSM（迁移表）、§6.3 `[NEXT]` 12 态 + priority 表、§6.4 审计线/棘轮（协议两态 + 结果闭集 + 本地账是投影）、§7.1 seal 动作闭集与 `on_error`/`on_rerun` 语义 + 相位 3 刷新事实。
2. 修 `[NEXT]` 优先级错误（overview §7 指向 §6.3；encyclopedia §3.2 改为完整 priority 链）。
3. `encyclopedia.md` 只加**术语行 + 指路**（Task FSM / 同步链 / 提交门禁层 / 封版动作闭集 / 事件面），不复制叙事（ADR-0018：非第二套叙事）。
4. `engine/spec.md` §3 补一行 Task 状态机指针 + 不变量（**不复制表格**，避免第四份副本）。
5. 新码 **`ARCH_STATE_DOC_DRIFT`**：`overview.md` 必须列全 `nextstep.STATE_OPTIONS` 与 `TaskState` 的值（反引号标识符级出现性；不解析表格）。

## 边界与拆分

- 事实归属：状态闭集的唯一源在**代码**（`nextstep.py` / `state_machine.py`）；文档是投影 ⇒ 闸只查"有没有列全"，不查表述。
- 不做的：不在 overview/encyclopedia 里抄 `audit_flow` 的相位闭集（那是运行态投影，归 ADR-0025 + 代码）；不给 prose 设闸。
- 与已存在的投影闸（域表 `ARCH_TABLE_DRIFT`）分开：一个查**表行事实**，一个查**状态集齐备**。

## 结案

- 落地：`docs/architecture/overview.md`（§3.1/§3.2/§6.1–6.4/§7.1，§6 改名「状态机与流程总览」）、`docs/architecture/encyclopedia.md`（§3.2 加 5 行术语 + 修优先级）、`docs/specs/engine/spec.md`（§3 Task FSM 指针行 + TC-ENG-28）、`engine/evaluator.py`（`_check_state_doc_coverage`）、`engine/gate_facts.py`（`ARCH_STATE_DOC_DRIFT`）、`tests/unit/engine/test_state_doc_coverage.py`（5 例）。
- 实测：本仓 `overview.md` 列全 12 + 4 个态 ⇒ 闸绿；缺一个态 / 去掉反引号 / 缺文件分别由单测覆盖。
- 验证：`k3dge check --with-tests` 绿（cli/engine/sync/templates）；`pytest -q` 全绿。
- 有意留：`audit_flow` 的相位闭集不在文档逐条抄（ADR-0025 为权威，避免第二份清单）；`escalated`/`rejected` 等播报态只列名与含义，不列文案。
