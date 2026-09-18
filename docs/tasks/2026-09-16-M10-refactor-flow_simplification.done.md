---
status: done
milestone: M10
priority: P1
date: 2026-09-16
---

# 流程精简：审计腿模式显式化 + 修 doc-audit 空壳票

- **Status**: done
- **Milestone**: M10
- **Priority**: P1
- **可检索摘要**: 三项流程级断言经运行时取证后**两项被自己的证据推翻**：scaffold 腿并非死代码（peer action 仍声明、8 个测试覆盖），报告覆盖闸不存在不对称风险（kind 已编入文件名）。真正可证的缺陷是「默认值与全部实配不一致 + 测试静默依赖默认值 + 测试名与实际路径不符」与「doc-audit 票丢弃已知文件清单」。已修后者，并把前者显式化 + 加回归守卫。
- **Date**: 2026-09-16

## 意图

用可复跑命令证明每个断言，只改证据支持的部分。

## 证据链

### E1 — ratchet 模式下 scaffold 段是 no-op（✅ 成立）

```
_audit_mode(ws)      = 'ratchet'      # 用本仓实际 pipeline.toml
run_action 调用次数  = 0              # produce 循环体零迭代
bump_verify_attempt  = 1              # 无意义自增
reset_verify_attempts= 1              # 无意义重置
返回 status          = 'audited'
```
探针：mock `run_action`/`bump`/`reset` 计数 + mock `_ratchet_audit_step` 返回 closed。

### E2 — 生产从不选 scaffold（✅ 成立）

```
.agent/pipeline.toml:23                              mode = "ratchet"
src/k3dge/templates/assets/pipeline.toml.template:23  mode = "ratchet"
```

### E3 — 「零测试覆盖 scaffold」❌ **断言错误，已推翻**

`_ws()`（test_seal_flow.py:43）**不写** pipeline.toml → `_audit_mode` 回落默认 `"scaffold"` → 7 个测试实跑 scaffold 路径。`_ws_r()`（:451）才显式写 ratchet。

先前 grep 的是 `mode.*scaffold` 字面量，漏掉「不写 mode 键即走默认」这一情形。

### E6 — scaffold 不是死代码（❌ **断言错误，已推翻**）

```
milestone_audit.py:201  streams = {"audit": ("k3dit.actions.audit", "k3dit.actions.verify")}
.agent/pipeline.toml:53 [peers.k3dit.actions.audit]     ← 仍声明
.agent/pipeline.toml:59 [peers.k3dit.actions.verify]    ← 仍声明
模板同上（:53 / :59）
```
两个 action 在本仓与模板都仍声明 ⇒ scaffold 腿**已接线、可跑、有测试**，只是无人选用。删它属策略决定，不属技术清理。

### E4 — 报告覆盖闸不对称有风险 ❌ **断言错误，已撤回**

运行时实测：
```
quality 提交 → 2026-09-16-M10-ext-quality.md
audit   提交 → 2026-09-16-M10-ext-audit.md
同一文件?     False
原案卷被覆盖? False（首行仍为 <!-- k3dge:kind: quality -->）
```
两条路径都把 kind 编入文件名 ⇒ 跨类碰撞不可能发生。`collect_audit` 那道闸防的是「文件名与内容标记不匹配」的外部文件（来自 peer/worktree），不是本函数场景。

### E5 — doc-audit 空壳票（✅ 成立）

```
_ensure_doc_audit_task(workspace, milestone_id, docs, report)   # 签名接收 docs
  docs 仅用于：scopes = {d.split("/")[1] for d in docs} → 拼 title
  文件清单从不写入任务体
实票 2026-09-14-M10-audit-doc_audit_adr_guides_memo_4.done.md：
  ## 已确认意图 / ## 可检索摘要 / ## 上下文/切入点  ← 三段同文
```

### E10 — 该测试的 setup 惰性（✅ 成立，额外发现）

