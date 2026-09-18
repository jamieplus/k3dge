---
status: done
milestone: M10
priority: P2
date: 2026-09-16
---

# 术语清理：deferred 值级碰撞 + 两处重复常量

- **Status**: done
- **Milestone**: M10
- **Priority**: P2
- **可检索摘要**: 三项证据确凿的术语/事实源问题：(1) `deferred` 在同一仓内跨「里程碑域」与「任务域」两义混用（值级碰撞，两处均为用户可见）；(2) `_VALID_PROVIDERS` 在 `pipeline_runner` 与 `pipeline_schema` 各定义一份；(3) `adr_gate._SKIP` 与 `milestone_files._DOC_AUX_NAMES` 实测完全相同却不共用。
- **Date**: 2026-09-16

## 证据链

### E14 — `deferred` 跨两域（产物）

| # | 位置 | 含义 | 域 | 持久化 |
|---|---|---|---|---|
| ① | `nextstep.py:78` STATE_OPTIONS | 放弃封板 | 里程碑 | 否 |
| ② | `seal_flow.py:141` 返回 status | 同上 | 里程碑 | 否 |
| ③ | `task_index.py:13` + `tasks/.schema.json` | 任务推迟 | 任务 | **是** |
| ④ | `state_machine.py:17` `TaskState.DEFERRED` | 同上 | 任务 | 否 |

消费点证据（①② 必须同改）：
```
cli/mcp.py:443   nextstep.NextStep.from_state(status, milestone_id)
                 if status in ("deferred", "escalated", "audit_needed")
```
seal-flow 的返回 status **被直接当作 nextstep state 名** ⇒ 二者是同一字符串的两处出现。

### E18 — 文档零影响（消费者）

`deferred` 的全部文档提及均属**任务域**：
```
docs/adr/0005-local-first-and-layer-cuts.md:55   Status 只校验枚举 {idea, deferred, in-progress, done}
docs/adr/0018-doc-readme-anchor-governance.md:55 idea → deferred → in-progress → done
docs/tasks/AUTHORING.md:3                        Status ∈ {idea, deferred, in-progress, done}
```
**无任何文档提及 seal status 的 `deferred`** ⇒ 改里程碑域该值零文档改动，反证其为撞名而非有意术语。

### E15–E17 — 重复常量（产物）

```
E13  adr_gate._SKIP        = ['AUTHORING.md', 'README.md', '_template.md']
     milestone_files._DOC_AUX_NAMES = ['AUTHORING.md', 'README.md', '_template.md']
     set 相同: True

E15  pipeline_runner.py:52  _VALID_PROVIDERS = frozenset({"mcp","cli","manual","skip"})
     pipeline_schema.py:29  _VALID_PROVIDERS = frozenset({"mcp","cli","manual","skip"})

E16  milestone_files 依赖：仅 re          → adr_gate 可安全复用
E17  adr_gate 依赖：仅 re                 → 无环
E15  pipeline_runner 依赖：mcp_json(+stdlib) → 新增 pipeline_schema 边为 lifecycle→gate，允许
```

## 改动

### 1. 里程碑域 `deferred` → `seal_declined`

选此名理由：与既有 `seal_ready` 同族；语义准确（封板被婉拒）。

| 文件 | 改动 |
|---|---|
| `engine/nextstep.py:78` | STATE_OPTIONS 键 |
| `engine/seal_flow.py:121,139,141` | docstring + `from_state` + return |
| `cli/main.py:660-661` | 退出码判据 + 注释 |
| `cli/mcp.py:443` | 元组判据 |
| `tests/…/test_nextstep.py:35` | `from_state("deferred", "M7")` |
| `tests/…/test_seal_flow.py:234` | `assertEqual(status, "deferred")` |

**不动**：任务域（③④）——已持久化进 task frontmatter，且有文档与 ADR 锚定，改它代价与风险都大。

### 2. `_VALID_PROVIDERS` 单源

`pipeline_schema` 是「什么取值合法」的结构权威（且为叶子模块，只依赖 stdlib）⇒ 由它拥有；`pipeline_runner` 改为 import。

### 3. `adr_gate._SKIP` 复用 `_DOC_AUX_NAMES`

删 `adr_gate._SKIP`，改 import `milestone_files._DOC_AUX_NAMES`。

## 边界与拆分（feat 类必填；规则 08）

- 事实归属：审计腿/封板状态名归 `nextstep.STATE_OPTIONS`；合法 provider 集归 `pipeline_schema`；doc 辅助文件名集归 `milestone_files._DOC_AUX_NAMES`
- 边界检查：① 两域同步改（`cli/mcp.py` 依赖同名）；② `pipeline_runner→pipeline_schema` 为 lifecycle→gate，不违反 gate ↛ lifecycle；③ `adr_gate→milestone_files` 后者仅依赖 re，无环
- 桩子先行：逐项改完即跑相关测试，三项独立可回退

## 验证

| 检查 | 结果 |
|---|---|
| V1 `adr_gate` 无 `_SKIP` 残留 | ✅ |
| V2 `_VALID_PROVIDERS` 只剩 `pipeline_schema.py:29` 一处定义 | ✅ |
| V3 里程碑域 `deferred` 残留 | ✅ 无 |
| V4 任务域 `deferred` 保留（`task_index:13` + `state_machine:17`） | ✅ 按预期 |
| 全量测试 | **479 passed, 2 skipped**（原 477，+2 守卫） |
| `k3dge sync` | engine 契约已回写；`generated/api.md` 中 STATE_OPTIONS 已含 `seal_declined`、旧 `deferred` 条目消失 |

### 新增守卫

| 守卫 | 钉住什么 |
|---|---|
| `test_no_state_name_collides_with_task_status` | `set(STATE_OPTIONS) & set(_ALLOWED_STATUS) == ∅`——下一次态名撞名会红 |
| `test_valid_providers_has_single_source` | `pipeline_runner._VALID_PROVIDERS is pipeline_schema._VALID_PROVIDERS`（同一对象） |

## Notes

- 改动量：~10 处字面量 + 2 处 import + 2 条守卫
- MCP 面变化：`k3dge_milestone_seal` 返回 JSON 的 `status` 值由 `deferred` 变 `seal_declined`（外部消费者可见，属契约变更）⇒ 已跑 `k3dge sync`
- 记入 LEFTOVERS（待真出误读再动）：TERM-01 `scope` 四义、TERM-02 `kind` 三义、TERM-03 `state` 四义、DUP-01 `AUX_NAMES` 刻意复制（已有守卫）
