---
type: AST
severity: P1
status: closed
---

# Incident: 旧报告充闭环——ratchet 的「已闭环」只看本地账，M10 因此被封板

## 1. 现象与证伪证据 (B-T-D Evidence)

- **预期行为 (Baseline)**：`k3dge milestone seal M10` 必须**先真跑一次审计**（ADR-0004 §2.1.9
  相位 2）；审计没正常返回 ⇒ 不得归档、不得提版、不得立边界 tag。
- **现存破损 (Treatment)**：真跑实测 —— seal 一路走完并打印
  `审计: closed（audited；基线 a98e3a7b0cbb）`，随后**归档 44 张票、提版 0.1.12、写封版提交、
  立 `tag M10`**。而它的审计依据是 2026-09-14 的旧报告（`基线: 0cb1b42`，其后 **60 个提交**）。
- **复现路径**：
  ```bash
  # 本地账里存在一条陈旧的 collected 单（基线远早于当前 HEAD）
  python -c "import json;d=json.load(open('.agent/audit_jobs.json'));\
print([j for j in d['jobs'] if j.get('milestone_id')=='M10'])"
  # ⇒ baseline 0cb1b42…, state collected, counts.待修 0, merge_ok True
  git rev-list --count 0cb1b4245dc3ae134e9c95f9e99604f8b235a223..HEAD   # ⇒ 60
  k3dge milestone seal M10 --yes    # 旧代码：判 closed 并封板（错）
  ```
- **记录自相矛盾（durable 证据）**：封版提交 trailer 写 `Audit-baseline: a98e3a7b0cbb`，
  而作为依据的报告写 `基线: 0cb1b42…` —— 两者不是同一版，说明"审哪版封哪版"未成立。

## 2. 根因剖析 (5 Whys)

1. 为什么旧报告能充闭环？→ `_ratchet_audit_step` 的"已闭环"分支只读本地账
   （`state == collected ∧ merge_ok ∧ counts.待修 == 0`），不验磁盘与 git。
2. 为什么只读本地账？→ 该分支写在"本地账＝k3dge 自己的事实"的旧前提上；而本地账
   （`.agent/audit_jobs.json`，gitignored）真正的定性是**运行态投影**（ADR-0004 §2.1.10）：
   可重建、可陈旧，冲突应以 git/磁盘为准。
3. 为什么 T1/T4 没堵住它？→ 两条修法各自覆盖了别的入口：T1 堵 oneshot 的 `skip`/`ok=False`
   与"配置层 `stages_produce` 留空"；T4 **立了**"git 为准"的原则并加了 `audit_evidence()`，
   但**没有把它接到 ratchet 的接受判定点上**（原则与判定点脱节）。
4. 为什么测试没拦住？→ 相关单测（`test_collected_closes_without_resubmit`）用的是**临时目录
   里的桩账**，天然无法暴露"账陈旧"与"文件不在盘上"这两类事实。
5. 为什么到"真跑"才发现？→ 之前所有验证都在 oneshot 桩上做；本仓生产配置是 `ratchet`，
   而 ratchet 的那条分支从未在真仓真数据上走过。

## 3. 防退化动作清单

| 动作 | 落点 | 证据 |
| --- | --- | --- |
| 接受"已闭环"前逐条验事实 | `milestone_audit._closed_job_evidence()`：①报告**文件在盘上** ②署名齐 + 待修=0（**从文件重算**，不用账里 counts）③报告 `基线` == 单 `基线` ④单基线**覆盖本轮 B** | `test_stale_collected_job_is_not_accepted`（陈旧 ⇒ 去建新单 + stalled）、`test_missing_report_file_is_not_accepted` |
| 本轮基线 B 进流程 | `run_audit_flow(..., fresh_baseline=)` / `_ratchet_audit_step(..., fresh_baseline=)` | `test_collected_closes_without_resubmit`（真 git 仓 + 真报告 ⇒ 接受） |
| 判定用真仓真数据 | 上述两条测试改为**真 git 仓 + 真报告文件**（桩账测不出"陈旧/缺文件"） | 同上 |
| 错前提的封板作废 | commit `dda8280`（revert seal）+ `git tag -d M10` | `seal-check M10` ⇒ `[EVIDENCE] 边界 tag M10 = -；封版记录 缺` |
| 修好后行为回归 | 重跑 seal ⇒ 打印"本地账里那单不算本轮审计（…早于本轮基线）⇒ 需要本轮新单"并**停下** | 见 §4 |

## 4. 经验灌入

- **原则必须接到判定点上**：T4 立的"git/磁盘优先"只在文档与一个新函数里；只要**接受路径**
  没换成它，原则就等于不存在。教训：立原则时同轮改**所有**会读旧源的分支（本仓当时有
  oneshot 与 ratchet 两条）。
- **本地账的"独立副本"永远是老化源**：任何"账里说完成 ⇒ 当完成"的判定都要配一条
  "事实还在不在"的复核（存在性 + 自洽 + 时效三件套）。
- **桩测试测不出事实类缺陷**：与磁盘/ git 有关的不变量，测试必须落在真仓真文件上
  （本票把两条测试从桩账改成真仓，改完立刻能复现原缺陷）。
- **"真跑一次"不可替代**：45 个提交、689 条测试全绿，缺陷仍在——因为生产路径（ratchet）
  从未在真数据上走过。凡引入新入口/新相位，收尾必须含一次真跑。
- 本事故暴露的相邻口径问题已裁定并落地（ADR-0004 §2.1.11 🅰2）：`manual` 作为**首选**传输
  （`downgrades` 为空）也一律记 `degraded-manual` 并要求署名——判"有没有独立透镜"（事实），
  不判"链里排第几"；否则"把 manual 排第一"就是绕开署名、且 trailer 记成 `closed` 的路。
