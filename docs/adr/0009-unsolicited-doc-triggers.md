# ADR 0009: 文档与里程碑由触发规则维护，不靠用户再喊一声

- **Status**: Accepted
- **Date**: 2026-08-24
- **Deciders**: Core Maintainer

## 1. 上下文 (Context)
k3dge 的意图不是替用户想「做什么」，而是：用户说出任务后，Agent 在**完成该任务的同一轮**自动维护契约、spec、ADR、milestone 等，使下一会话仍一致。原先 §5/§6 偏口令驱动（「先记下来」「memo一下」），§11 的 align/seal 写得像要用户提醒。MCP 配置若随 Agent 喜好发挥，外部 harness 注入会漂移。

## 2. 决策 (Decision)
- 用户只陈述工作意图。维护文档的**时机**以 `AGENTS.md` §12 事件表为准，禁止等「请写 ADR / 该 sync / 该封板」。
- 口令仍保留的只有：tasks 收件（尚未发生「做完」）、memo 收件（尚未成事）。
- 里程碑：某 `Milestone` 下顶层任务全部 `done` → 当轮 `align`；三闸机可过则当轮 `seal`（先填 stub/guide-stub）。
- MCP：不自动改其它 harness 的配置。用户要求「帮我配」时，只执行 `docs/guides/mcp-bridge.md` 固定剧本。

## 3. 后果 (Consequences)
- 漏写 ADR/漏 sync 是违反协议，不是「用户没叫」。
- seal 仍可能因 guide-stub 失败，Agent 应先填 guide 再 seal，而不是停下来问「要不要封板」。
