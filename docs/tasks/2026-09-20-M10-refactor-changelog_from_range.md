---
status: idea
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
