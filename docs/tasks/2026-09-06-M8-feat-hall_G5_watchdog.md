---
status: idea
milestone: M8
priority: P2
date: 2026-09-06
---

# G5: W2 轮间清场 + W6 看门狗注入

- **Status**: idea
- **Milestone**: M8
- **Priority**: P2
- **可检索摘要**: 每轮结束销毁/轮换席目录（防残留）；Hall spawn 时注入三重预算（轮数/token/无进展，W6 计数在大厅不在席），触发停机+签名清单+escalated；计数器桩 `fuse()` 已有 task（idle_fuse_counter），本 task 做 Hall 侧接线
- **Date**: 2026-09-06

## Intent

W2/W6 从条款变成 Hall spawn/回收路径上的代码。

## Notes

- W2：轮结束 → 归档席输出 → 销毁/轮换目录；残留检测（新轮目录非空即告警）进 G7 测试。
- W6：spawn 参数 `budget={rounds, tokens, stagnant}`；`fuse()` 纯函数来自 `2026-09-05-M8-feat-idle_fuse_counter.md`（依赖该 task 先出桩）。
- 触发语义：停机 + `WARN[DOWNGRADE]` + 已试签名清单 → escalated 转人工；窗口永不自判"再试一次"。

## 边界与拆分（feat 类必填；规则 08）

- 事实归属：预算/计数属 Hall；席输出归档属账本。
- 边界检查：计数器只哈希签名不存载荷（W1）；agent 本体不实现计数。
- 桩子先行：fuse 桩先行（对方 task）；接线用 dummy 长命席（故意空转）验证熔断。

## Related

- `docs/adr/0025-hall-harness-topology.md`（§2.3 W2/W6）
- `2026-09-05-M8-feat-idle_fuse_counter.md`（fuse 纯函数桩）
- `2026-09-06-M8-feat-hall_G2_kernel.md`（前置：Hall 进程存在，接线对象）
