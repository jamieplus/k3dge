# 封板闸机改为验收证据而非 align 自动桩，并校验任务 Status 枚举

- **Status**: done
- **Priority**: P1
- **Date**: 2026-08-24
- **来源**：[docs/reviews/2026-08-24-8dim-vibe-audit.md](../reviews/2026-08-24-8dim-vibe-audit.md) S-05 / S-06

## 可检索摘要
ADR 0004 规定「对齐与验收 → 填写 reviews → 封板」。实现上 `align` 会自动生成 `{date}-{id}-align.md`，正文已写「准予封板压缩」、重构清单为未勾选框。`seal` 闸机 1 只要求「文件名含 id 且非空」，不看内容是否填完，也不验证本次 align 跑过回归。结果：align + 在 SUMMARY 追加一行 id 即可 seal，人工验收被绕过。同时 Status 捕获任意 `[\w-]+`，缺省为 `unknown`，不拦截 `idea → done` 非法跃迁。

## 上下文/切入点
- 自动桩：`src/k3dge/engine/milestone.py` `run_milestone_alignment` 写 reviews 段（约 156–186 行）
- 闸机：`seal_milestone` 闸机 1/2（约 211–231 行）
- 状态：`STATUS_RE` 与 `status != "done"`
- 决策：`docs/adr/0004-milestone-lifecycle-governance.md` §2.1
- 相关：A-01 已修子串误匹配，不解决「桩文件本身就能过闸」

## 方案
1. align 生成的模板必须带未完成标记（例如 `<!-- ALIGN-STUB -->` 或未勾选即视为未填）；seal 拒绝仍含该标记或「重构准入」未勾选的文件。
2. 或者 align 只打印路径、不落盘，强制人/Agent 手写 reviews（与 ADR「填 reviews」更贴）。二选一，推荐 1（保留脚手架）。
3. `STATUS` 白名单 `{idea, deferred, in-progress, done}`；未知值在 align/seal 视为失败并列出文件。非法跃迁（无历史则无法做边校验）至少拒绝未知枚举。不在本任务做完整边表，除非用户要求。

## 触发条件
用户确认方案 1 或 2 后开工。
