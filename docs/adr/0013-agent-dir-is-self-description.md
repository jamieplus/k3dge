# ADR 0013: `.agent/` 是 Agent 自说明根，不是「只有 manifest.json」

- **Status**: Amended by ADR 0014
- **Date**: 2026-08-24
- **Deciders**: Core Maintainer

> **修正**：ADR 0014 撤回「Agent 打开本目录即自说明」。三件套清单仍有效；发现面是 `AGENTS.md`。

## 1. 上下文 (Context)
k3dge 的目的是换会话、换模型仍一致（ADR 0001 / 0011）。为此把口头约束落到磁盘。目录名 `.agent/`、`_find_workspace` 以它为 workspace 标记、里面同时放 `manifest.json` / `rules/` / `docs.toml`，本来就是：**Agent 打开这个目录就能自说明这个项目怎么被治理**。

这段目录级初衷没有写成自包含文档。后人只看见 `manifest.json` 是地址簿（client_intro、README、engine spec），rules 变成没人读的切片（直到 ADR 0012），`docs.toml` 只在 generate-docs 注释里。Agent 按 AGENTS.md 干活可以整段对话不提 `.agent/` 这个目录——自说明失败。用户指出后确认：信息丢失，应写回磁盘，禁止只活在聊天里。

ADR 0012 只裁定 rules vs AGENTS.md，不定义「`.agent/` 这个目录是什么」。本条补上。

## 2. 决策 (Decision)

1. **`.agent/` = Agent 工作区根**（对标 `.git`）。打开它应能回答：域怎么路由、纪律在哪、收尾要写哪些人读文档。入口是 `.agent/README.md`（目录自说明）。
2. 三件套职责固定：
   - `manifest.json`：机器事实源（域路由）。`k3dge check/sync` 读这个，不读 README。
   - `rules/`：协议切片（ADR 0012）。
   - `docs.toml`：人读文档生成配方，给 Agent 收尾用，不是门禁输入。
3. 仓库根 `AGENTS.md` 仍是活协议（主流 harness 加载它）。它必须**指向** `.agent/README.md`，不能把目录级初衷只写在对话或只写在 ADR。
4. `k3dge-init` 必须写出 `.agent/README.md`，与本仓同一份（`templates/assets/agent-readme.md`），避免下游仓再次丢失。
5. 不把 `AGENTS.md` 搬进 `.agent/`：那会让 Grok/Codex 不再自动加载。若将来主流 harness 改约定，再重开本 ADR。

## 3. 后果 (Consequences)

- **正**：换 Agent 打开 `.agent/` 不再需要上一轮聊天；目录名与内容重新对上。
- **负**：又多一份要与 assets 对齐的 README（`test_template_sync` 锁）。
- **何时重开**：把 AGENTS.md 放进 `.agent/`；或给 `.agent/` 加第四类文件（须先改本 ADR，禁止静默堆）。
