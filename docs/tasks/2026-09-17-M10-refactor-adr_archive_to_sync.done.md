---
status: done
milestone: M10
priority: P1
date: 2026-09-17
---

# ADR 归档移出封板（seal → sync）+ 删冗余 gates.toml

- **Status**: done
- **Milestone**: M10
- **Priority**: P1
- **可检索摘要**: ADR 自动归档（`reconcile_supersedes`）被放在 seal 的**只读判定通道**里，导致三个后果：它返回的「修复成功报告」被当拒绝理由（首次封板被拒）；本仓 `gates.toml` 覆盖列表漏了它（功能静默死亡）；它从不被调用但 6 个测试直接调函数（测试掩盖生产失效）。根因不是「通道选错」而是「**放错了侧**」——它的触发源是文件里的声明（作者/提交时事件），产出是派生状态，该在 `k3dge sync`。同时删掉本仓多余且已漂移的 `.agent/gates.toml`。
- **Date**: 2026-09-17

## 意图

**原始方向**：commit 是闸；闸红后由【已有的修复命令】修；seal 只判不修。

本票是这一方向在「ADR 归档」这件事上的落地：把该在 commit 侧做的活从 seal 侧拆出来，**拆除 bug 出现的环境**，而不是在 seal 内改判定条件。

## 证据链

### E-A — 本仓 `.agent/gates.toml` 是 DEFAULTS 的冗余副本（实测）

可复跑：

```python
import tomllib
from pathlib import Path
from k3dge.engine import gates
d, t = gates.DEFAULTS, tomllib.loads(Path(".agent/gates.toml").read_text())
print("相同段:", sorted(s for s in set(d) | set(t) if d.get(s) == t.get(s)))
print("唯一差异:", set(d["checks"]["seal"]["preconditions"]) - set(t["checks"]["seal"]["preconditions"]))
```

输出：

```
相同段: ['audit_trigger', 'markers', 'output', 'search']    ← 4/5 段一字不差
唯一差异: {'reconcile_supersedes'}                          ← 抄漏的那一行
```

补充实测：

- 该文件头注释自称「此处只列本仓覆盖（**可删**，删则用缺省）」⇒ 实际无任何真实覆盖项，**违反自身契约**
- `scaffold.py` 不为新仓写它 ⇒ 下游仓本无此文件
- `gates.load` 对缺失文件回落 DEFAULTS（`gates.py:39-40`）⇒ 删除安全
- `tests/unit/engine/test_gates.py` 自建临时 `gates.toml` ⇒ 不依赖本仓这份
- `pairs.py` 未配对它 ⇒ 无漂移闸

### E-B — `reconcile_supersedes` 放在 seal 里的三个后果（实测）

**E39 首次封板被拒**：

```
第一次调用返回: '[ADR RECONCILED] 0001-old.md → obsolete/ (Superseded by ADR-0002)'
第二次调用返回: None                                    ← 幂等
seal 闸循环（seal.py）：err = fn(); if err: return err   ← 非 None = 拒绝理由
⇒ 它真干活时，那句「我修好了」被当拒绝理由 ⇒ 封板被拒
⇒ 再跑一次才过（第二次无事可做）
```

作者意图（`adr_gate.py` docstring「返回修复报告或 None」）与消费者契约（拒绝）相反。

**E43 声明漏项**：

```
gates 生效列表（本仓）: ... guides_filled, adrs_all_accepted, adr_landed
seal.py 注册:            ↑ 上述 7 项 + reconcile_supersedes
⇒ 孤儿注册，无任何检查发现
```

**E44 功能静默死亡**：

```
它唯一的调用路径 = seal 闸循环（只遍历【声明列表】里的 id）
本仓声明列表不含它 ⇒ 从不被调用
但 6 个测试直接调 adr_gate.reconcile_supersedes(...) ⇒ 全绿
  ⇒ 「测试覆盖的是生产不走的路径」
```

**E45 从未被行使**：`grep '^Supersedes: ADR' docs/adr/*.md` 零命中。

### E-C — `sync` 与 reconcile 同性质（实测）

```
k3dge sync 现在干的活：
  contract hash 回写     ← 从代码重建派生状态
  docs-index 重建        ← 从文档重建派生状态
  extractor 插件生成     ← 从 toml 重建派生状态

reconcile_supersedes      ← 从 `Supersedes:` 声明重建 docs/adr/ 归档状态  ← 同性质
```

且 `sync` 本就写文件 ⇒ **无通道语义冲突**（不像 seal 的只读判定通道）。

### E-D — `sync` 缺 ADR 触发词（实测）

```
AGENTS.md §12 中 k3dge sync 只被两条触发：
  "Public signature" → k3dge sync
  "新建 src/ 域"     → 补 manifest+spec+tests，再 k3dge sync
写 ADR / 声明 Supersedes 【不在其中】
⇒ 只做①，agent 不会被提示跑 sync ⇒ ① 不完整
```

### E-E — 没有闸能查「声明了却没归档」（实测）

```
pure_refs 已有 ADR 规则：check_dangling_adr（悬空引用）、check_adr_consistency（编号一致）
两者都不查「声明了 Supersedes 但目标未标记/未归档」
接线点已存在（scripts/pre-commit 的 ADR 规则调用处）
```

