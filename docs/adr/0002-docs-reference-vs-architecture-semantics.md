---
Status: Accepted
# Append-only after Accepted. Revise via `Amended by` / `Superseded by` below — do
# NOT rewrite this decision's prose in place, and never reuse a number (see README).
Supersedes: -
Amended-by: -
Date: 2026-08-21
Deciders: Core Maintainer
Note: ① 人读化改写（按 AUTHORING「人读优先」：决策先行、一行一点、长条拆子项；不变量与编号不变）2026-09-10，经 Core Maintainer 本轮显式授权，依 `docs/adr/AUTHORING.md`；过闸口径 = manual fallback（实测 `command -v k3dit` 无输出，no live lens）。
---

# ADR-0002: docs 判据与投影的语义分工（architecture vs generated）

> **Related**: ADR-0018（README 锚定治理）

## 1. 上下文 (Context)

机器生成的 manifest 快照与人（维护者）写的系统级判据内容高度重叠。

- 两者曾同放在易混淆的目录名下（旧名 `docs/reference/`）。
- 缺少「谁是判据、谁可重建」的声明时，Agent 会把成对物合并或删掉其中一份。

## 2. 决策 (Decision)

1. reference 侧目录现为 `docs/generated/`，消除同名混淆。
   - 该侧内容是机器生成的 manifest 快照 / 投影，如 `docs/generated/domains.md`。
2. 语义分工永久固定：
   - `docs/architecture/overview.md` = **一致性判据**：人写常驻，Agent 跨域改动必读；含依赖方向、数据流、全局不变量。
   - `docs/generated/*` = **投影**：`k3dge sync` 从 manifest 派生，可随时重建，**永不作为一致性判据**。
3. 通用纪律（写入 AGENTS.md）：动任何"看似冗余"的成对物前，必查 `docs/adr/` 与全局不变量。
   - 无据则停下来询问，不得自作主张合并/删除。

## 3. 产生后果 (Consequences)

- **正面**：判据与投影职责分明。
  - 同类混淆有 adr 可查，第二次不再依赖人在场解释。
- **负面**：两处域表仍会同步更新（同源但手工）。
  - 接受此成本，以换取判据文件不被生成逻辑覆盖。
- **升级条件**：第 3 对语义相近产物出现，或第 2 次同类事故发生时。
  - 再考虑引入 `.agent/manifest.json` 的 docs_registry 类型注册表做创建期拦截。
