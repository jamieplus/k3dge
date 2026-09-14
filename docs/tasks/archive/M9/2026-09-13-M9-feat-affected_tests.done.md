---
status: done
milestone: M9
priority: P2
date: 2026-09-13
---

# 受影响测试映射（import 传递 → 测试文件，喂 selective L2）

- **Status**: idea
- **Milestone**: M9
- **Priority**: P2
- **可检索摘要**: 沿 import 反向边传递求"受影响测试文件集"，喂 `k3dge check --with-tests` 选择性 L2；来源 memo `agent-dev-tools-absorption-eval` §1/§3（codegraph `affected` ≡ worktrunk `cargo-affected`）。
- **Date**: 2026-09-13

## Intent
把"改动文件 → 受影响测试文件"落成确定性事实，作为选择性 L2 的输入。

## 上下文/切入点
- 现状：`engine/import_graph.py` 已有 `blast_radius`（下游模块），缺"模块→测试文件"映射。
- 吸收点（clean-room）：传递依赖选测；worktrunk 的"覆盖读不到 ⇒ input-rule 强制选测"防漏思路（可选）。

## 边界与拆分
- 事实归属：import 图/受影响集＝确定性事实（k3dge）；"该跑哪些"判定＝消费侧 CI。
- 边界检查：只出受影响测试文件列表，不执行、不阻断；**缺映射 ⇒ 回落全量**（保守）。
- 桩子先行：先用 `import_graph` 边 + `tests/unit/<domain>/` 目录映射求集，再考虑 input-rule。

## 验收
- `check --with-tests` 可选"只跑受影响测试"；空集回落全量；零依赖。
- **并入**（2026-09-13）：`symbol_graph_store` 取消；确需图边的部分（最小 import/call 边）在本题实现，**不建 SQLite+FTS 平台**（换存储不产生新能力）。

## 收尾（2026-09-13 误置→重指）
- **本票误置**：`import_graph`/`blast_radius` 底物在 **k3dit**（`tools/`），k3dge 无此模块。
- 实现落 **k3dit `feat-affected_tests`**（`5ed05be`：`import_graph.affected_tests` + `k3dit affected` CLI，150 passed）。
- k3dge 侧不重建扫描器（避免跨 peer 重复实现）；`symbol_graph_store` 的"最小图边"随该实现吸收。
