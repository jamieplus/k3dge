---
status: idea
milestone: M9
priority: P2
date: 2026-09-04
---

# 空 except 治理（质量席 Q-6 转票，36 处）

- **Status**: idea
- **Milestone**: M9
- **Priority**: P2
- **可检索摘要**: engine/cli 36 处 `except Exception: pass` 类吞错点需分类治理：真兜底留者加注释与 debug 日志面、掩盖编程错误的改 re-raise/warn（首案 F-5 的先例形：[WARN] 落 stderr）；禁止批量刷 pass→log 不分诊
- **Date**: 2026-09-04

## 已确认意图

- 逐处三问：吞的是什么／吞了谁会哑／哑了谁负责；答案进 commit message 不进代码注释。

## 验收

- `grep -c "except.*pass"` 计数下降且每处有分类结论，或质量席复程改判。
