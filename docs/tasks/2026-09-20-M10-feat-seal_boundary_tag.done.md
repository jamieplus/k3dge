---
status: done
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

## 落地（2026-09-20）

| 项 | 落点 | 实测 |
| --- | --- | --- |
| ① 基线标识 | `seal.head_commit()` 在审计**之前**取一次 B；写进 trailer 与 tag；job id 退为本地进度 | `TestSealRecord.test_commit_carries_trailers_and_tag_points_at_baseline` |
| ② 封版提交 + trailer | `seal.seal_record()`：`git add -A` → `--no-verify` 进程身份提交（`-F <tmp>`，不读终端）→ 正文带四键（`SEAL_TRAILER_KEYS` 单源）；`format/parse_seal_trailers` 写入读回同源 | `git log -1 --format=%B` 解析出四键；空改动 ⇒ 不造空提交（`test_clean_tree_does_not_create_empty_commit`） |
| ③ 边界 tag | `seal.tag_audit_baseline()`：`git tag -a <M> <B>`；**幂等**（同指向绿、不同指向拒，不移动边界事实） | `TestTagBoundary`：同指向 ⇒ "已在"；改指向 ⇒ 拒且 tag 未动 |
| ④ 版号时机 | `seal_flow` 相位 3 新节点 `version_bump`（`on_error=continue`，失败只告警不回滚归档）；`cli/main.py` **不再**在流程后另跑 bump，只透传 `--no-version-bump` | `test_version_advances_after_the_audit_returns`：1.2.3 ⇒ 1.2.4（默认）/ 1.2.3（`--no-version-bump`） |
| ⑤ 记录挂载点 | 相位 3 新节点 `seal_record`（`on_error=stop`，记录落不下就不算已封）；成功消息打印 `边界: tag <M> = <B>` | 零改动审计（`test_zero_audit_commit_still_gets_a_record`）⇒ 仍有记录载体 |
| ⑥ 声明面 | `gates.DEFAULTS` / `pipeline.toml`（+模板镜像）actions 序：`full_matrix, audit, archive, version_bump, seal_record, closure_note, prune`；`NODE_DEFAULTS` 两节点（fact） | `test_gates` 断言 actions 序；PAIRS `diff` 一致 |
| ⑦ 散文同步 | `AGENTS.md` §12 / `.agent/rules/04-milestone.md`（+镜像）：版号时机、trailer、`tag <M>=<B>`、本地账＝运行态投影 | PAIRS `diff` 一致 |

测试：新增 `tests/unit/engine/test_seal_record.py`（9 条，**真 git 仓**——凭据的价值就是可复算，
桩掉 git 只剩同义反复）；seal 流程测试注入 `_record_ok()` 桩。
**662 passed, 2 skipped**；`k3dge check` 绿。

### 有意偏离票面（附理由）

1. **封版提交由 k3dge 自己写**（票面只说"显式 `git add` 再提交"）。理由：ADR-0004 的相位 3 是
   "审核后**自动**"，而提交是记录的唯一载体——交给操作者手工提交，记录就退回"希望他记得写"。
   `push` 仍是人的边界（§2.1.13），本票不碰。
2. **`tag <M> = B` 指基线而非封版提交**：这样 tag 语义稳定为"审的那一版"，且下一次
   `tag(M_prev)..HEAD` 仍覆盖该里程碑全部工作（T6 的 CHANGELOG 区间据此取到封版提交为止）。
3. **动作序里 `version_bump` 在 `archive` 之后**：先归档（幂等性更强的 fact）再动版本文件；
   顺序对"版号在审计返回之后"没有影响（两节点都在相位 3）。

### 边界（有意留）

`tag` 只立**不删**；已存在的异指向只能人工裁决（`tag` 指向是边界事实，静默改写等于篡改历史）。
