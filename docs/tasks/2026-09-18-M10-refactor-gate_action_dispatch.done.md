---
status: done
milestone: M10
priority: P2
date: 2026-09-18
---

# 判定到动作的结构化派发：gate_id 到 action（替掉散文子串匹配）

- **Status**: done
- **Milestone**: M10
- **Priority**: P2
- **可检索摘要**: 闸拒绝后，`nextstep.next_for_rejection` 靠在错误**文案里搜关键词**（`"no 12-col audit report" in msg`、`"未审计" in msg`）决定下一步提示；文案一改分支静默失效。改为拒绝携带闭集 `gate_id`（`Rejection`，str 子类，向后兼容），派发表在 `GATE_NEXT`：id → (state, note)。源：`docs/memo/archive/2026-09-16-orchestration-form-exploration.md` §S7 对偶表（投影给**进程**的判定必须是闭集 bool/enum，禁散文）。
- **Date**: 2026-09-18

## Intent

`[NEXT]` 是投影给「进程」的判定通道，必须是闭集；现状是散文子串匹配，属形态错误（memo §S7）。同一仓已有同类前科：`docs/reviews/archive/untagged/2026-08-24-5pass-audit.md` A-01（子串匹配里程碑 id，`M1` 被 `M10` 误放行）。

## 证据（实测）

```
src/k3dge/engine/nextstep.py:192
    msg = (message or "").lower()
    if "no 12-col audit report" in msg or "audit-submit" in msg:  → 提示去交报告
    if "audit_needed" in msg or "未审计" in msg or "not audit" in msg: → 提示去审计
    return "rejected" + 原文                                        ← 兜底：无下一步

拒绝理由的**真实来源**已是声明式闸 id：
    .agent/pipeline.toml [checks.seal].preconditions =
      [tasks_all_done, audit_closed, evidence_chain, align_pass,
       guides_filled, adrs_all_accepted, adr_landed]
    src/k3dge/engine/seal.py:182 gate_fns 已按 id 求值
⇒ id 在产出点已知，却在返回时被压成字符串，消费点再靠猜关键词还原
```

调用点 6 处：`seal_flow.py:180,185`、`milestone_audit.py:251`、`cli/main.py:610`、`cli/mcp.py:393,420,444`。

## 方案（已定形）

| 层 | 归属 | 内容 |
|---|---|---|
| 拒绝事实 | `engine/gates.py` | `Rejection(gate_id, message)`——**str 子类**：既有 `print(msg)` / `assertIn(x, msg)` / `(bool, str, ...)` 签名全不动，id 随消息一起流到消费点 |
| id 词表 | `engine/gates.py` + `pipeline.toml` | 闸 id 仍由硬闸契约声明；新增内部 id（`audit_report_missing` / `audit_open_declined` / `unknown_gate_id` / `unknown_action_id`） |
| 派发 | `engine/nextstep.py` | `GATE_NEXT: id → (state, note_key)` 闭集表 + `REJECTION_NOTES`；**不在表里的 id 走 `("rejected", None)`，原文照登，不猜** |
| 消费 | 6 个调用点 | 不改签名（`Rejection` 是 str），只在产出点包一层 |

刻意不做：把 `run_milestone_alignment` / `run_seal_flow` 的返回元数改成带 id 的三/四元组——`Rejection` 是 str 已足够，改元数会波及全部 CLI/MCP 调用点与测试而无增益（规则 02）。

## 边界与拆分（规则 08）

- 事实归属：**闸 id 词表归 `gates.py`**（谁声明谁拥有）；**id → state 的映射归 `nextstep.py`**（谁拥有 state 词表谁拥有路由）；`seal.py`/`align.py`/`milestone_audit.py` 只产出 id，不知道 state 存在。
- 边界检查：`nextstep` 不读 `seal` 的内部（不知道有几个闸、什么顺序）；`seal` 不读 `STATE_OPTIONS`。两侧只经 `gate_id` 这个闭集字符串通信。
- 桩子先行：`Rejection` + `GATE_NEXT` 先落（表里只有现有两条路由，行为等价），再逐个产出点换掉字符串；每步 `pytest` 绿。

## 验收

