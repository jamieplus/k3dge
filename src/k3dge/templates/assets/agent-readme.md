# `.agent/` — k3dge 的机器配置目录

`AGENTS.md` 广播「该怎么干」。本目录是进程配置：`manifest.json` 管「活在哪个域」，`rules/` 是按路径取的 how 切片。不要 `ls` 本目录当探索（ADR-0010 §2.1）。

主流 harness 自动加载的是仓库根 `AGENTS.md`，不扫这里。`k3dge check` 写死读取 `manifest.json`。`_find_workspace` 把含本目录的路径当 workspace 根。读到这里是因为已知路径，不是因为被逛到。

## 这里有什么

| 路径 | 给谁 | 干什么 |
| --- | --- | --- |
| `.agent/manifest.json` | 机器（`k3dge check` / `sync` / MCP `spec://manifest`） | 域路由：哪段 `src/` 对应哪份 `docs/specs/` 和测试。不可省。 |
| `.agent/rules/*.md` | 被 `AGENTS.md` **点名路径**读到时 | 协议切片（ADR-0010）。例如「要求简化」时点名的 `.agent/rules/02-simplification.md`。不靠浏览本目录发现。 |
| `.agent/docs.toml` | `./scripts/generate-docs.sh`；封板闸 `guides_filled` 等消费方 | 人读文档生成配方，**「应交付文档清单」的唯一源**（消费方一律从此派生；`k3dge check` 本身不读它）。 |
| `.agent/README.md` | 已经打开本目录的人/工具 | 本文件。说明「不要把这里当成 Agent 入口」。 |

Agent 入口是仓库根 `AGENTS.md`。表里一律写**仓根相对全路径**（本目录没有 `.schema.json`，坐标写裸名就会
在别的窗里判成悬空）；需要某个 Rule 时，由点名它的那份文件给出完整路径，不让人靠浏览目录猜。

目录名叫 `.agent` 是历史命名（对象曾被设想成 Agent）。不要从名字推断「Agent 会自己找到这里」。
