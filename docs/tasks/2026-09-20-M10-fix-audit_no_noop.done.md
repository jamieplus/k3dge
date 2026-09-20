---
status: done
milestone: M10
priority: P1
date: 2026-09-20
---

# 保证审计不可空转：`run_audit_flow` 必须看 `ok/skipped`，`audit-result` 闭集落进封版提交 trailer

- **可检索摘要**: 传输层把"空转"也报成成功——`_run_manual` 返回 `TransportResult(True, "manual", "…not an independent audit")`（`pipeline_runner.py:339`），`skip` 返回 `TransportResult(True, "skip", "skipped", skipped=True)`（`:376`），而 `run_audit_flow`（`milestone_audit.py:215`）拉起动作后**只看 payload/provider/downgrades 拼提示，从不看 `ok/skipped`**。今天唯一兜底是 `_find_report` 的"报告存在 ∧ 待修=0"，而**旧报告即可满足**（本会话 M10 实测过）。ADR-0004 §2.1.9/§2.1.11 把"审计正常返回"当成版号前进的条件 ⇒ 不先堵这个洞，空转会推进版号，"保证 audit"直接失守。

## Intent

"审计完成"必须是**真实执行**的事实，不是"时间到了"或"存在旧文件"。这是 ADR-0004 §2.1.11 的全部内容，也是本次里程碑流程重设计的底线（比版号、tag、报告都优先）。

## 证据（实测）

```
pipeline_runner.py:339  _run_manual(...) → TransportResult(True, "manual", "manual protocol presented (not an independent audit)")
pipeline_runner.py:376  provider == "skip" → TransportResult(True, "skip", "skipped", skipped=True)
milestone_audit.py:215  produced = run_action(...) 之后只读 produced.payload / .provider / .downgrades
                        ⇒ ok=False 与 skipped=True **都不影响判定**
今天没出事纯靠 _find_report（报告存在 ∧ 待修=0）；旧报告在 ⇒ 空转被当闭环（M10 实测）
本仓 k3dit.actions.audit 的链路是 [mcp, manual]（无 skip），但 manual 兜底等价于"打印协议指针"，
下游仓可声明 skip ⇒ 洞是通用洞，不是本仓配置问题
```

## 方案

```
① 每一跳：produced.ok is True ∧ produced.skipped is False 才算"真跑过"
   · skipped/ok=False ⇒ refused（不推进版号，返回明确"未审成"）
   · downgrades 非空 ⇒ degraded（不是闭环）
② `audit-result` 闭集（单源常量，与 STATE_OPTIONS 同纪律）：
   closed | degraded-manual | escalated | refused
③ 允许推进版号的条件：closed，或（degraded-manual ∧ 有审计席位署名）
   —— 降级不静默：署名（`_SIGN_KEYS` 口径）是降级可接受的前提
④ 落点：seal 写封版提交 trailer（见 `feat-seal_boundary_tag` 票），`audit-result` 是四个键之一
⑤ 返回面：refused ⇒ 明确"未审成、不得封"，**不得**显示为"在办进度"
```

## 边界与拆分（fix 类）

- 事实归属：**执行事实**归 `pipeline_runner`（传输层如实返回 ok/skipped/downgrades，不自己判 merit）；**判定**归 `milestone_audit` / `audit_flow`；**记录**归封版提交 trailer。
- 边界检查：k3dge 不判 merit（ADR-0026 §2.1）——本票只判"这一跳是否真跑"，不看报告质量、不数透镜、不驱动 k3dit 内部轮次。
- 桩子先行：先落 ①②③ 的纯函数 + 单测（喂 skip / manual / ok / downgrades 四种 produced），再接 trailer 写入。

## 验收

```
单测：produced.skipped=True 且仓里存在旧报告 ⇒ 不得判 closed（退 refused）
     produced.ok=False                                    ⇒ 不得判 closed
     downgrades 非空 ∧ 无署名                              ⇒ 不得推进版号
     downgrades 非空 ∧ 有署名                              ⇒ degraded-manual（可推进，trailer 记明）
     produced 全绿且真跑                                   ⇒ closed
```

## Notes

- 与 ADR-0004 §2.1.11 同源。报告闸 `_SIGN_KEYS` 不动：报告仍是"存在则须合格"（`refactor-report_demote` 票）。
- 这是重设计的**第一票**：其余票（相位、tag、报告降级、CHANGELOG）都假定"审计正常返回"已可信。

## 落地（2026-09-20）

| 项 | 落点 | 实测 |
| --- | --- | --- |
| ① 闭集单源 | `audit_flow.AUDIT_RESULTS` / `SEALABLE_AUDIT_RESULTS` / `_STATUS_RESULTS`；`audit_call_result(produced)` + `audit_result_of(status)` | 单测断言闭集字面量与 in-flight（`ratchet_open`/`audit_open`）⇒ `None`（不推进） |
| ② 空转先于报告 | `run_audit_flow` produce 循环：`produced.ok ∧ not produced.skipped` 不成立 ⇒ **在 `_find_report` 之前**返回 `refused` | `test_skip_not_closed_even_with_stale_report`：旧报告在场 + `skipped=True` ⇒ `refused`（旧代码会判闭环） |
| ③ 降级须署名 | `degraded` 累积；报告缺 `_SIGN_KEYS`（`审计人`/`透镜来源`/`基线`）⇒ `refused`；署名齐全 ⇒ `audited_degraded` | `test_downgraded_needs_signature`（拒）/ `test_downgraded_and_signed_is_degraded_manual`（记 `degraded-manual` + 告知行） |
| ④ 传输层同洞 | `submit_audit` / `collect_audit` 的 `skip` 显式拦（此前只在信封校验处以"未按契约返回"擦边拦下） | 错误码 `NOOP`；`test_audit_flow` 的 stub 补 `skipped` 字段（原先缺字段本身就是隐患） |
| ⑤ 拒绝码入表 | `gates.INTERNAL_GATE_IDS` += `audit_noop` / `audit_degraded_unsigned`；`nextstep.GATE_NEXT` + `REJECTION_FACTS` 同轮补 | `test_gate_next_vocabulary_is_closed`（GATE_NEXT ⊆ 声明面）绿 ⇒ 追加码必须同轮声明，不能悬空 |
| ⑥ 消费面 | `cli/main.py` `status.startswith("audited")`；MCP 回包新增 `audit_result` + `audited = result in SEALABLE_AUDIT_RESULTS` | 降级审计不再被 CLI 判失败、也不被 MCP 判"未审" |

测试：`TestAuditNoNoop`（5 条）+ 存量回归；**661 passed, 2 skipped**；`k3dge check` 绿。

**边界（有意留，归后续票）**：本票只让"结果"可判可信，尚未把它写进持久记录（trailer）——那是 `feat-seal_boundary_tag`；`audit-result` 目前只在返回面与 `[NEXT]` 上可见。