`test_audit_ratchet_closed_is_audited_without_quality` 名字说 ratchet、实跑 scaffold，且写 `audit_jobs.json`：
```
有 audit_jobs.json → status: audited | 该文件被 open 次数: 0
无 audit_jobs.json → status: audited | 该文件被 open 次数: 0
```
`Path.open` 探针证明 scaffold 路径从不读该文件 ⇒ setup 惰性，测试名撒谎。

## 改动

### 1. `engine/task_write.py` — `create_task` 新增 `context` 参数

`## 上下文/切入点` 段改为 `context or title`。docstring 写明：已知具体范围的调用方**必须**传，否则产出无人能执行的票。

公开签名变更 ⇒ 已跑 `k3dge sync` 回写 engine 契约哈希。

### 2. `engine/doc_audit.py` — `_ensure_doc_audit_task` 传入文件清单

```python
context = (f"本次触发 doc-audit 的受管文档（{len(docs)} 份），逐份对照 "
           f"`docs/<type>/AUTHORING.md` 检查作者合规：\n\n"
           + "\n".join(f"- `{d}`" for d in sorted(docs)))
```
E7 验证：4 份文件全入体（`E7c: True`），三字段不再同文（`E7d: False`）。

### 3. `tests/unit/engine/test_seal_flow.py` — 模式显式化 + 4 条回归守卫

- 新增 `_ws_scaffold()`（写显式 `mode = "scaffold"`）；7 处 `run_audit_flow` 测试改用它。**行为中性**：改后 44 passed 与改前一致
- `test_audit_ratchet_closed_is_audited_without_quality` → 改名 `test_single_audit_report_suffices_without_quality`，删惰性 `audit_jobs.json` setup，docstring 记录改名理由与 E10 实测
- 新增守卫：
  - `test_default_mode_is_scaffold_not_ratchet` — 钉住默认值，改动须为有意
  - `test_repo_and_template_declare_ratchet` — 钉住 E2 生产配置事实
  - `test_ratchet_closed_invokes_zero_peer_actions` — 钉住 E1（`calls == []`）
  - `test_task_body_lists_the_actual_files` — 钉住 E5/E7 修复

## 边界与拆分（feat 类必填；规则 08）

- 事实归属：任务体内容归 `task_write.create_task`（`context` 参数）；doc-audit 范围事实归 `doc_audit`；审计腿形状归 `milestone_audit._audit_mode`
- 边界检查：`context` 为可选参数，缺省行为不变（`context or title`）⇒ 其余 3 个 `create_task` 调用方零影响
- 桩子先行：先取运行时证据 → 只改证据支持的部分 → 每步跑测试

## 验证

- 全量 **477 passed, 2 skipped**（原 473，+4 守卫）
- `_ws_scaffold()` 替换后 test_seal_flow 44 passed，与替换前一致 ⇒ 行为中性得证
- `k3dge sync`：engine 契约已回写

## 未做（证据不支持或属策略决定）

| 项 | 原因 |
|---|---|
| 删 scaffold 腿 79 行 | E6 证明它已接线可跑、E3 证明有 7 个测试覆盖。删除是策略决定，需先裁决「scaffold 是否为受支持的降级形态」 |
| 改 `_audit_mode` 默认值为 ratchet | 会让缺 `mode` 键的下游仓静默换审计腿形状；若其 peer 只实现 `actions.audit`/`verify` 则会断。属兼容性决定，非清理 |
| 补 `persist_external_audit_report` 覆盖闸 | E4 撤回：不存在该风险 |

## Notes

- 本票最大产出不是代码改动，而是**证据链推翻了自己 3 条断言中的 2 条**。若按原断言直接动手，会删掉一条有测试、已接线的可用路径，并给一个不存在的风险加保护
- 遗留策略问题（待人裁决）：scaffold 腿是「受支持的降级形态」还是「应删的遗留」？前者需补文档说明何时该用它；后者需迁移 7 个测试到 ratchet 语义并移除 `actions.audit`/`verify` 声明
