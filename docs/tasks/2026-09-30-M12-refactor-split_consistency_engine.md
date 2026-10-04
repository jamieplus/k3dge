---
status: idea
milestone: M12
priority: P3
date: 2026-09-30
---

# 拆 ConsistencyEngine：检查组各自成模块，只共享 workspace_root


## 已确认意图
拆 ConsistencyEngine：检查组各自成模块，只共享 workspace_root

## 可检索摘要
拆 ConsistencyEngine：检查组各自成模块，只共享 workspace_root

## 上下文/切入点
来源：M11 审计 `value-14`（`docs/reviews/archive/M11/2026-09-29-M11-k3dit-bundle-audit.md`）转票。

**核验（2026-10-04）——债仍在，成立**：`src/k3dge/engine/evaluator.py` 现 **1294 行**，`ConsistencyEngine` 仍是单一 God 类，`evaluate()` 串起彼此无关的多组检查（版本一致性、模板漂移、pipeline、审计留痕、文档闸、域、验证矩阵、域契约），共享的只有 `self.workspace_root`。消费者三处（`cli/main.py:218/1018`、`cli/status.py:111`、`cli/mcp.py:139`）。

**切入**：按检查类型拆成独立 checker（各自 `(workspace, manifest) -> List[Violation]`），类只留编排；先动耦合最低的组，保持 `evaluate()` 返回 `GateReport` 的契约不变。
