---
status: done
milestone: M12
priority: P3
date: 2026-09-30
---

# seal 动作声明序的不变量层封堵 + kind/on_rerun 通用强制


## 已确认意图
seal 动作声明序的不变量层封堵 + kind/on_rerun 通用强制

## 可检索摘要
seal 动作声明序的不变量层封堵 + kind/on_rerun 通用强制

## 上下文/切入点
来源：M11 审计 `value-13`（`docs/reviews/archive/M11/2026-09-29-M11-k3dit-bundle-audit.md`）转票。原票两件事，核验后**只剩后半**：

- ✅ **`kind`/`on_rerun` 通用强制——已实现**：`engine/nodes.py` 的 `NODE_DEFAULTS`（fact 必带 `on_rerun`）+ 单一执行器 `run_phase`（未知 id 拒绝、`on_error` 通用语义）；`tests/unit/engine/test_nodes.py` 钉住（fact 必声明 on_rerun ∈ append/reject、`[nodes.*]` 必须被某相位引用、未知 id 拒绝）。此半**不必再做**。
- ⬜ **声明序不变量层——未做，成立**：`[checks.seal].actions` 仍靠**列表顺序**承载正确性（`pipeline.toml:83-84`：archive→version_bump→closure_note→seal_record→prune）；`[nodes.*]` 的 `needs`/`produces` 全仓**无人消费**（`produces` 仅 `archive`/`seal_record` 声明，grep 无读取点）。value-13 的根因「靠排序耦合」还在：后续动作插错位置会重造 `closure_after_record` 三症状（工作树 ??、DOC_INDEX_STALE、版本多记一拍）。

**剩余范围**：把「进提交的产物集合」由动作表改为对提交阶段的显式输入（或加声明面环校验），使 `seal_record` 不再依赖前序动作副作用顺序；或在 ADR 写明为何保留声明序。按规则 12，加环校验＝新机制，需先有消费者。

## 落地（2026-10-04）

- **`kind`/`on_rerun` 通用强制**：已在 M11 前落地（`engine/nodes.py` 的 `NODE_DEFAULTS` + `run_phase`，
  `tests/unit/engine/test_nodes.py` 钉住）——本票不重复。
- **声明序不变量层封堵**：新增 `pipeline_schema._validate_seal_action_order(data)`，对
  `[checks.seal].actions` 的成对相对序做静态校验（`full_matrix→audit→archive→version_bump→
  closure_note→seal_record→prune`；缺省走 `gates.DEFAULTS` 合法序、只比有依赖的对、容忍缺项与插入），
  乱序 ⇒ `PIPELINE_SCHEMA_INVALID`（复用现役码；`fix=judgment`，无需新三件套）。接入
  `validate_pipeline_config`，故 `k3dge check` 在声明面即挡。
- **文档**：ADR-0004 §2.1.9 增「声明序＝正确性（不变量，带闸）」条，写明为何保留声明序、乱序的已证症状
  （`closure_note` 晚于 `seal_record` ⇒ 派生投影漏提交；`version_bump` 晚于 `seal_record` ⇒ 版本多记一拍）。
- **验证**：`tests/unit/engine/test_pipeline_schema.py::test_seal_action_order_invariant`（合法序/三种乱序/缺省）；
  `pytest tests` 1280 passed, 10 skipped；`k3dge check` 绿。
