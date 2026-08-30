# Docs — 受管文档根

本仓库所有受管文档的总纲。每个 `docs/` 子目录都是一类文档域，须自带 `README.md` 说明本域写法。

## 文档编撰规则 (Document Authoring Rules)

- **每子目录必备 README**：`docs/` 下每个子目录（`adr` / `branches` / `incidents` / `memo` / `reviews` / `tasks` / `protocols` / `architecture` / `guides` / `specs` / `generated`）都必须有 `README.md`；缺 README 视为结构破损，提交门禁拦截。
- **锚定段即软规则**：各目录 `README.md` 须含 `## 文档编撰规则 (Document Authoring Rules)` 段，约束该目录文档写法（frontmatter / 章节 / 机检契约）。编辑时直接读该段照办，**不注入、不强制**。
- **提交门禁（结构-only）**：`scripts/pre-commit`（已 `git config core.hooksPath scripts`）校验暂存文档所在目录的 README 是否含该锚定段；**缺 README 或锚定段即拦提交，不验内容**。
- **代码侧验证维持不变**：`k3dge check` 仍校验微观形式 / 结构（含 `TEMPLATE_DRIFT`、契约哈希），文档侧规则不替代它。
- **特例**：`specs/`、`generated/` 由 `k3dge` 自管（契约哈希 / 自动生成），其 `README.md` 仅作说明，不手写正文内容。
