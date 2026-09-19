---
status: in-progress
milestone: M10
priority: P1
date: 2026-09-19
---

# 编排骨架收敛·第一刀：闸红文案单源 + 阻断档位统一（Violation 只产 code+事实，文案/severity/options 归声明）

- **可检索摘要**: 骨架收敛的第一刀切 B 线（自动→自主）。现状：`[NEXT]` 的文案已单源（`nextstep.STATE_OPTIONS`，2026-09-19 落），但**闸红侧没有内容声明面**——`engine/evaluator.py` 里 29 处 `Violation(code, f"…手拼串…")` 各自措辞，且只有一句 message、**没有 options**（违 ADR-0026 §2.2「给判断主体＝事实 + 成对选项」）；阻断档位也四写各表：`DOC_NEW_UNSCREENED` 阻断、`ORPHAN_*` WARN、`[DUP-CHECK]` 观测、`[NEXT]` 提示。修法：闸只产 `(code, 结构化事实字段)`，文案 + `options` + `severity` + `pointers` 全部归节点声明，由单一渲染器投影。

## Intent

内容/流程解耦（用户裁定 2026-09-19）：文案与档位是**内容**，必须声明化；闸与渲染是**流程**，只留一份实现。四条线（A 自动→自动 / B 自动→自主 / C 自主→自动 / D 自主→自主）**不各设一套机制**，差异只体现在节点声明的字段上。本票落 B 线用到的三个字段：`severity` / `fact`+`options` / `pointers`。

## 已裁定（用户，2026-09-19）

1. B 线的形状 ＝ **阻断闸 + 投喂事实源**：闸拦住并指路，投喂的事实源把调查范围限定住。
2. **硬约束**：投喂的事实源必须是**已有的投影**，不新造调查通道。现成的：`docs/generated/docs-index.json`、`k3dge_adr_index`、`markers` 账、12 列报告、`.k3dge/events.jsonl`、`k3dge doc list/grep --type`。
3. 文案单源与档位统一**不是 B 线的独立课题**，就是内容/流程解耦的两个字段。
4. 收敛顺序：本票（B）→ `pipelines.*` 接通（③）→ A 线节点表/ctx → `sync` 收编；`task done` 有意留（原子性风险大、收益小）。

## 现状证据（实测）

```
文案：evaluator.py 内 Violation(...) 构造点 29 处，其中 28 处含手拼 f-string
      pure_refs / pure_schema 另有 ~20 个 code，message 同样在构造点拼好
      scripts/pre-commit 的阻断文案是 hook 里的散文（"[k3dge screen] FAIL: …"）
档位：block  = DOC_NEW_UNSCREENED / 全部 check violation / schema gate
      warn   = ORPHAN_ADR|SPEC|TEST（pure_refs B4，"WARN-only until FP rate known"）
      observe= [DUP-CHECK]（cache.search 提示，"不阻断、不裁决"）、k3che hints
      提示   = [NEXT]（nextstep.STATE_OPTIONS）
      ⇒ 四档四处实现，无统一标记；同一 code 在 evaluator / pure_refs / hook 里可能各说各话
无 options：闸红只给 message，不给合法选项 ⇒ 违 ADR-0026 §2.2（判断主体须得成对选项）
```

## 方案

```
声明（唯一一张表，落 .agent/pipeline.toml 的 [checks.*]；见 orch_node_table 票）
  code | severity(block|warn|observe) | fact 模板 | options(≥2) | pointers | 投喂的事实源
闸侧（流程）
  Violation 只带 code + 结构化事实字段（如 {file, expected, actual, domain}）
  —— message 不再在构造点拼
渲染器（单一实现，两投影）
  给进程     → code + 事实字段（闭集，可机械分支；对齐已落的 gates.Rejection/GATE_NEXT）
  给判断主体 → fact + 成对 options + pointers（陈述式，不出疑问句；对齐 [NEXT] 现行形状）
```

## 边界与拆分（规则 08）

- 事实归属：**code 词表 + 事实字段** 归各检查器（evaluator / pure_refs / pure_schema / hook）；**文案 + 档位 + 选项** 归声明表；**渲染** 归单一渲染器。检查器不得知道文案，声明不得知道检查器内部。
- 边界检查：渲染器不读检查器内部状态（只吃 `(code, 事实字段)`）；声明表不含逻辑/表达式（沿用 `gates.py` 既有原则「契约只承载数据」）。
- 桩子先行：先落声明表 schema + 渲染器 + **3 个 code 迁移**（选一个 block、一个 warn、一个 observe 各一），跑通骨架并证明两投影同形；再逐批迁完 29+ 处。每批 `pytest` 绿 + `k3dge check` 绿。
- 不做：不在本票引入节点表全量（A 线的 `needs/produces/on_error` 归 `orch_node_table`）；不动 `.schema.json` 的判据（那是 `judge` 轴，另一维）。

