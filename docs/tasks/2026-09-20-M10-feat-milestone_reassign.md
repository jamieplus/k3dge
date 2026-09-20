---
status: idea
milestone: M10
priority: P2
date: 2026-09-20
---

# 里程碑重挂：`milestone reassign <from> <to>` + 归属闸 + 修子串一致性检查

- **可检索摘要**: ADR-0004 §2.1.9 定"B 之后的主线改动归下一个里程碑（票随之重挂）"。今天既没有"重挂"入口，归属检查也**用子串**：`pure_refs.check_task_consistency` 对里程碑一致性用 `ms not in base` 之类的包含判断（A-01 同类，闸偏松——`M1` 会匹配 `M10`）。本票落一个原子/幂等的重挂工具（改票的 milestone 事实：frontmatter + 文件名 M 段）、一条归属闸（票的 milestone 必须 = 当前指针，或按 tag 归属可解释；先作提示不硬阻断），并把子串检查修成 token 判定（复用 `_has_milestone_token`，边界集 `[-_./\s]`，不含 `+`）。

## Intent

有了 tag=B 边界，就必然出现"票贴着旧编号、实际归属新里程碑"的窗口期；重挂必须是**一次机械改写**（不是人肉改 frontmatter + 改文件名两处），否则又会造出双源。

## 证据（实测）

```
pure_refs.check_task_consistency：里程碑一致性用包含判断（子串）⇒ M1 与 M10 互相误匹配
task 的里程碑事实有两处物理位置：frontmatter `milestone:` 与文件名 `…-M10-…`（必须同改）
milestone_pointer.get_current_milestone() 有 9 处读取点，分"新工作语义"与"待封语义"两类
本会话已有一批 M10 票共 14 张（B 未锁定，故本次不预设重挂编号）
```

## 方案

```
① `k3dge milestone reassign <from> <to> [--dry-run] <task…|--all>`
   · 只改票的里程碑事实（frontmatter + 文件名 M 段），**同一次原子写**、幂等
   · 未知 id / 目标号非法（含 `_SAFE_MILESTONE_ID_RE`）⇒ 拒绝
② 归属闸（先提示后阻断二选一，本票先落提示）：
   票 milestone ≠ 当前指针 ∧ 无法由"最近 tag 之后的提交"解释 ⇒ 报
③ 修 `pure_refs.check_task_consistency`：子串 → `_has_milestone_token`
④ 一次性重挂：等 B 锁定后由人/agent 按真实归属执行（工具化，不写死编号）
```

## 边界与拆分（feat 类必填；规则 08）

- 事实归属：**票的里程碑**归票自身（frontmatter + 文件名，单源两处必须同步由工具保证）；**当前指针**归 `milestone_pointer`；**归属边界**归 git tag。不新建"归属账本"。
- 边界检查：工具不改票的 status/priority/正文；不做编号方案变更（如 `M+` 过渡号，ADR-0004 §2.1.13 已列为非目标）；不引入第二份映射文件。
- 桩子先行：先落"改 frontmatter + 文件名"的原子函数 + 幂等/干跑单测，再接闸与子串修正。

## 验收

```
reassign 跑两次结果一致（幂等）；--dry-run 不改盘
未知 from/to ⇒ 拒绝（不静默跳过）
造 M1 票 + 指针 M10 ⇒ 不再互相误匹配（token 判定）；M10 票 + 指针 M11 且不可解释 ⇒ 提示
```

## Notes

- 与 `feat-seal_boundary_tag` 同期：没有 tag 就没有"归属可解释"的判据。
