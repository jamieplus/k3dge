---
status: done
milestone: M10
priority: P1
date: 2026-09-17
---

# 引用便携：k3dge 的 ADR 引用在下游仓指错靶

- **Status**: done
- **Milestone**: M10
- **Priority**: P1
- **可检索摘要**: k3dge 的 `[NEXT]` 与模板 `AGENTS.md` 硬编码了 k3dge 自家的 ADR 编号，下游仓按编号解析会指到**自己的同名 ADR**（错靶）或不存在的文件（悬空）。实测：k3dit/k3che 的 AGENTS.md 各有 4 处悬空引用；`[NEXT]` 引的 ADR-0004/0005 在 k3dit 里存在（指另一件事），ADR-0022/0025 不存在。修法：引用必须便携（自限定或经 `K3DGE_SOURCE` 解析），并加校验 + 便携性测试。
- **Date**: 2026-09-17

## 意图

消除 k3dge 对下游仓的引用污染。这是本会话唯一**已确认影响下游**的缺陷。

## 证据链

### E48 — 真下游仓此刻就是污染状态（实测）

```
k3dit/AGENTS.md  引用 ADR 0010/0012/0014/0015 → 4 处全部悬空（k3dit 只有 0001-0006）
k3che/AGENTS.md  引用 ADR 0010/0012/0014/0015 → 4 处全部悬空（k3che 只有 0001-0003）
```

（注：k3dit/k3che 用 `ADR 0010` 空格格式写，故用 `grep -oE 'ADR[ -][0-9]{4}'` 才抓得到。）

### E49 — `[NEXT]` 同时产生「错靶」与「悬空」（实测）

```
k3dge 的 STATE_OPTIONS 引 4 个自家 ADR：0004 / 0005 / 0022 / 0025

在 k3dit（自家 ADR 为 0001-0006）：
  0004 / 0005  → 【存在】但是 k3dit 自己的决策 ⇒ 错靶（比悬空更糟）
  0022 / 0025  → 不存在 ⇒ 悬空

在 k3che（自家 ADR 为 0001-0003）：
  全部悬空（自家编号不够到 0004）
⇒ 错靶还是悬空，取决于下游的 ADR 数量范围
```

### E50 — 下游跑的确实是本仓这份 k3dge（实测）

```
k3dit/.venv/k3dge-source.txt → /Users/jamie/Workspace/k3dge
k3che/.venv/k3dge-source.txt → /Users/jamie/Workspace/k3dge
```

### E51 — 无闸可查（实测）

```
pre-commit 的悬空 ADR 检查只覆盖 docs/**（scripts/pre-commit:105）
⇒ AGENTS.md 在根目录，不在检查面
⇒ 且 pure_refs.check_dangling_adr 只能查「悬空」，查不出「指错靶」（文件存在）
```

### E52 — 引用不可配（产物）

```
STATE_OPTIONS 硬编码在 src/k3dge/engine/nextstep.py（Python 字面量）
⇒ 下游无法覆盖；且不该覆盖（见「边界」）
```

## 方案

### 1. 引用便携化

| 写法 | 例 | 下游对吗 |
|---|---|---|
| ✅ 相对引用 | `AGENTS.md §12` | 对（不带外部编号） |
| ✅ 自限定 | `k3dge ADR-0004 §2.1.5` | 对（明确是 k3dge 的） |
| ✅ 经源仓解析 | `k3dge doc where --source ADR-0004` | 对（用 `K3DGE_SOURCE` 定位） |
| ❌ 绝对裸引 | `ADR-0004 §2.1.5` | **错靶** |
| ❌ 裸引包在命令里 | `k3dge doc where ADR-0025` | **错靶**（在当仓解析） |

涉及面：
- `src/k3dge/engine/nextstep.py` 的 `STATE_OPTIONS` pointers（9/12 态）
- `src/k3dge/templates/assets/agents.md` 的 8 处（含模板同步两份）
- `src/k3dge/templates/assets/adr-readme.md.template`（它已写「k3dge's own ADRs stay in the k3dge checkout; do not copy them here」——模板自己就在违反）

### 2. 校验（加进已有的 pre-commit schema 闸，不新建机制）

| 检查 | 形态 |
|---|---|
| 裸 ADR 号即红 | `pointers` 与 **AGENTS.md** 不得含未限定的 `ADR[ -]\d{4}` |
| 检查面扩到 AGENTS.md | 现只查 `docs/**`，须加根目录 `AGENTS.md` |
| `[NEXT]` 问号/`y/N` 检查 | **并入本项**（无 incident 记录，不单列）——`[NEXT]` 无应答通道却写「y/N／倒计时」，属虚假承诺 |

### 3. 便携性测试（最有价值的一条）

