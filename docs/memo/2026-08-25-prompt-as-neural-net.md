# Memo: Prompt as Neural Net — 稀疏门控解释框架

- **类型**：模糊概念（解释话语体系，非可执行方案）
- **念头**：`https://blog.kunchenguid.com/p/your-agentsmd-is-a-neural-net` 将 `Prompt` 类比神经网络：过长 `AGENTS.md` 致全连接注意力稀释与跨规则梯度干扰；解法为稀疏门控路由（`AGENTS.md` 微内核仅常驻底线 + 路由，`.agent/rules/*.md` 按需激活）与硬约束下沉（确定性校验移出 `Prompt` 至 `engine` 物理阻断）。`k3dge` 现 `51` 行微内核已是该隐喻的最简工程解，无需再为此改代码
- **触发场景**：用户喂该文给 `Gemini` 得三点采纳后，问"这套话术如何学习、是否加 ADR"
- **关联度**：弱相关——属说服与命名工具，非门禁硬改；`k3dge` 的 `AGENTS.md` 已固化稀疏路由，`ADR` 仅记跨域不变量
- **Date**: 2026-08-25
- **处置**：仅 `memo` 存档作解释框架，不建 `ADR`/`tasks`；后续向新 Agent 解释"为何瘦身"时引用本篇即可
