---
status: done
milestone: M8
priority: P2
date: 2026-09-05
---

# 空转熔断机制化（W6 活性墙的最小实现）

- **Status**: done
- **Milestone**: M8
- **Priority**: P2
- **可检索摘要**: agent 空转（同一动作+同一错误反复重试）现无机制拦截——`check` 只在 commit 时跑，不在 agent 循环里；需把 `(动作签名,结果签名)` 连续 N 全等检测做成机制（宿主 hook 计数器或大厅看门狗），触发即停机 surface 转人工
- **Date**: 2026-09-05

## 依据

- 维护者报告：观察到"agent 一直空转"的实例，问"是否要规定一直重复出错就停止"。
- 判据（rules/10）：现有三条止损全是散文或场景特例（check 红×2 / seal verify >3 / hillclimb"卡住要 surface"），通用空转无闸；且"发现自己一直转"依赖自我意识，而空转的定义即自我意识失效（上下文压缩后看不见前 N 轮）——**计数者必须在 agent 之外**。
- 定案：`ADR-0025` W6（活性墙，Proposed 段就地加入）；软规则行已进 `AGENTS.md` 触发表。

## 上下文/切入点

- 无进展签名：动作签名 = 命令/目标文件+操作；结果签名 = 退出码/输出哈希/失败测试名。连续 N（默认 3）全等 = 熔断。
- 两条实现轨（择一先桩）：
  1. **宿主 hook**（opencode/claude hooks）：tool-call 流水落 `.agent/` 本地计数，命中即注中断消息；
  2. **Hall 看门狗**（ADR-0025 实施时）：spawn 窗口带轮数/token/无进展三重预算，超时 kill + `WARN[DOWNGRADE]`。
- 边界：计数器是程序不是判断（大厅纪律：确定性管流程）；触发后**不自动重试**，按 escalated 先例转人工。

## 验收

- 单测：喂脚本化动作流（同签名 ×3）→ 断言熔断 + 签名清单输出；异签名交错 → 不熔断。
- 现网演练一次：故意让 agent 撞同一错误三次，观察是否第 4 次前停。

## 边界与拆分

- 事实归属：动作/结果流水属宿主（或 Hall 进程）；阈值配置属 `.agent/`；熔断语义（escalated 转人工）属 k3dge 既有状态，不新建。
- 边界检查：计数器不得读窗口内容（W1）——只哈希签名，不存载荷；agent 本体不实现计数（否则违"计数者在 agent 外"）。
- 桩子先行：先纯函数 `fuse(observed_stream)->verdict` + 脚本化测试（骨架绿），再接 hook/Hall 传输。

## Related

- `docs/adr/0025-hall-harness-topology.md`（W6）
- `.agent/rules/10-structure-over-prose.md`（本 task 即"叮嘱→机制"的下沉）
- `AGENTS.md` 触发表"空转"行
