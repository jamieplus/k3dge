---
status: done
milestone: M10
priority: P3
date: 2026-09-19
---

# 闸红声明面收尾：pure_* 检查器产结构化事实（3-tuple），Violation.message 降为兜底

- **可检索摘要**: `gate_facts` 声明面已落（42 code / 35 处 `Violation` 构造点，0 未声明；commit `84040f5`），但**只做了一半**：`evaluator` 侧的构造点已给 `detail=` 结构化事实，`pure_refs`/`pure_schema` 的 ~20 个检查器仍返回 `(code, msg)` 二元组，散文 `msg` 由 hook 当作 `render(detail=)` 的行带出——这是**过渡约定**，不是终态。收尾要做两件：① 检查器返回 `(code, facts, msg)` 三元组，让声明里的 `{path}`/`{expected}` 等占位符由真事实填（而非整句原文）；② `Violation.message` 降为纯兜底（JSON/MCP 与未声明 code 仍读它），或删。

## Intent

内容/流程解耦的**最后一格**：`fact` 模板要能引用结构化字段，否则"文案单源"只到句级、不到字段级。

## 证据（实测）

```
声明侧（已落）
  GATE_FACTS 42 code；每个声明带 fix(确定性可修|需判断) / severity / fact / options / pointers
  占位符：CONTRACT_DRIFT{expected_hash,actual_hash} DOC_INDEX_STALE{reason}
          DOC_NEW_UNSCREENED{path} ORPHAN_*{path} …
生产侧（未落）
  pure_refs  ~20 个 code 仍返回 (code, msg)：如
    ("ORPHAN_TEST", f"{rel}: no Verification Matrix references this test file")
    ("TASK_BODY_META_REDUNDANT", f"{rel}: 正文复写 frontmatter 元数据…")
  消费侧（过渡约定）
    scripts/pre-commit 的 _add(code, msg, where, facts)：
      facts = {"path": where or msg.split(":")[0]}          ← 只有 path 一个字段
      gate_facts.render(code, facts, where=where, detail=msg) ← 原文整句塞 detail 行
  ⇒ 声明里的 {reason}/{expected} 这类字段，pure_* 侧**填不出来**（只能整句塞 detail）
```

## 方案

```
① 检查器签名：Ref = Tuple[str, str] → 新增 RefFacts = Tuple[str, dict, str]
     (code, facts, msg)   msg 保留为"人类可读的兜底原文"（未声明 code 与 JSON 消费者仍需要它）
   改动面：pure_refs ~20 个 check_* / pure_schema check_file 的 (code, msg, scope)
           + scripts/pre-commit 的 _add + tests/unit/engine/test_pure_*.py 的断言形状
② 声明侧补字段：把 fact 模板从"整句"细化到"字段"
     例：ORPHAN_TEST.fact 由「`{path}` 没有被任何 Verification Matrix 行引用」保持（已够）
         ADR_NUMBER_REUSE.fact 补 {num}/{was}/{dest}（现在这些塞在 msg 里）
③ Violation.message 的处置：降为纯兜底（不删），并在 gate_facts 侧加守卫
     「已声明 code 的 message 不得承载 fact 模板已有的信息」（避免两处描述同一事实）
     —— 现有 TestNoProseBackflow 已守"message ≤100 字符且不含补救散文"，本票再加一条
     "message 不得复述声明 fact 的措辞"（可用词集重叠率做粗判，超阈值即红）
```

## 边界与拆分（规则 08）

- 事实归属：**事实字段**归检查器（它才知道实际值）；**字段名与文案**归声明表；**渲染**归单一渲染器。检查器不得知道文案，声明不得知道检查器内部。
- 边界检查：三元组是**加法**（保留 `msg`），老消费者（`Violation.message`、MCP JSON）不受影响；不引入新机制（无新表、无新渲染器）。
- 桩子先行：先改 3 个检查器（各取一个 block/warn/observe）+ `_add` + 守卫，跑通；再批量改剩余 ~17 个。每批 `pytest` 绿。
- **不做**：不给 pure_schema 的 `(code, msg, scope)` 加第三元（scope 是位置语义，与 facts 不同类；必要时把 scope 并入 facts）。

## 验收

- `grep -c "return \[(.*\"" pure_refs.py` 的返回形状全部为三元组（`msg` 仍在）；
- 守卫测试：每个已声明 code 的声明占位符，都能由对应检查器给出的 facts 键覆盖（现在是"部分覆盖"，收尾后应"全等"）；
- `TestNoProseBackflow` 扩一条"message 不复述 fact 措辞"；
- 全量 pytest 绿；`k3dge check` 绿；`k3dge sync` 回写契约哈希（pure_refs/pure_schema 公开符号变更）。

