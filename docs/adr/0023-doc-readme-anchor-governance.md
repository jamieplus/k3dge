---
Status: Accepted
Date: 2026-08-30
Deciders: Core Maintainer
---

# ADR 0023: 受管文档的 README 锚定治理

## 1. 上下文 (Context)

`docs/` 下各子目录的 frontmatter、章节、机检契约写法长期不一致，Agent 编辑时无可参照的本地约束，评审只能事后纠错。集中式治理（单一 registry、硬编码前缀）要么过重、要么在 agent 够不到处无法强制。需要一种零假设、软规则、结构可机检的模型：约束写在文档自身所在目录的 README 中，编辑前读取即可。

## 2. 决策 (Decision)

1. **约束随域走（隐式路由）**：每个 `docs/` 子目录的 `README.md` 以 `## 文档编撰规则 (Document Authoring Rules)` 锚定段承载本域写法（frontmatter / 章节 / 机检契约）；约束即该目录 README，无中央注册表、无硬编码前缀。
2. **软规则，不注入不强制**：该段是给"读文档的人 / Agent"的约定，编辑时直接读照办；规则文本、单篇 frontmatter/章节、索引同步不由机器校验。
3. **结构-only 门禁（doc-gate）**：`scripts/pre-commit`（经 `git config core.hooksPath scripts` 安装）对暂存的每个 `docs/` 文档，核验其顶层域目录 `README.md` 是否含锚定段——缺 README 或缺锚定段即拦提交；不验内容。
4. **每子目录必备 README**：`docs/` 下每个子目录（adr / branches / incidents / memo / reviews / tasks / protocols / architecture / guides / specs / generated）都必须有 `README.md`；缺失即结构破损。
5. **docs 根仅允许 README.md**：除总纲 `docs/README.md` 外，禁止在 `docs/` 根直放任何其它文档/文件；该约束由 `k3dge check` 的 `DOCS_ROOT_DISALLOWED` 拦截，`evaluator.py` 已对 `docs/README.md` 豁免。
6. **代码侧验证不替代**：`k3dge check`（含 `TEMPLATE_DRIFT`、契约哈希）继续保证微观形式/结构；文档侧规则与之一致但不重合。
7. **治理总纲归 docs/README.md**：所有子域写法总则与子目录索引集中于此，AGENTS.md 路由段仅作指向。

## 3. 产生后果 (Consequences)

- **正**：约束零距离、可发现；新增文档域只需一个带锚定段的 README，无中央改动；doc-gate 把结构破损挡在提交前。
- **负**：锚定段内容质量靠评审保证，doc-gate 不验内容；嵌套内容目录（specs/*、*/archive）归其顶层域 README 管辖，不单独设 README。
- **负**：doc-gate 仅以本地 git hook 形式生效，CI 与 pre-commit 框架未接入，服务端目前不强制 README 锚定。
- **何时重开**：若需服务端强制，将 doc-gate 接入 CI 与 pre-commit 框架、或并入 `k3dge check` 的锚定校验时重评。
