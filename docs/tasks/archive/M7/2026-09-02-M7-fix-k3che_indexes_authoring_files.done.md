---
status: done
milestone: M7
priority: P3
date: 2026-09-02
---

# k3che 检索索引把 docs/*/AUTHORING.md 当语料

- **Status**: done
- **Milestone**: M7
- **Priority**: P3
- **可检索摘要**: k3che 建索引只排除 `readme.md` 与 `_` 前缀，`AUTHORING.md`（编撰规则，不是内容）进了检索语料；与本仓 `task list` 幽灵任务是同一根因的另一种表现
- **Date**: 2026-09-02

## 已确认意图

`docs/<type>/AUTHORING.md` 是"怎么写这类文档"的规则件，与 `README.md`（卡片）、`_template.md` 同属结构件，不该作为知识条目被检索/命中统计。

## 上下文/切入点

- 现场：`../k3che/src/k3che/index.py:13` `_AUX_FILENAMES = frozenset({"readme.md"})`，`:118` `if name.startswith("_") or name.lower() in _AUX_FILENAMES: continue` ⇒ `AUTHORING.md` 不被排除。
- 实测（本仓，用 k3che 自己的索引器）：
  ```
  PYTHONPATH=../k3che/src .venv/bin/python -c "from k3che.mcp import _get_harness,_find_workspace; ..."
  indexed: 122
  AUTHORING in index: ['docs/specs/AUTHORING.md', 'docs/adr/AUTHORING.md', 'docs/tasks/AUTHORING.md',
                       'docs/branches/AUTHORING.md', 'docs/guides/AUTHORING.md', ...]
  ```
  即 122 篇里有 **≥6 篇是编撰规则**，会参与打分并占用 `top_k` 名额（`docs/reviews/AUTHORING.md`、`docs/incidents/AUTHORING.md`、`docs/protocols/AUTHORING.md` 也在内）。
- 与 k3dit 报告 `docs/reviews/2026-08-26-k3dit-5pass.md` 里 R3-01 的"import 变量悬空"无关；但与本仓已修的 `docs/tasks/2026-09-02-M7-fix-task_list_ghost_authoring.done.md` 同源：**结构件名单在各仓各持一份**。
- 上游修复已落：`src/k3dge/engine/milestone.py:306-311` 的 `_DOC_AUX_NAMES` + `_is_doc_aux()` 是本仓单一事实源。

## 候选改法（择一，改的是 k3che 仓，需其维护者授权）

- **A（一行）**：`_AUX_FILENAMES` 加 `"authoring.md"`。最小、无依赖；缺点是名单仍是第三份副本。
- **B（收敛）**：由 k3dge 把 `_is_doc_aux` 提为公开符号（`is_doc_aux`）并写进 `docs/specs/engine/spec.md` 契约，peers 复用 ⇒ 全家族一个事实源。代价：peers 要 import k3dge，与 k3che 现注释「Does not import k3dge」冲突，属跨仓依赖决策（`ADR-0006` 地位对等条），**不建议轻率做**。
- **C（各自持有 + 机验对齐）**：保留各仓一份，但 k3dge `check` 增加"结构件名单一致性"静态核对（盘上事实，不连进程）。

## 验收

- k3che 建索引后 `docs/*/AUTHORING.md` 不在 `index.documents` 内；`k3che_search` 的 `top_k` 名额不再被规则件占用。
- k3che 侧新增/调整一条单测（覆盖 `AUTHORING.md` 排除）+ 其 `pytest -q` 全绿。
- 若选 B/C：对应仓的 spec 与 `k3dge sync` 一并完成。

## Related

- 同源已修：`docs/tasks/2026-09-02-M7-fix-task_list_ghost_authoring.done.md`
- 勘误：本文件初稿在此写过「本轮未动 k3che 任何文件」，与下方回填矛盾。那条「k3che 一字不动」只是对话里的临时约定，从未进任何 ADR；维护者授权破例后，改完就要改记录（`ADR-0006` §2.3.7）。

## 回填（2026-09-02，本轮做完）

维护者破例授权改 k3che（原约定"k3che 一字不动"）。方案 **A**（各仓自持名单，不引入跨仓依赖）：

- `../k3che/src/k3che/index.py:13` → `_AUX_FILENAMES = frozenset({"readme.md", "authoring.md"})`（附两行注释说明结构件语义）
- `../k3che/pyproject.toml:17` → `mcp = ["mcp>=1.0,<3"]`
- `../k3che/tests/unit/k3che/test_index.py::test_build_skips_readme_and_templates` 增加 `AUTHORING.md` 用例（该测试名本就承诺模板与卡片，现在才真覆盖）
- 留痕：`../k3che/docs/tasks/2026-09-02-fix-authoring_in_corpus.md`

实测：

```
$ k3che pytest -q                     → 36 passed
$ 对 ../k3dge 重建索引                → indexed 122 → 118；docs/*/AUTHORING.md 命中数 → 0
```

未选 B（提公开符号 `is_doc_aux` 让 peers 复用）与 C（k3dge 机验各仓名单一致）：B 会让 peers 依赖 k3dge、与 `ADR-0006` 地位对等条相抵；C 是新增闸，按本轮"文档先行"的取向不扩。名单仍是两处副本（k3dge `_DOC_AUX_NAMES` / k3che `_AUX_FILENAMES`），漂移风险显式留档。
