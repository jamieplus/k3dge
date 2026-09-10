# Quality Protocol — Default (k3lity 12 列)

> **事实源**：质量层（k3lity，软：复杂度/重复/类型/坏味道，不判"值不值"）。缺 k3lity 时本文件为 `peers.k3lity.actions.quality` 与 `.actions.verify` 的 manual 兜底——人工填质量报告，不伪造分数。审计层（健壮/架构/契约）见 `audit_default.md`，与本层各出一份 12 列报告。

## 一轮"审过一遍" = 两份报告

一次闭环的界定是：**审计报告（k3dit）+ 质量报告（k3lity）都各到 `待修=0`**。改之后按报告各自复审：`k3dit.actions.verify` 核审计报告、`k3lity.actions.verify` 核质量报告，互不串。

## 交付

`docs/reviews/YYYY-MM-DD-<scope>-quality.md`，首行放 `<!-- k3dge:kind: quality -->` 以标类。表头 12 列：

`ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收`

`类型` 取质量维度（复杂度/重复/依赖/坏味道）。每行的 `位置` 处，审计角色可钉一个指针标记 `# k3dit:pending <ID>`（或 `<!-- k3dit:pending <ID> -->`），供 `k3dge check` 扫到、在 `[NEXT]` 里报 `pending=N`。**标记只是指针**，理由/怎么改/验收步骤留在本表，不进代码/文档正文（否则成第三份事实，L1 不哈希注释、硬闸抓不到漂）。

## Constraints（12 列，与 audit/verify 同构）

- 表头 12 列齐备，表体每行列数 == 12，首行含 `k3dge:kind: quality` 标记。
- `状态 ∈ {已修, 待修, 有意留}`；`待修 == 0` 才算质量闭环。
- `有意留` 写进报告 `处置` 并在 `docs/reviews/LEFTOVERS.md` 留一条；对应标记改成 `k3dit:leftover <ID>` 指针（不再计 pending）。
- 已修的发现：删掉代码/文档里的 `k3dit:pending` 标记。
- k3lity 不判"思想值不值得"（那是人/ k3dit），只给可数的质量发现。

## 到达

本文件由 `pipeline.toml` 的 `peers.k3lity.actions.quality.manual` / `.verify.manual` 指向；`k3dge check` 不解析本文件内容，仅在质量阶段按此手填，与 `k3lity_score` 互为同级降级终点。
