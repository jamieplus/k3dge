---
Status: Accepted
Date: 2026-08-21
Deciders: Core Maintainer
---

# ADR 0002: docs 双架构文件的语义分工（reference vs architecture）

## 1. 上下文 (Context)
`docs/reference/architecture.md`（机器生成的 manifest 快照）与 `docs/architecture/overview.md`（人写的系统级判据）内容高度重叠，Agent 在"去重"时险些合并两者。经人指出才避免——暴露出"看似冗余实则有别"的成对产物缺乏语义声明。

## 2. 决策 (Decision)
1. reference 侧更名为 `docs/reference/domains.md`，消除同名混淆。
2. 语义分工永久固定：
   - `docs/architecture/overview.md` = **一致性判据**：人写常驻，Agent 跨域改动必读；含依赖方向、数据流、全局不变量。
   - `docs/reference/*` = **投影**：`k3dge sync` 从 manifest 派生，可随时重建，**永不作为一致性判据**。
3. 通用纪律（写入 AGENTS.md）：动任何"看似冗余"的成对物前，必查 `docs/adr/` 与全局不变量；无据则停下来询问，不得自作主张合并/删除。

## 3. 产生后果 (Consequences)
- **正面**：判据与投影职责分明；同类混淆有 adr 可查，第二次不再依赖人在场解释。
- **负面**：两处域表仍会同步更新（同源但手工），接受此成本以换取判据文件不被生成逻辑覆盖。
- **升级条件**：当第 3 对语义相近产物出现、或发生第 2 次同类事故时，再考虑引入 `.agent/manifest.json` 的 docs_registry 类型注册表做创建期拦截。