- `next_for_rejection` 内不再出现任何 `in msg` 形式的文案匹配（守卫测试锁死）。
- 裸 str（无 `gate_id`）传进来 → `state="rejected"` + 原文，**不猜**。
- 已知 id → 表驱动到既有 state/note，行为与改前一致（`audit_closed`→`audit_needed`；`audit_report_missing`→ 提示 `audit-submit`）。
- `k3dge sync` 回写契约哈希；`k3dge check` 绿；全量 pytest 绿。

## 落地（2026-09-19）

| 位置 | 改法 |
|---|---|
| `gates.Rejection(gate_id, message)` | 新增：str 子类，携 `gate_id`；`(ok, msg)` 元数、`print(msg)`、`assertIn(x, msg)` 全不动 |
| `gates.rejection(msg, fallback_id)` | 新增：失败返回值正规化（已是 Rejection 则透传） |
| `gates.INTERNAL_GATE_IDS` | 新增：不经契约声明的内部 id 词表（`audit_report_missing` / `audit_open_declined` / `unknown_gate_id` / `unknown_action_id` / `milestone_id_invalid` / `no_tasks` / `invalid_task_status` / `align_failed` / `archive_failed`） |
| `nextstep.GATE_NEXT` + `REJECTION_NOTES` | 新增：`id → (state, note_key)` 闭集派发表；**不在表里 ⇒ `rejected` + 原文照登** |
| `nextstep.next_for_rejection` | 重写：读 `gate_id`（入参或 `Rejection` 自带）查表；**删除全部 `in msg` 文案匹配** |
| `nextstep.STATE_OPTIONS["rejected"]` | 补齐兑底态（原本 `rejected` 在 state 词表里无条目，却已被三处返回——词表不闭） |
| `seal.seal_preconditions_error` | 返回 `Optional[Rejection]`，`gate_id` 就是契约里声明的那个 id |
| `seal.seal_milestone` / `align.run_milestone_alignment` / `align._align_run_gates` | 失败路径包 `Rejection`（id 在产出点已知） |
| `seal_flow` 动作循环 | 未知动作 id → `unknown_action_id`；动作失败 → `gates.rejection(out, aid)` |
| `milestone_audit` | 两处手写 `NextStep(state="rejected", note=...)` → 走 `Rejection` + 派发表 |
| `cli/mcp.py` audit/seal 分支 | 不再拿流程返回的散文消息重猜：`nextstep.load_persisted(ws)` 直接投影流程已判定的那一份（sidecar，rules/11）；同时去掉 `status in ("seal_declined","escalated","audit_needed")` 白名单（新增态就要改）→ `status in STATE_OPTIONS` |
| `nextstep.load_persisted(ws)` | 新增：读 `.k3dge/next.json`；坏/缺 ⇒ None（不抛）。消费者：MCP 两分支 |

## 验收（实测）

```
tests/unit/engine/test_nextstep.py
  test_rejection_maps_to_action            audit_report_missing → audit-submit 提示；audit_closed → audit_needed
  test_rejection_without_gate_id_does_not_guess
      裸 str 写满「未审计」/「no 12-col」/「audit-submit」也只能 rejected + 原文
      —— 直接锁死旧病（改前这四串均被子串匹配命中）
  test_explicit_gate_id_kwarg_wins / test_unknown_gate_id_falls_back
  test_gate_next_vocabulary_is_closed      GATE_NEXT 的 key ⊆ 契约声明 id ∪ INTERNAL_GATE_IDS；
                                           value 的 state ⊆ STATE_OPTIONS、note_key ⊆ REJECTION_NOTES
tests/unit/engine/test_nextstep.py::TestPersistedProjection   sidecar 往返 + 坏 JSON/无 state ⇒ None
tests/unit/engine/test_seal_flow.py::TestGateIdDispatch
  test_audit_flow_rejection_routes_by_gate_id / test_declined_fix_routes_by_gate_id
  test_seal_preconditions_rejection_carries_declared_gate_id  （id == 契约声明的 id，且仍是 str）
  test_seal_flow_rejection_is_table_driven                    （原文照登 + 表驱动 note）

521 passed, 2 skipped；k3dge check 绿；k3dge sync 回写 engine 契约哈希
```

## Notes

- 与 `2026-09-17-M10-refactor-decision_single_source`（P3）同属 memo §S7 的两条对偶约束：本票管**投影给进程**（闭集判定），那票管**投影给判断主体**（文案单源）。两票互不依赖，可分别落。
- memo 的另三条不变量（问号结尾、options ≥2、播报态无分支）用户已裁定 B「只删装饰词」，不在本票范围。
