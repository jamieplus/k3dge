# `.agent/` — k3dge 的机器配置目录

`AGENTS.md` 广播「该怎么干」。本目录是进程配置：`manifest.json` 管「活在哪个域」，`rules/` 是按路径取的 how 切片。不要 `ls` 本目录当探索（ADR-0011 §2.1）。

主流 harness 自动加载的是仓库根 `AGENTS.md`，不扫这里。`k3dge check` 写死读取 `manifest.json`。`_find_workspace` 把含本目录的路径当 workspace 根。读到这里是因为已知路径，不是因为被逛到。

## 这里有什么

| 路径 | 给谁 | 干什么 |
| --- | --- | --- |
| `manifest.json` | 机器（`k3dge check` / `sync` / MCP `spec://manifest`） | 域路由：哪段 `src/` 对应哪份 `docs/specs/` 和测试。不可省。 |
| `rules/*.md` | 被 `AGENTS.md` **点名路径**读到时 | 协议切片（ADR-0010）。尤其 Rule 02。不靠浏览本目录发现。 |
| `docs.toml` | `./scripts/generate-docs.sh` | 人读文档生成配方。门禁不读。 |
| `README.md` | 已经打开本目录的人/工具 | 本文件。说明「不要把这里当成 Agent 入口」。 |

Agent 入口是仓库根 `AGENTS.md`。需要读 manifest / Rule 02 时，由那份文件给出具体路径。

目录名叫 `.agent` 是历史命名（对象曾被设想成 Agent）。不要从名字推断「Agent 会自己找到这里」。
