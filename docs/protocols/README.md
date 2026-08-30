# Protocols — 协议默认文件

各 `<type>_default.md` 是 `k3dge scaffold` 生成对应文档的**脚手架模板**；实时编写规则见各文档目录 README 的 `## 文档编撰规则` 段。`audit_default.md` / `verify_default.md` 为过程协议，由 `.agent/protocols.toml` 路由。

## 文档编撰规则 (Document Authoring Rules)

- 文件名 `docs/protocols/<type>_default.md`，满足 `^[\w]+_default\.md$`。
- 含 `## Constraints` 机检段（仅承载机检项，叙事质量项作 advisory 散文）与 `> **事实源**` 注脚。
- `## Constraints` 下每条机检项以 `- ` 列表项呈现，供 `expected_constraints` 抽取。