## 验收

- `grep -c 'Violation(' evaluator.py` 的构造点不再含 prose f-string（事实字段化）；
- 同一 code 在 CLI / hook / MCP 三处投影同源（守卫测试：改声明一处，三处输出同时变）；
- 每个 `severity=block` 的 code 都有 ≥2 个 options（守卫测试，同 `TestProjectionInvariants` 口径）；
- 档位唯一源：不再有"WARN-only"这类写在代码注释里的档位（迁进声明）；
- `k3dge sync` 回写契约哈希；全量 pytest 绿。

## Notes

- 与 `2026-09-18-M10-fix-pipelines_stages_dead_config`（③）互为前后件：本票先落声明面的一半（code→文案/档位），③ 落另一半（hook→stages）。
- 与 `2026-09-19-M10-refactor-orch_node_table` 的关系：本票是那张表的第一批居民，不是另建一张表。
- 本票是**现行 ADR-0026 违规的修复**（闸红无 options），不只是重构。

## 进度（2026-09-19，桩已落 · commit b189846）

已落（骨架 + 5 个 code 迁移，实测两投影同形）：

```
engine/gate_facts.py（零依赖，pre-commit 与 engine 共用）
  GATE_FACTS 声明表：code → severity | fact | options | pointers
  severity() / render()（给判断主体）/ projection()（给进程）/ fill() / facts_of()
  档位闭集 block|warn|observe 只在此定义
Violation.format()      已声明 code 走表（[GATE ERROR|WARN|NOTE] + fact/options/pointers）
                        未声明保持旧形状 ⇒ 迁移可增量
已迁 5 个 code          CONTRACT_DRIFT(block) DOC_NEW_UNSCREENED(block)
                        ORPHAN_TEST|ORPHAN_SPEC|ORPHAN_ADR(warn)
evaluator               CONTRACT_DRIFT 的 message 降为事实摘要（spec=… code=…）
pure_refs               find_unscreened_new_docs 返回 (code, path)，只产事实不产文案
scripts/pre-commit      run_screen_gate → [(severity, 文本)]，档位/文案查表；
                        声明面不可用 ⇒ 回落 `[code] 事实`（不放行、不崩）
cli/main._to_json       violation 带 severity（进程投影）
守卫测试 16 条          档位闭集 / block 必 ≥2 options / 声明文案无疑问句与 y/N、倒计时 /
                        占位符缺失不抛 / 未声明兜底 / projection 闭集 /
                        声明占位键 ↔ 检查器 detail 对齐 / hook 回落
555 passed；k3dge check 绿
```

待办（本票剩余）：
1. 迁余下 code：evaluator 的 29 处 `Violation(...)` 手拼串（CONTRACT_HASH_MISSING /
   TEMPLATE_DRIFT / VERSION_MISMATCH / DOC_INDEX_STALE / DOMAIN_IMPORT_VIOLATION /
   MATRIX_TEST_UNRESOLVED / MISSING_TEST_FILE / PIPELINE_SCHEMA_INVALID /
   SPEC_MISSING_SECTION / UNREGISTERED_DOMAIN / AUDIT_TRAIL_APPEND_ONLY / …）
   + pure_schema/pure_refs 的 ~20 个 code（ADR_* / DOC_* / MD_* / TASK_* / DANGLING_*）
2. hook 的 schema gate：`run_schema_gate` 现在把 `(code,msg)` 拍平成字符串再打印
   （`f"{rel}: [{code}] {msg}"`）⇒ 档位/文案仍在 hook 里；改为查表（与本票同口径）
3. `_orphan_warnings` 的 "WARN (non-blocking)" 散文标签改为查表 severity
4. `[DUP-CHECK]` / k3che hints 的 observe 档进表（现在是 cli 里的 print 散文）
5. 全部迁完后：`Violation.message` 降为纯事实字段（或删），并加守卫
   「已声明的 code 不得再在构造点拼散文」

## Notes（补）

- 与 `orch_node_table` 的接口已对齐：本表就是那张节点表的 `severity/fact/options/pointers`
  四个字段，届时**并入而非并存**（避免长出第二张文案表）。
- 档位声明放在代码里而非 `pipeline.toml`：code 词表是 k3dge 自己的（下游不能发明 code），
  下游可配的是"走哪些步/什么顺序/失败怎么办/阈值"（见 `adr0026_d_line_and_downstream` §2.7 草案）。
  若后续要求下游能降档（block→warn），再把 severity 提升为 toml 可覆盖项。
