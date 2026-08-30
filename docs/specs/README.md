# Specs — 契约规格

各域 `spec.md` 是 `k3dge` 的**契约规格**，由 `k3dge check` 机检（含 Contract Hash）。

## 文档编撰规则 (Document Authoring Rules)

- 本目录由 `k3dge` 管理，**勿手改** frontmatter 的 Contract Hash；改动公共符号后运行 `k3dge sync` 重新对齐。
- 文档侧写法（章节 / 描述）由各域 ADR 约束；新增域须先有 `manifest.json` 条目。
- 本目录不要求手写叙事内容；结构由 `k3dge check` 保证。
