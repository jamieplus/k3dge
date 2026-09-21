---
status: done
milestone: M11
priority: P2
date: 2026-09-21
---

# `k3dge commit` 用 `--no-verify` 绕过 hook：引用/排查闸在便利入口上失效（PRE-01）

- **可检索摘要**: `k3dge commit` 内层只跑 `evaluate(staged=True)`（一致性集），外层 `git commit --no-verify` 关掉 hook ⇒ doc-gate / schema gate（`pure_refs` 12 个 detector）/ 排查闸 `DOC_NEW_UNSCREENED` 在常用入口上全不生效；注释却写「hook 只会重跑同一个 gate」。实例：2026-09-21 提两份 memo 时示例字面 `ADR-9xxx` 漏检，提交后手工扫才出来。

## 证据

```
cli/main.py（改前）：
  report = ConsistencyEngine(...).evaluate(staged=True, ...)   # 一致性集
  # 5) commit; --no-verify bypasses the live hook (which would re-run the same gate).
  ["git", "commit", "-m", msg, "--no-verify"]

hook ≠ 同一个 gate（scripts/pre-commit 四层，按 staged 内容条件触发）：
  层1 doc-gate（docs/<type>/ 的 README+AUTHORING）
  层2 schema gate（.schema.json + pure_refs：悬空 ADR/退役号/名实一致/归档去向/markdown）
  层3 screen gate（DOC_NEW_UNSCREENED）
  层4 check（仅当 src/ docs/specs/ .agent/ pyproject 变）
evaluator 不含 pure_refs：`grep -n pure_refs src/k3dge/engine/evaluator.py` 零命中。
```

## 方案

去掉 `--no-verify`（保留内层 `evaluate(staged=True)`：staged 范围 + fail-fast + `--with-tests` 只有它支持），
让 live hook 承担引用/排查面；注释与 `--help` 同步改口径，并留下前科说明（不得再改回）。

## 边界与拆分

- 事实归属：gate 的**权威面**归 `scripts/pre-commit`（git hook）；`k3dge commit` 只是便利入口，不得自建第二套判据面。
- 不动：审计线 `worktree.advance` 与封版 `seal.py` 的 `--no-verify`（机械件，理由成立，另案）。
- 代价已知：code/spec 类提交会多跑一遍 `check`（hook 那遍是 worktree 范围，与内层 staged 范围不同源）。

## 结案

- `cli/main.py::cmd_commit`：`git commit -m <msg>`（不再 `--no-verify`）+ 注释写清「hook 跑得更多、不得回退」；`commit --help` 改为 `staged gate + live git hooks + attestation sign`。
- **正向验证（探针）**：临时在某 memo 里加 `ADR-42xx`（真编号形态）并 staged 后跑 `k3dge commit` ⇒ **exit=1**，日志第 249 行命中
  `[DANGLING_ADR_REF] docs/memo/…`（改前同一操作会直接提交成功）。探针已清理（`git checkout HEAD --` + `k3dge sync`）。
- 回归：`k3dge check --with-tests` 绿、`pytest -q` 全绿；真提交走 `k3dge commit`（hook 真跑：doc-gate/schema/check 三层输出可见）。
- 有意留：内层 `evaluate` 与外层 hook 的 `check` 各跑一遍（staged vs worktree 不同源）——若将来成为可感负担，再按 PRE-01 的选项 B（抽库入口）收。
