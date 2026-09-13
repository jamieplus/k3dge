---
status: done
milestone: M9
priority: P2
date: 2026-09-04
---

# 复杂度债登记（质量席 Q-1/Q-2/Q-4/Q-5/Q-7 转票）

- **Status**: done
- **Milestone**: M9
- **Priority**: P2
- **可检索摘要**: k3lity 质量席首程把极高/高/中圈复杂度与文件体积超线归组转票：evaluate(61)/_auto_backfill_reviews(50)/_validate_file(40) 等 CC≥11 函数群 + main/milestone 超 1000 行；拆解须与 A-1 上帝模块票（2026-09-04-M7-chore-engine_milestone_py_A_1_1547_6.md）合流推进，禁止为过闸刷指标
- **Date**: 2026-09-04

## 已确认意图

- 本票是**债的登记册不是修复承诺**：每个函数拆/降须带测试护航单独成程（Simplify-first，见 rules/02）；
- CLI argparse 派函数（Q-3）若席认可"派形状天然分支多"，可只调阈值口径不修码——记录在报告，不在此票。

## 验收

- 拆分票逐函数闭环（每票一 diff 一测试跑），或质量席复程改判；不得整体销账。

## 收尾（2026-09-13 并入 A-1）
- 本登记册**并入** `2026-09-04-M7-chore-engine_milestone_py_A_1_1547_6.md`（该票正文现含 2026-09-13 实测的完整 CC≥11 函数表 + >1000 行文件）；本文件按「先并入，后新建」物理删除（git 留档）。
- 拆分执行归 A-1：逐函数/逐模块单独成程，禁止整体销账。