## Notes

- 来源：`docs/tasks/2026-09-19-M10-refactor-orch_converge_gate_facts.done.md` 的「有意留」第 1 条。本票是它的**下一批**（当时判"改 ~20 个检查器返回形状 + 全部测试，收益低于当轮风险"）。
- 与 `orch_node_table` 无依赖：那张表管"走哪些步"，本票管"每步的事实字段"。
- 优先级 P3 的依据：现状**不产生错误行为**（文案仍来自声明，只是字段粒度粗）；收益是可机检的"字段级单源"。

## 落地（2026-09-19）——**定形修正：3-tuple 改造经实测为零收益，改为做真正缺的两件**

### 实测（本票的前提被推翻）

```
逐 code 量：声明里需要 `path` 之外字段的有 18 个
  AUDIT_TRAIL_APPEND_ONLY / CONTRACT_DRIFT / CONTRACT_EXTRACT_FAILED / CONTRACT_HASH_MISSING /
  DOC_INDEX_STALE / DOMAIN_IMPORT_VIOLATION / GIT_UNAVAILABLE / MANIFEST_INVALID /
  MATRIX_TEST_UNRESOLVED / MISSING_TEST_FILE / PIPELINE_SCHEMA_INVALID / SPEC_DECODE_FAILED /
  SPEC_MISSING_SECTION / SPEC_NOT_FOUND / TEMPLATE_DRIFT / TEST_ENV_MISSING / TEST_FAILURE /
  VERSION_MISMATCH
⇒ **这 18 个全在 evaluator 侧，且早已结构化**（各构造点给 `detail=`，由 `TestProducersFeedDeclaredFacts`
  的 AST 守卫锁着）
只需 `{path}` 的 28 个：path 由**调用方**本来就知道（staged 文件的 rel）
无占位符的 2 个：NO_DOMAINS / DUP_CHECK
```
⇒ 「pure_* 返回 3-tuple 以便填字段」在**数据上无对象**：需要多字段的都已结构化，剩下的只用 path。
按规则 12（不单独扩基建、要有实证正向作用），**不做** 3-tuple 改造（改 ~20 个检查器 + 全部测试
换取零行为差异）。

### 真正缺的两件（已落）

| 项 | 内容 |
| --- | --- |
| **检查器只产事实**（消掉散文解析） | `check_markdown_bytes` / `find_orphan_specs` / `find_orphan_tests` / `find_orphan_adrs` / `find_unguarded_archives` 的第二项由 message 改为**事实（路径）**；`pre-commit` 的 `_add` 删掉 `msg.split(": ")[-1]` / `msg.split(":")[0]` 两处散文解析，`path` 一律显式传（`where=` / `facts=`） |
| **棘轮两条** | ①`TestMessageDoesNotRestateFact`：已声明 code 的静态 message 不得复述声明 fact 的**含中文散文片段**（字段名/标识符重叠不算——那本身就是事实；实测当前 0 命中，原先 2 处 `NO_DOMAINS` 命中是字段名，已按此收窄）②`TestFactsAreProducedNotParsed`：hook 源码里不得再出现 `msg.split`（非注释行） |
| `Violation.message` 降为事实摘要 | 已由上一票完成（静态最长 25 字符）+ `TestNoProseBackflow` 守着（≤100 字符、不含补救散文） |

### 有意留（记此）

- **pure_* 的 `(code, msg)` 形状保留**（未改三元组）：见上，零收益；若将来某个 pure_* 检查
  需要声明里 path 之外的字段（如"哪一行/哪个值"），**那时**再按实际需要改它一个，不必全量重构。
- `Violation.message` 未删：仍是 JSON/MCP 消费者与未声明 code 的兜底（同上票记录）。

## 验收（实测）

```
632 passed；k3dge check 绿
tests/unit/engine/test_gate_facts.py::TestMessageDoesNotRestateFact（0 命中）
tests/unit/engine/test_gate_facts.py::TestFactsAreProducedNotParsed
  hook 无非注释的 `msg.split`；抽样断言 MD_CRLF / ARCHIVE_NO_DEST 返回的第二项就是路径
渲染实测（文案仍正确）：
  ORPHAN_TEST → `fact: tests/x.py 没有被任何 Verification Matrix 行引用…`
  MD_CRLF     → `fact: docs/x.md 用了 CRLF 行尾——纯格式偏差，进程可按固定规则修`
```
