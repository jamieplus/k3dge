---
status: done
milestone: M11
priority: P2
date: 2026-09-20
---

# align 报告写一次就停；`_seal_review_gate` 把 12 列稿误报成无 marker

- **可检索摘要**: `run_milestone_alignment` 对当天 `*-align.md` 存在即跳过；审计票后补后清单仍是 44 项。`_seal_review_gate` 扫所有带里程碑 token 的 reviews，12 列稿没有 align-pass marker，错误优先级把「清单缺票」显示成「无 marker」。

## 已确认意图

align 报告是结构桩，任务集会变，必须按当前票重写。align 闸只验对齐报告，不拿 12 列审计稿充 missing_pass。

## 证据（M10 真跑相位 3）

```
align.md 有 <!-- k3dge:align-pass:M10 -->，Completed Tasks: 44
缺 2026-09-20-M10-audit-audit_job_1e408cbd4c78.done.md
2026-09-14-M10-audit.md / 2026-09-20-M10-audit.md 无 pass marker
GATE: [SEAL REJECTED] Review … has no align-pass marker
清单 ⚙️ align_pass —— seal 会先跑它（同一句误报）
align.py: if not review_file.exists()  ⇒ 写一次
```

## 结案

封版提交 `dea69ca`（边界 B 之后，归 M11）已落地：

- `align.py`：每次重写当天 align 报告（含当前全部票名）
- `seal.py` `_seal_review_gate`：只看文件名含 `-align.md`
- 单测 `TestSealReviewGate.test_audit_report_without_marker_does_not_mask_align`

真跑 seal attempt 5 过了 archive 闸并封上 M10。
