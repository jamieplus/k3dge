# Guides

Human Diátaxis how-to. Not a machine SOP.

- **Address**: `k3dge doc list --type guides`.
- **Write**: read [`AUTHORING.md`](AUTHORING.md). `docs/guides/<slug>.md`.

## 这一层是什么 / 从哪读起

Diátaxis 四模式各一份，**入口按角色挑**（名单以 `k3dge doc list --type guides` 为准，本文件不抄清单）：

- 要把 k3dge 装进别的仓 → `downstream.md`（教程/操作）
- 要让 harness 通过 MCP 驱动 k3dge → `mcp-bridge.md`（参考）
- 只想用这套门禁做日常开发 → `user_guide.md`（教程）
- 想知道为什么长成这样 → `architecture.md`（解释；机器版结构在 `docs/generated/`，别混读）

未开的模式不是缺口：`.agent/docs.toml` 里关掉的项目（如 `api_guide`/`deployment`）**默认不生成**，
需要时开配置并由人补，禁止用占位桩冒充"已有"（`<!-- k3dge:guide-stub -->` 会被 seal 前置闸拦）。

