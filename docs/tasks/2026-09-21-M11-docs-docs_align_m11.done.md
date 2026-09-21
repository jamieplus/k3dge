---
status: done
milestone: M11
priority: P2
date: 2026-09-21
---

# 文档对齐：downstream 手册跟上 hooks 下发 + 六条持久设计并入 ADR-0004/0018

- **可检索摘要**: 一次对齐审计（"至少与 M10 对齐"）：机检面全对（架构两件在 `M10..HEAD` 内已更新、spec 接口块/哈希由 sync 回写、矩阵行齐、generated Reference 自动），但**人写面两处落后**——① `docs/guides/downstream.md` 的"拷进仓"清单与激活口径还是旧的（没写 hooks 两件、激活只写 `pre-commit install`、没写"首提交前先 sync"）；② 今天六条持久设计**一条都没进 ADR**（只在票与 LEFTOVERS 里）。

## 证据

```
_architecture_staleness(M11) → ✅ overview/encyclopedia 在 M10..HEAD 内都已更新（区间 src+specs 48 文件）
grep -l "ARCH_TABLE_DRIFT|ARCH_STATE_DOC_DRIFT|_refresh_projections|doc_gate|INIT_DELIVERED_DOCS" docs/adr/*.md → 零命中
docs/guides/downstream.md:14 "拷进仓的协议与包装" 清单无 scripts/pre-commit|commit-msg
docs/guides/downstream.md:39 激活只写 `pre-commit install`（与本仓/下发 AGENTS.md 的 core.hooksPath 口径不一）
到达环测试（test_hooks_reach_downstream）实测：下游首提交前必须先 `k3dge sync`
```

## 方案

1. `docs/guides/downstream.md`：清单加 hooks 两件（并说明闸逻辑在 `engine/doc_gate`）；激活口径统一为 `core.hooksPath scripts`，并说明 `pre-commit` 框架路也指向同一实现；补"首提交前先 `k3dge sync`"；镜像到资产（PAIRS）。
2. ADR 并入（**不新开**，按 §12「先并同类」+ AUTHORING 的 Amend 口径）：
   - `ADR-0004` 🅰3：相位 3 先刷**纯投影**、不跑整条 `sync`（事实源写归审前）+ 派生件新鲜度四闸 + `k3dge where` 自愈（正文改 + footnote）。
   - `ADR-0018` 🅰1：新增第 13 项——文档面事实对账（域表/状态集两闸、"要么不写要么写全"）、**到达环**（闸逻辑归 engine、hooks 与治理件随 init 下发）、引用闸自限定、排查面豁免；并给第 11 项"硬底"那句加脚注（到此时才实测成立）。

## 边界与拆分

- 事实归属：行为在代码（已落），本条只做**文档对齐**（手册 + 决策记录）；不新增机制、不改判据。
- 授权：Accepted ADR 就地修订按 ADR-0004 抬头要求**显式人工授权**——本条由 Core Maintainer 口头授权（"y"）。

## 结案

- 落地：`docs/guides/downstream.md`（三处）+ 资产镜像；`docs/adr/0004-milestone-lifecycle-governance.md`（🅰3 + footnote `[^🅰3.1]`）；`docs/adr/0018-doc-readme-anchor-governance.md`（🅰1 + 第 13 项 + footnote `[^🅰1.1]`）。
- 验证：`k3dge check --force-full --with-tests` 绿（四域，含 `adr_gate` 对 `Amended-by`/`Landed-by` 的解析）；`pytest -q` 734 passed, 2 skipped；`TEMPLATE_DRIFT` 通过（downstream 资产字节一致）。
- 有意留：`docs/guides/*` 其余篇章与 `mcp-bridge` 的工具表**今天没有行为变更**，未动（避免无因编辑）。
