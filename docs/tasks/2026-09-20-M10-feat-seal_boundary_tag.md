---
status: idea
milestone: M10
priority: P1
date: 2026-09-20
---

# 封板边界与标识：`tag <M> = B`、封版提交 trailer（四键）、版号在审计正常返回后前进

- **可检索摘要**: ADR-0004 §2.1.9/§2.1.10 定"审计输入标识＝基线 B 的 git hash（不用 job id）、封板边界＝`tag <M> = <B>`、完成记录＝封版提交的 trailer（`seal-milestone`/`audit-baseline`/`audit-seat`/`audit-result`）、版号在**审计正常返回后**前进"。现实现三处相反：版号前进挂在"seal 成功"后（`seal_flow` 里调 bump）；全仓无 tag、无 trailer；而报告由 `collect_audit` 写进**主干工作树**，靠 `merge_back(accept_dirty=…)` 放行合并却**无人提交它**。

## Intent

"审哪版封哪版"必须有**可复算的凭据**：hash 标识 + tag 边界 + trailer 记录。且记录**不能**依赖"审计有没有提交/有没有报告"——因为审计常常零提交（见证据）。

## 证据（实测）

```
seal_flow.py            封板动作里调 version bump；触发点是"seal 成功"而非"审计正常返回"
worktree.advance()      **只在脏时提交**（`if status --porcelain` 非空才 commit）；
                        线 tip == 主干头 ⇒ 直接返回，**无新提交**
worktree.merge_back()   主干已含线 ⇒ {"ok": True, "mode": "already"} ⇒ **零提交、零合并**
audit_flow.collect      report_path 写在 workspace（主干工作树）⇒ accept_dirty 只"放行 merge"，
                        **不负责提交** ⇒ "审计完了就提交 comment 一句"在零改动/零报告审计上没有载体
```

## 方案

```
① 基线：submit_audit 锁 B（`prov["baseline"]` 已有）；对外的标识统一用 **B 的 hash**，job id 退为本地进度
② 封版提交：显式 `git add` 审计产出（报告 / 审计线的改动）再提交；commit trailer 四键：
     seal-milestone: M10
     audit-baseline: <B>
     audit-seat: <席位>
     audit-result: closed|degraded-manual|escalated|refused
③ tag：封板时 `git tag -a <M> -m … <B>`（annotated，**指向基线**，不是封版提交）
④ 版号时机：审计正常返回 ⇒ 立即 bump（不管有没有报告）；`--no-version-bump` 保留为显式逃生
⑤ 归属：B 之后的主线提交归下一里程碑（由 tag 界定；重挂工具见 `feat-milestone_reassign` 票）
```

## 边界与拆分（feat 类必填；规则 08）

- 事实归属：**基线**归 `audit_flow` 的 job 记录 + git（hash 是 durable 标识）；**边界**归 git tag；**完成记录**归封版提交 trailer；**版本号**归 `pyproject.toml`（单源，§2.3 不变）；**进度**归本地账（`audit_jobs.json`，投影）。逐条不重叠。
- 边界检查：trailer 由 seal 写、由闸用 `%(trailers)` 读，**不经散文解析**；tag 只被"归属判定"读，不被任何模块当作内部状态的替代；不让 B 之后的模块知道审计线的内部（分支/worktree 只属 `worktree.py`）。
- 桩子先行：先落 trailer 写入 + 单测（读回四键），再加 tag（`git tag -a` 封装 + 幂等检查），最后挪版号时机（顺序变化可单测）。

## 验收

```
封版提交 `git log -1 --format=%(trailers)` 含四键，且 audit-baseline == tag 指向的 B
`git rev-parse <M>^{commit}` == B（tag 指向基线，不是封版提交）
零改动审计（线无新提交）⇒ 仍有封版提交承载 trailer/tag（不依赖审计提交）
审计返回后版号已前进（即使报告缺失）；`--no-version-bump` 下不动
主干在 B 之后有提交时 ⇒ 封版提交落在其后，历史未重写（A′）
```

## Notes

- A′ 的取舍已写进 §2.1.9：不重写公共历史，边界靠 tag 表达（历史里封版提交位于后续工作之后）。
- 依赖 `fix-audit_no_noop`（`audit-result` 的值由它定）。
