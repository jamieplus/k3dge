# ADR 0007: k3dge 处于自举开发（dogfood / bootstrap）

- **Status**: Accepted
- **Date**: 2026-08-24
- **Deciders**: Core Maintainer

## 1. 上下文 (Context)
「本仓自用」（ADR 0005）容易读成「还没给别人用的玩具」。实际阶段是 **用 k3dge 开发 k3dge**：本仓的 Agent 协议、`k3dge check`/`sync`/`milestone`、specs、reviews、MCP 注入，全部作用在本仓库自己身上。下游发行不是当前目标。

## 2. 决策 (Decision)

- 当前唯一生产路径是 **自举**：改本仓代码必须过本仓门禁。
- 「生产 ready」= 能作为本仓的硬门禁拦住自举过程中的契约漂移，**不是** PyPI 产品 ready。
- 安装默认 editable（ADR 0005）是因为自举需要改完立刻用同一份代码，不是权宜之计。
- 不为此阶段做：发布流程、对未知下游的安装 UX、多租户 MCP。那些等自举循环稳定、第一次要给第二个仓用时再开。
- 第二个仓出现时：设 `K3DGE_SOURCE` 指向本检出；仍不必上 PyPI，直到有「无本仓路径」的用户。第一批第二个仓定为并列 harness（ADR 0008：audit / quality / cache），不是任意业务仓。

## 3. 后果 (Consequences)
- Agent 不要把「缺 PyPI / 缺通用安装向导」写成 blocker。
- 本仓文档、测试、门禁的缺口会直接伤到开发自己，优先修自举路径上的问题。
- 质量闸、审计 harness 同样先对本仓 dogfood，再考虑拆仓发行。
