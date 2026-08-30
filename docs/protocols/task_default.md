# Task Protocol — Default (可检索 / 状态机)

> **事实源**：`k3dge` 仅验"文件存在 / 注册一致"；本文件载 task 文档的机检契约。

## 交付

`docs/tasks/YYYY-MM-DD-<type>-<slug>.md`，含 `Status` / `Priority` 表头与「可检索摘要」。

## Constraints

L2 入场券须逐条确认：

- 含表头 `Status`（`∈ {in-progress, done, cancelled, pending}`）与 `Priority`（`∈ {P0,P1,P2,P3}`）
- 首段含「可检索摘要」段或 `可检索` 关键词，确保跨会话可检索
- 文件名满足 `^\d{4}-\d{2}-\d{2}-[\w-]+\.md$`
- 不得声明与既有 task 完全相同的 `Status: done` 重复闭环
