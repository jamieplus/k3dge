---
Status: Proposed
# Append-only after Accepted. Revise via `Amended by` / `Superseded by` below — do
# NOT rewrite this decision's prose in place, and never reuse a number (see README).
Supersedes: -
Amended-by: -
Date: 2026-09-11
Deciders: Core Maintainer
Note: ① 2026-09-11 新建（Proposed 段），经 Core Maintainer 本轮显式授权（会话指令「三条全实做」），依 `docs/adr/AUTHORING.md`：把 MCP 工具 `workspace_path` 从「直通不收敛」改为「默认锁服务根、越界显式化」。过闸口径 = manual fallback（Core Maintainer 会话授权，agent 代改字）。
---

# ADR-0026: MCP 服务根的 workspace_path 收敛

## 1. 上下文 (Context)

- MCP 注入面（ADR-0006）为本地 stdio，信任域＝OS 用户（S-13）；防伪不成立，仍靠主体分离。
- 但 MCP 工具带可选 `workspace_path`，此前直通 `_find_workspace`、不解析收敛。
- 一个任意 `workspace_path` 即旁路窗/仓物理隔离（ADR-0025 §2.7 防越窗写）：可读他仓 manifest、写 task、seal 搬移他仓，`with_tests` 更对任意路径执行 pytest。
- 约束：不得废跨仓 `workspace_path`（既有流程/测试依赖它）；不得把信任域从 OS 用户升级（ADR-0006 重开条件未到）。

## 2. 决策 (Decision)

- MCP 服务进程启动时钉住**服务根**：`K3DGE_MCP_ROOT`＝启动 CWD（`cli/mcp.py` 的 `__main__` 设定）。
- `_find_workspace(workspace_path=…)` 在服务根存在时，要求解析后的路径**位于服务根之内**；越界即 `raise`（显式化，不静默旁路）。
- 跨仓为显式例外：设 `K3DGE_ALLOW_EXTERNAL_WORKSPACE=1` 才放行服务根之外的路径。
- 非 MCP 直调（CLI / 测试）不设服务根 ⇒ 语义不变。
- 非目标：不做防伪 / 多用户隔离（仍是 OS 用户）；不放宽 `with_tests` 对仓内代码的执行（仓内受信）。

## 3. 产生后果 (Consequences)

- **Up**：`workspace_path` 不再能静默旁路窗/仓隔离；越界抬头可查（错误含服务根与越界路径）。
- **Down**：托管的 MCP 服务若需同时服务多个仓，须显式设 `K3DGE_ALLOW_EXTERNAL_WORKSPACE=1`；忘记设会报错而非静默。
- **Reopen when**：MCP 转网络 / 多用户（ADR-0006 重开条件）⇒ 升级为认证与授权，而非路径收敛。
