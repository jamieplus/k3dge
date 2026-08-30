# Incident Protocol — Default (B-T-D 证据链)

> **事实源**：`k3dge check` 仅验"文件存在 / 注册一致"；本文件载事故报告的机检契约。

## 交付

`docs/incidents/INC-YYYYMMDD-<TYPE>-<slug>.md`，含 `背景(B)` / `触发(T)` / `处置(D)` 三段与证据链。

## Constraints

L2 入场券须逐条确认：

- 文件名满足 `^INC-\d{8}-[A-Z]+-[\w-]+\.md$`
- 含 `## 背景` / `## 触发` / `## 处置` 三节（B-T-D 不可缺）
- 含至少一条可机器核验的证据链接（产物路径 / 命令输出 / 消费者引用）
- 文件名日期与文件内 `Date` 一致