## 方案

### ① `reconcile` 从 seal 移到 `k3dge sync`

| 位置 | 改动 |
|---|---|
| `seal.py` `gate_fns` | 删条目 |
| `gates.py` DEFAULTS `seal.preconditions` | 删 `reconcile_supersedes` |
| `sync/generator.py` `sync_all` | 加一步（与 `extractor_gen` 同级；报告一行） |

效果：seal 里不再有变更步 ⇒ **E39 的环境不存在**；功能真跑 ⇒ **E44 修**。

### ② 删 `.agent/gates.toml`

⇒ **E43 根因消除**（双源消失，declaration 只剩 DEFAULTS 单源）。

> ⚠️ **必须与①同做**：单独删会把 reconcile 重新激活在 DEFAULTS 的 preconditions 里
> ⇒ E39 立刻回归（等真封板时发作）。已验证：删掉后生效列表变回 8 项（含 reconcile）。

### ③ pre-commit 加规则：声明了却没归档即红

```
规则：ADR-X 声明 `Supersedes: ADR-Y` ⇒ ADR-Y 必须 Status: Superseded 且位于 obsolete/
否则红，提示：run `k3dge sync`
落点：pure_refs 的 ADR 规则族（已有两条）⇒ 零新基建，接线点已存在
```

这一步**不是可选项**，而是①的完整性的组成部分：没有它，agent 没有信号去跑 sync（E-D），
归档会退化成「要记得手动跑」（即换个形态的静默失效）。

## 边界与拆分（feat 类必填；规则 08）

- 事实归属：派生状态重建归 `sync`（`sync_all`）；只读判定归 `pure_refs`（pre-commit 闸）；封板判定归 `seal` 的 preconditions
- 边界检查：
  - `sync` 是变更命令（本就写文件）⇒ 变更步放这里无通道冲突
  - `pure_refs` 保持零依赖只读（ADR-0006 §2.3.2 / 本会话实测 E25）
  - `reconcile_supersedes` 原子已幂等（实测：第二次返回 None）⇒ 每次 sync 跑它安全
  - **纯度不变量（机检，可选）**：seal 的 `preconditions` 不得含会写文件的步骤。
    若加，需先让注册表能表达纯度（`gate_fns` 现在是局部变量）。
    按规则 12：E39 的环境被①拆除后，此检查失去实测对象 ⇒ **不加**，仅登记为 reopen 条件
- 桩子先行：先①（含验证 seal 里不再调用它）→ 再②（验证生效列表变回 8 项）→ 再③（当轮即红，因测试用例）

## Notes

### 被否定的旧方案（勿重提）

| 旧方案 | 否因 |
|---|---|
| `FIXERS` 注册表 + 编排器 | 推测性通用性；且接入点 `k3dge commit` 是空插座（AGENTS.md/rules 零提及） |
| 把 reconcile 在 seal 内从 preconditions 移到 actions | **方向漂移**：把「放错侧」降级成「侧内换通道」。且在 seal 内仍会引入顺序副作用（reconcile 后移 ⇒ `adr_landed` 会新拒一个「Accepted 但缺 Landed-by」且正被取代的 ADR，实测复现） |
| 把 reconcile 留在 preconditions 但改成恒返回 None | 只是掩盖：功能仍留在 seal，且变更步仍在只读通道 |
| 大编排器（Step/Flow/Pipeline） | 越界（agent 工作流不可被 k3dge 编排，见 memo S6） |

### 与 memo 的关系

- 本票证据段 = memo `F2`（E39 复现）/ `F3`（声明双源）/ `F5`（特性死亡）的落地
- memo 下一步第 1、4 项由本票取代（原两项都在 seal 内，属漂移残留）

### 改动量

① ~30 行（删两处 + sync 加一步 + 报告）② 删一个文件 ③ ~20 行（规则 + 接线 + 测试）

## 收尾（已完）

| 项 | 落点 | 验证 |
|---|---|---|
| ① reconcile → sync | `sync/generator.py` `sync_all` 加一步（打印 `[SYNC] [ADR RECONCILED] …`）；`seal.py` 删 gate_fns 条目；`gates.py` DEFAULTS 删该项 | seal 调用 reconcile **0 次**（mock 计数）；sync 后旧 ADR 已入 `obsolete/` 且原地已无 |
| ② 删 `.agent/gates.toml` | 文件已删 | `k3dge check --force-full` 全绿（DEFAULTS 生效）；生效列表 7 项，不再含 reconcile |
| ③ 新闸 | `pure_refs.check_supersede_unreconciled` + `scripts/pre-commit` 接线 | 三个红向用例（仍在原位 / obsolete 无文件 / 未标 Superseded）+ 三个绿向用例（已归档且标；无声明；非 ADR 与 obsolete 路径跳过）全过；对现有 ADR **0 误报** |

测试：全量 **493 passed, 2 skipped**。契约已回写（`pure_refs` 增公开函数）。

未做（未登记 reopen）：纯度不变量机检——E39 的环境已被①拆除后，它失去实测对象。