```
scaffold 一个临时仓 → 跑 k3dge 命令 → 断言 [NEXT] 的 pointers
  在该仓里「要么可解析，要么自限定」
⇒ 一次抓住两层污染（STATE_OPTIONS + 模板），且把「下游才会暴露的问题」
  变成能在本仓跑的测试
```

## 边界与拆分（feat 类必填；规则 08）

- 事实归属：投影词汇（含 pointers）归 `nextstep.STATE_OPTIONS`；模板归 `templates/assets/`；便携解析归 `K3DGE_SOURCE`（机制已有，`gate.sh` 在用它做一致性校验）
- 边界检查：
  - **词汇属协议，不得让下游可配**——否则 agent 面向的协议碎片化，违背 k3dge 作为协议单一源的定位（AGENTS.md §12 触发表必须与之对齐）
  - 所以修法是「让引用便携」，**不是**「让下游改写词汇」
  - 校验器只读（ADR-0006 §2.3.2）
- 桩子先行：先写便携性测试（当轮即红，因 `[NEXT]` 现在就指错靶）→ 再便携化 → 校验转绿

## Notes

### 出处

本票由 `docs/memo/archive/2026-09-16-orchestration-form-exploration.md` §S8 升级而来（memo 下一步第 2、3、5 项合并）。

### 与投影契约的关系

本票是 memo「投影三维契约」第三维（**范围**）的落地：

| 维度 | 由什么决定 | 约束 | 落地 |
|---|---|---|---|
| 目标 | 谁消费 | 判断主体 → 选项；进程 → 闭集判定 | S6 |
| 语法 | 有无应答通道 | 有 → 疑问句；无 → 陈述句 | S7 |
| **范围** | 在哪个仓消费 | **引用必须便携** | **本票** |

### 改动量

`STATE_OPTIONS` pointers ~9 处 + 模板 2 份 + 校验 ~30 行 + 测试 ~20 行。

## 收尾（已完）——**实施与原计划有重要偏差，理由如下**

### 偏差：从「手改 77 处」改为「scaffold 生成时转换」

| | 原计划 | 实际 |
|---|---|---|
| 协议面（AGENTS.md + rules + agent-readme） | 手改 2 份模板（约 44 处） | **scaffold 写入时转换**（`_qualify_adr_refs`，~10 行，覆盖 33 处） |
| `[NEXT]` pointers | 手改 9 处 | 手改 10 处（含 1 处 `note`；含把 `k3dge doc where ADR-0025` 改为文本形式 `k3dge ADR-0025`——它是 pointer，下游会解析到本仓同名 ADR） |
| 校验 | 加进 pre-commit 闸 | **便携性测试**（scaffold 临时仓断言），非闸 |

**为何改机制而不手改**：

1. 手改**不完整**——新写的裸引仍会漏进下游；生成时转换才是根因封堵
2. 手改**易误伤**：`adr-readme.md.template` 的 `k3dge doc where ADR-0001` 指的是**本仓** ADR（不该限定），`08-design-discipline.md` / `10-structure-over-prose.md` 的反引号内 `ADR-0006` / `ADR-0012` 却是设计引用（该限定）——**反引号内外不能机械区分**，手改需逐处判断
3. 转换规则可测：`where ADR-NNNN` 前瞻跳过唯一命令形式，且幂等、不二次限定

### 落地

| 件 | 位置 |
|---|---|
| 转换函数 | `templates/scaffold.py` `_qualify_adr_refs`（应用于 AGENTS.md / rules / agent-readme） |
| pointers 自限定 | `engine/nextstep.py` 10 处 |
| 便携性测试 | `tests/unit/templates/test_reference_portability.py`（9 条：协议面无裸引 / 命令示例保留裸 / 本仓 adr-readme 不动 / STATE_OPTIONS 显示串无裸引 / 转换规则四条） |

### 验证

```
scaffold 临时仓 → AGENTS.md + rules + agent-readme 裸引 0 处；k3dge ADR-… 9 处
[NEXT] 渲染 → pointers: k3dge ADR-0004 §2.1.4 | docs/reviews/
全量 502 passed, 2 skipped；契约已回写
```

### 未做（按规则 12 裁定，附理由）

**`[NEXT]` 语法检查（问号 / `y/N` 虚假承诺）**——原计划并作本项。不做，因为：

- 无 incident 记录 ⇒ 无实测危害（规则 12 第 2 条）
- 修它需把 5 个疑问式状态改为陈述式，是**改 agent 面向文案的语义变更**，不该用未证危害驱动
- reopen 条件：一旦有「agent/人因 `[NEXT]` 写了 y/N 但无应答通道而空等/误操作」的实例

**存量下游仓（k3dit / k3che）不自动回填**——scaffold 只 `_write_if_missing`，不会改写已存在的 AGENTS.md（防覆盖定制）。两仓现有的各 4 处悬空需各自处理。
