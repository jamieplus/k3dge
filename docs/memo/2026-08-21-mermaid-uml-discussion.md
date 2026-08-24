# Memo: UML 文本 vs 纯文字的选型讨论全过程

- **闪念**：UML（Mermaid 文本）是否比纯文字更适合 agent 与人读？契约层用代码文本 vs UML 文本哪个效率更高？当前是否为该方案？
- **触发场景**：在 `docs/architecture/overview.md` 与 `spec` 的 `State Machine` 已部分文本化后，用户追问是否应统一切 `Mermaid`
- **关联度**：弱相关——属文档范式选型，不影响门禁核心，但影响 harness 作为模板的长期可读性
- **Date**: 2026-08-21

## 讨论过程

1. **初始判断**：Agent 认为契约层文本代码块更高效（与 `contract.py` 直连），架构/状态用 `Mermaid` 更高效，但鉴于 `k3dge` 当前仅 4 域、状态简单，收益边际小，建议"现阶段不换，待域>6 再批量切"
2. **用户反驳**：`harness` 是给**其它工程**用的模板，`k3dge` 自身域少不代表使用方也少；按"优势不小、缺点是规模问题"的逻辑，应**统一标换**更对
3. **Agent 认同**：锚错了——应按使用方的最大复杂度定标准，而非按 `k3dge` 当前最小规模；`Mermaid` 成本在模板层一次定标即可摊薄，遂改判"统一切"

## 决策

* 契约保持代码文本（`spec:20` ` ```python` ）——已最优
* `docs/architecture/overview.md:14,25` 依赖图与数据流、`spec` 的 `State Machine` 统一改为 ` ```mermaid` 块，门禁不验图语法
* 已落地：`overview.md` 与 `engine/spec.md` 切 `mermaid`，`scaffold.py` 的 `ARCHITECTURE_TEMPLATE` 与 `SPEC_TEMPLATE` 同步更新

## 供更成熟系统评判

* 判据：`harness` 作为模板，是否该为"潜在复杂使用者"提前支付 `Mermaid` 的学习与渲染成本
* 反事实：若保持纯文本，复杂工程的 Agent 是否会因散文歧义多耗 token/幻觉；若全切 `Mermaid`，简单工程的裸 `md` 可读性是否受损
* 本次选择"统一切"是否过度设计，或恰是模板应有的前瞻性
