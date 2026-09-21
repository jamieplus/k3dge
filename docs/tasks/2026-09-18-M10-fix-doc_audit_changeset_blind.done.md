---
status: done
milestone: M10
priority: P1
date: 2026-09-18
---

# doc-audit 改动集只看未提交：先提交即集体失明（并回单一源 diff.get_changed_files）

- **可检索摘要**: `doc_audit._changed_docs` / `_new_archive_without_note` 各自跑 `git status --porcelain`，只看**未提交**改动；`diff.get_changed_files` 才是本仓「本轮改动集」的单一源（未提交 ∪ `K3DGE_BASE_SHA...HEAD`）。后果：分批提交后再跑 `k3dge doc-audit` 返回 `no managed docs changed`，`[NEXT] doc_audit` 提示也不再出现——**提交顺序决定了非阻断审计跑不跑**，作者合规检查可被无声跳过。

## Intent

改动集只能有一个定义（事实归属：`engine/diff.py`）。doc-audit 是消费者，不得自带第二套口径。

## 证据（实测，2026-09-19）

```
M10 本轮 134 项改动分 7 批提交完毕后：

  $ k3dge doc-audit
  [DOC-AUDIT] no managed docs changed; nothing to doc-audit.

  ← 而本轮实际改了 docs/adr(5) docs/memo(4) docs/protocols(2) docs/guides(1)
     docs/architecture(1) 等受管文档；[NEXT] doc_audit 也不再出现

根因（两处重复实现，均弱于 canonical）：
  doc_audit.py:20  _changed_docs            → subprocess git status --porcelain
  doc_audit.py:48  _new_archive_without_note → subprocess git status --porcelain（且只认 A/R 码）
  diff.py:87       get_changed_files         → git status ∪ git diff <base>...HEAD（唯一源）
```

消费点两个：`run_doc_audit`（审计范围）+ `cli/main.py:_emit_doc_audit_hint`（`[NEXT] doc_audit` 触发）——两者同时失明。

## 修法（结构性，非散文；规则 10）

两个函数改为消费 `diff.get_changed_files`，删掉各自的 `subprocess` 调用：

- `_changed_docs`：过滤 `docs/` + 排除进程产物（`docs/reviews|tasks|generated`、`archive/`）+ 排除 aux 名（`_is_doc_aux`，与 `status.py:114` 同一源），返回排序结果。
- `_new_archive_without_note`：同一改动集里筛 `**/archive/*.md`，读文本查 `Superseded-by` / `Legacy note`（ADR-0023 §2.2）。不再依赖 porcelain 的 `A`/`R` 状态码——**已提交的归档同样算本轮增量**。

刻意不做：给 doc-audit 加 `--base` 参数。`K3DGE_BASE_SHA` 已是全仓约定（`diff.py:100`），再加一个 CLI 口径就是第三源（规则 12）。

## 验收（实测）

```
tests/unit/engine/test_seal_flow.py::TestDocAudit::test_change_set_includes_committed_docs
  真 git 仓：base 提交 → 改 docs/guides/a.md + 加一张 .done.md 票 → **提交** →
  K3DGE_BASE_SHA=base 下 _changed_docs() == ["docs/guides/a.md"]
  （旧实现在此返回 []；票属进程产物，排除）

522 passed, 2 skipped；k3dge check 绿
```

## Notes

- 同类前科：`2026-09-13-M10-fix-seal_scan_archive`（seal/align 扫描不含 `archive/<M>/` ⇒ 提前归档即「No tasks found」）——都是「范围口径漏了已落盘/已提交的那一半」。
- 影响面：本票修完后，doc-audit 的送审范围会**变大**（含本轮已提交的受管文档），属预期恢复而非扩权。

## 结案

- 关闭提交：`5675663`（2026-09-18）
- 落地记录：见该提交 message 与本文正文（回填于 2026-09-19，事实取自 `git log --diff-filter=AR -1 -- <path>`）。
