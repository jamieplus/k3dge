# Memo：Harness 环境级硬隔离 vs 认知级软隔离（h8m2k-a1）

- **Date**: 2026-08-27
- **Source**: `h8m2k-a1` 5-Pass 隔离机制论证 + `k3dge/k3dit` 现行落地
- **Status**: memo（`k3dge` 已 `M7` `Gate SUCCESS`，`k3dit` 5-Pass 已 `k3dit_run_audit 1..5`，无需立即转 `tasks`）

> **勘误（2026-09-03，逐条可复跑）** —— 本 memo 的核心判断（环境级硬隔离 > 认知级软隔离）仍然成立，下面两句事实已过期：
>
> 1. 「`k3dit` 5-Pass 已 `k3dit_run_audit 1..5`」当时是**宿主 agent 逐轮自取指令**，不是本 memo 主张的硬隔离：那时 k3dge 侧连 MCP 客户端都没有。今天的对外入口已换成动作级 `k3dit_run_audit_flow`（`../k3dit/src/k3dit/mcp.py:155`），`pass_number` 退回内部原语。
> 2. 支柱表里的「Clean Session 仅注入 `diff + 单轮 focus`」与本仓新规则 `ADR-0006` §2.3.8（调用方不得知道轮次）**正面冲突**。二者只能留一：要么 harness 遍历 peer 返回项（不发明轮次），要么 peer 自己派席。冲突的三条调和路（α/β/γ）与实测需求已记在 `docs/memo/2026-09-02-peer-wiring-and-seat-options.md` §2.1，未在此重复。
>
> 另：本 memo 的 **Capability Gating**（auditor 在能力层被剥夺写权限）目前**仍无实现**——现存的只是事后核查设想（git 快照越界即废）。这一格仍是缺口，别把「事后核」当「事前禁」。

## 1. 核心判断

`审计必须由外部 Harness 在环境与状态机层面强制隔离（环境级硬隔离），绝不能依赖 Agent 在同一上下文内的角色自我约束（认知级软隔离）。`

单 Agent 自写自审在同一 `Session` 必然 `Context Contamination` + `Confirmation Bias` + `CoT Leakage`，把 `Bug` 合理化为原意；`Harness` 将 `Agent` 视为无状态算力，由外部调度上下文、权限、验证时序，方能等效“独立双人审查”。

## 2. 现行 4 支柱（`k3dge/k3dit` 已落地）

| 支柱 | 机制 | 隔离效果 | 落地点 |
|---|---|---|---|
| **Zero-Context Fork** | `coder` 写后 `Harness` 捕 `Git Diff/AST`，**终结 Session**，开 `Clean Session` 仅注入 `diff + 单轮 focus` | 切断 `CoT` 惯性，`auditor` 不知“为何这么写” | `src/k3dit/mcp.py:85 _PASS_FOCUS` 5 次 `k3dit_run_audit`，`len>2000截断` + ````→ˋˋˋ |
| **Capability Gating** | `coder: write/bash` → `auditor: read_file/inspect_ast` 只读，`MCP` 协议层剥夺写工具 | 杜绝 `auditor` 顺手改代码/改测试迎合错误 | `mcp.py:84` `tools` 只读，`k3dit/report.py:21` 只验 9 列 |
| **5-Pass 隔离** | 外部状态机 5 轮独立短生命周期：`security→architecture→design→consistency→performance` 单维度 | 安全不被性能稀释，`P0` 召回↑ | `audit_default.md:9` 5 轮，`k8d3e-a78` 已 `1..5` 各透镜 |
| **确定性裁判** | `Agent` 断言 `file:line` 后 `verifier.assert_evidence_exists` 调 `Tree-sitter`/`pytest`/`k3dge check` 外部校验 | 幻觉/悬空直接拦截重测 | `engine/evaluator.py:119 GateReport` + `milestone.py:445 SEAL REJECTED` 硬阻断 |

## 3. 能力对比

| 维度 | 单 Agent 原生自审（Prompt 约束） | Harness 硬隔离（系统级） |
|---|---|---|
| 上下文 | 共享历史，`CoT` 偏误 | 强制擦除，冷启动 |
| 写权限 | `Prompt` 易击穿 | 协议层切断 `write` |
| 深度 | `Happy Path` 幻觉 | 5 轮穿透 |
| 测试 | `mock` 假实现 | `AST` + 真用例 |
| 阻断 | 概率性可忽略 | `P0` 硬 `rollback_staged` |

## 4. 状态机伪码（`h8m2k-a1.3c`）

`coder_session(tools=[read,write,bash]) → git diff → _run_5pass_audit_isolation(diff)` 每轮 `clean_session(tools=[read_file,inspect_ast])` + `verifier.assert_evidence_exists` → `has_p0_blockers() → rollback_staged` 否则 `commit`

`k3dge` 现行：`ConsistencyEngine.evaluate` 纯判定 + `milestone.py:445` `SEAL REJECTED` 硬阻断，`M7` `k3dit` 5-Pass 已 `Gate SUCCESS`

## 5. 后续（暂不转任务）

- 单 `M7` 空窗 `k3dit` 5-Pass 已验证，`docs/incidents` 单缺陷单报告已 `README` 模板化
- 若 `CoT Leakage` 再现或 `5-Pass` 召回下降，再晋升为 `docs/tasks` 并赋 `P1`（`k3dit` 透镜调优或 `Clean Session` 参数化）
- 关联：`docs/reviews/2026-08-27-M7-k3dit-5pass.md` / `docs/incidents/INC-20260827-*` / `AGENTS.md:12` `Audit fix done → docs/incidents`

---
*Harness 掌握上下文生命周期与工具网关，即单模型亦可自审闭环。*
