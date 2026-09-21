---
status: done
milestone: M10
priority: P2
date: 2026-09-20
---

# CHANGELOG 改由提交区间生成：删"每票 done 写一行"的双写、闸只验不漏项

- **可检索摘要**: ADR-0004 §2.1.12 定 CHANGELOG 由**提交区间**生成（`<上一里程碑 tag>..<本轮 tag B>` 的非机械提交；类型取 conventional 前缀），闸只验**不漏项**，语义润色归人。现状是双写：`task_write._append_task_changelog` 在每张票 `done` 时各往 `## [Unreleased]` 追加一行，封版再写一次版本段——本会话反复遇到"票写了 CHANGELOG 没写 / 标题漂移"。

## Intent

"发布说明收哪一段"应当由**区间**回答（tag 天然给出），而不是靠"谁记得写"。提交不可漏（每次改动必有提交），票可漏（没开票也能改）⇒ 来源取提交。

## 证据（实测）

```
task_write._append_task_changelog：每票 done 各写一行 ⇒ 未开票的改动漏、改题后 CHANGELOG 未同步
version.bump_version：seal 后把 Unreleased 段搬进版本段（消费式），但 Unreleased 内容本身不可靠
本仓 commit-msg 闸已强制 conventional 前缀（`k3dge check-msg`）⇒ 类型字段无需人手填
审计线机械提交：`round work <job>` / 作者 `k3dge-process` ⇒ 需过滤
```

## 方案

```
① 删双写：`task done` 不再写 CHANGELOG
② 封版时生成：区间 = <上一里程碑 tag>..<本轮 tag B>
   · 过滤机械提交（进程作者 / `round work` 前缀 / 封版提交自身）
   · 类型取 conventional 前缀；标题取提交 subject
③ 闸：版本段条目数 ≥ 区间内非机械提交数（**不漏项**）+ 类型合法（可机检）
④ 语义润色归人：允许在封版提交里补"面向用户"的描述；闸不判写得好坏
```

## 边界与拆分（refactor 类）

- 事实归属：**变更事实**归 git（提交区间 + trailer）；**展示**归 `CHANGELOG.md`（按 SemVer/Keep a Changelog 的既有格式）；**版本号**归 `pyproject.toml`（§2.3 不变）。
- 边界检查：k3dge 不判"某条变更该不该进 CHANGELOG"（merit 归人）；不解析散文（只读 conventional 前缀与 subject）。
- 桩子先行：先落"区间 → 条目"的纯函数 + 单测（喂造出来的提交区间），再接 `bump_version`。

## 验收

```
封版后 CHANGELOG 版本段覆盖区间内每个非机械提交；人为漏一条 ⇒ 闸红（指出漏了哪个 subject）
task done 不再改 CHANGELOG（该提交的 diff 里无 CHANGELOG）
```

## Notes

- 依赖 `feat-seal_boundary_tag`（区间靠 tag 界定）。
- 有意留的取舍：封版前 `Unreleased` 段为空（期间用 `k3dge status` / 票列表代替）。

## 落地（2026-09-20）

| 项 | 落点 | 实测 |
| --- | --- | --- |
| ① 删双写 | `task_write.mark_task_done` 不再调 `_append_task_changelog`（函数删除，`changelog` 依赖随之摘掉）；两处 docstring 改述 | `TestNoDoubleWrite::test_mark_task_done_leaves_changelog_untouched`：关票后 `CHANGELOG.md` 字节不变 |
| ② 区间生成 | `changelog.build_notes_from_range()`：`<上一里程碑 tag>..HEAD`、`--no-merges`、按 conventional 前缀分节（Keep a Changelog 顺序）；`mechanical_commit()` 过滤 `round work` 与带 `Seal-milestone` trailer 的封版提交；无边界 tag ⇒ 回落 `Unreleased` 累积 + 通用行 | `TestRangeNotes`（5 条，**真 git 仓**）：逐条覆盖；机械件滤除；最大号边界起算；无 tag ⇒ 空 notes |
| ③ 闸（不漏项） | `mechanical_commit` **不**把"非 conventional"当机械件——那类进 `uncovered`，由封版告警（`版本: X.Y.Z；N 条提交无 conventional 前缀（未成条目）`） | `test_untyped_subject_is_reported_not_invented`：条目只收能归档的，未归档的一条进 `uncovered`（不猜它归哪一节，也不静默滤掉） |
| ④ 接入封版 | `seal_flow._version_bump`：notes 优先取区间生成，空则回落 | `test_version_advances_after_the_audit_returns` 仍绿（bump 与 notes 同一处） |
| ⑤ 散文同步 | `AGENTS.md` §12 新增「CHANGELOG 条目」行；`.agent/rules/04-milestone.md` 新增「CHANGELOG 由提交区间生成」段（+镜像） | PAIRS `diff` 一致 |

测试：新增 `tests/unit/engine/test_changelog_range.py`（8 条）；**688 passed, 2 skipped**；`k3dge check` 绿。

### 有意偏离票面（附理由）

票面写"闸：版本段条目数 ≥ 区间非机械提交数"。落地**没有**做成 `check` 里的常驻闸：CHANGELOG
在两个边界之间**本来就**是不完整的（生成发生在封版那一刻）——常驻闸会在每次提交后恒告警，
变成噪音（"狼来了"）。改为两处落实"不漏项"：**生成即全覆盖**（来源就是区间，结构上没有漏的
余地）+ 解析不出类型的提交由封版**告警**（`uncovered`），并由测试守"逐条覆盖"这个不变量。

### 边界（有意留）

`_append_to_unreleased` 保留为**首个里程碑**的降级路径（无上一个边界 tag 时用）；它不再被
`task done` 调用。若将来引入"手动写 Unreleased"的用法，需要重新裁定（本票只保证不双写）。
