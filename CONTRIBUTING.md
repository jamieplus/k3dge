# Contributing

本仓自举运行（用本仓的 k3dge 开发本仓，见 ADR-0007）。欢迎提交代码/文档/规约。

## 搭环境

```bash
./k3dge-init.sh   # 或 k3dge-init.ps1
k3dge check       # 当前门禁面：docs/specs contract 漂移 / TEMPLATE_DRIFT / doc-gate 等
```

默认 editable 装本仓 `pip install -e ".[dev]"`，改完立刻以同一份代码生效、不走 PyPI。

## 提交要求

- 提交信息走 Conventional Commits（`fix(engine): …`、`docs(readme): …`、`chore(seal): …`）。
- 带进「受管路径」的提交必须经 `git hooks`（由 `core.hooksPath=scripts` 启用）；hook 会追加 `k3dge-commit:` attestation 行。CI 全量验。
- `k3dge check --with-tests` 与全量 `pytest tests -q` 都必须绿才能合入。
- 改动 `docs/` 须同时更新派生投影（`k3dge sync`），或保证 `docs/generated/` 一致。
- 成功后的 closed audit 才允许 seal 下一章。

## 与 agent 协作

`.agent/manifest.json` 是 manifest 事实源；改动公开接口要同步 `docs/specs/<domain>/spec.md` 接口块，再 `k3dge sync`。`.mcp.json` 不入库，属每台机器自己的对等 harness 绑定（模板/生成器见 `.agent/pipeline.toml`）。
