---
status: done
milestone: M9
priority: P2
date: 2026-09-04
---

# 空 except 治理（质量席 Q-6 转票，36 处）

- **Status**: done
- **Milestone**: M9
- **Priority**: P2
- **可检索摘要**: engine/cli 36 处 `except Exception: pass` 类吞错点需分类治理：真兜底留者加注释与 debug 日志面、掩盖编程错误的改 re-raise/warn（首案 F-5 的先例形：[WARN] 落 stderr）；禁止批量刷 pass→log 不分诊
- **Date**: 2026-09-04

## 已确认意图

- 逐处三问：吞的是什么／吞了谁会哑／哑了谁负责；答案进 commit message 不进代码注释。

## 验收

- `grep -c "except.*pass"` 计数下降且每处有分类结论，或质量席复程改判。

## 收尾（2026-09-13 分类治理）
37 处 `except Exception` 逐处三问分类；**纯 `pass` 12 → 9**（定点硬化 3），其余保留并附因：
- **硬化（掩盖真失败 ⇒ 出声）**：
  - `cli/main.py` init `sync_all` 失败 → `[WARN]`（否则初始契约静默不同步）。
  - `engine/milestone.py` `mark_task_done` 报告自动回填失败 → `[WARN]`（封板闸兜底）。
  - `engine/milestone.py` doc-audit lens 路由失败 → `WARN[DOWNGRADE]`（ADR-0006 §2.4 降级可见）。
- **保留（真兜底）**：main.py 文档提示 / peer-wiring 诊断；evaluator changelog/AGENTS 预算（外层已告警）；milestone seal verify（`run_action` 已出 `WARN[DOWNGRADE]`）/ `_prune` 清理；search manifest 缺失→回落发现；version 回滚失败→外层 `raise`；worktree 删线失败→幂等重试靠线仍在。
- 其余 25 处非 `pass`（返回/赋值/表达式）：已带降级/回落语义，保留。
