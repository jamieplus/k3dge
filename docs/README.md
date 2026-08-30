# Docs — 受管文档根

本仓库所有受管文档的总纲。每个 `docs/` 子目录都是一类文档域，须自带 `README.md` 说明本域写法。

## 文档编撰规则 (Document Authoring Rules)

- **每子目录必备 README**：`docs/` 下每个子目录（`adr` / `branches` / `incidents` / `memo` / `reviews` / `tasks` / `protocols` / `architecture` / `guides` / `specs` / `generated`）都必须有 `README.md`；缺 README 视为结构破损，提交门禁拦截。
- **docs 根下仅允许 README.md**：除本文件 `docs/README.md`（总纲）外，禁止在 `docs/` 根下直接放置任何其它文档/文件；其它内容必须归入对应子目录（无合适子目录时新建）。该约束由 `k3dge check`（`DOCS_ROOT_DISALLOWED`）机检拦截。
- **锚定段即软规则**：各目录 `README.md` 须含 `## 文档编撰规则 (Document Authoring Rules)` 段，约束该目录文档写法（frontmatter / 章节 / 机检契约）。编辑时直接读该段照办，**不注入、不强制**。
- **提交门禁（结构-only）**：`scripts/pre-commit`（已 `git config core.hooksPath scripts`）校验暂存文档所在目录的 README 是否含该锚定段；**缺 README 或锚定段即拦提交，不验内容**。
- **代码侧验证维持不变**：`k3dge check` 仍校验微观形式 / 结构（含 `TEMPLATE_DRIFT`、契约哈希），文档侧规则不替代它。
- **特例**：`specs/`、`generated/` 由 `k3dge` 自管（契约哈希 / 自动生成），其 `README.md` 仅作说明，不手写正文内容。

## 子目录索引 (Subdirectory Index)

| 目录 | 用途 |
| --- | --- |
| `adr/` | 架构决策记录（ADR），按编号独立成文件（`NNNN-<slug>.md`） |
| `architecture/` | 人类可读的架构总览与导航（ADR 记"决定"，本目录记"全貌与脉络"） |
| `branches/` | 试错分支归档（check 红后、stash 前的失败分支自包含摘要） |
| `generated/` | `k3dge` 自动生成（Diátaxis Reference / symbol-index 等），勿手改 |
| `guides/` | 人类撰写的使用指南 |
| `incidents/` | 事故复盘知识库（B-T-D：哪坏 / 为何坏 / 怎么修 / 证据在哪） |
| `memo/` | 暂不成事的灵光收件箱（模糊概念 / 暂无法落地 / 弱相关） |
| `protocols/` | 协议切片文档侧总览（与 `.agent/rules/*` 互补：本目录给"读文档"，`.agent/` 给"工具读协议"） |
| `reviews/` | 代码审计 / 评审归档（append-only，点时快照） |
| `specs/` | 各域契约规格，由 `k3dge check` 机检（含 Contract Hash） |
| `tasks/` | 唯一工作项容器（Status / Priority 两维独立） |
