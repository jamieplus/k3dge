---
status: done
milestone: M8
priority: P1
date: 2026-09-06
---

# G2: Hall 内核常驻进程（人肉窗先行）

- **Status**: done
- **Milestone**: M8
- **Priority**: P1
- **可检索摘要**: 把"agent 幂等步进"换成常驻调度进程（叫号→物化→收集→验签→推进→通告牌 + watch 账本事件循环），闭包计数表达"审计+复核双闭合才 seal"；窗口先由人肉担任（人当席跑通全链），自动派席放最后
- **Date**: 2026-09-06

## Intent

Hall 从"人点的命令"变成"常驻的进程"。第 2 步结束就能跑起来出结果——因为席是人，不依赖 G3/G4。

## Notes

- 状态机：单账（G1）+ `state ∈ {open, audit_closed, review_closed, sealed}`，双闭合才 seal。
- 事件循环：watch 账本文件/mtime 或轮询，推进 + 通告牌（降级公示）。
- 人肉窗验收：人按 claim→complete→sign 完整走一单（含打回一次），Hall 只管周转不代笔。**过渡态豁免 sidecar**：同一人兼席签名与 seal 接受仅限本 task 验证周转，G3 起恢复（席≠章）。
- kill -9 演练：Hall 崩溃重启后调度位置一致（W4 无自有状态）；单均耗时/轮数基线落盘（4 窗冷跑成本的可持续性依据）。
- `audit advance` 归修席窗能力，Hall 只调度不代推（主权线，见 G6）。

## 边界与拆分（feat 类必填；规则 08）

- 事实归属：调度序/闭包计数属 Hall；判断内容属席（人）；账本属审计模块。
- 边界检查：Hall 不读 findings 语义（验签只验形+钥）；人不碰 Hall 计数。
- 桩子先行：无席可测——dummy 席（脚本回固定报告）跑通全链，再换人肉。

## Related

- `docs/adr/0025-hall-harness-topology.md`（§2.1 大厅模型、§2.3 W4/W5/W6、§2.6 Accepted 门槛——本 task 与 G3 同为 Accepted 双门之一）
- `2026-09-06-M8-feat-hall_G1_merge.md`（前置：一本账）
