---
Status: Accepted
# Append-only after Accepted. Revise via `Amended by` / `Superseded by` below — do
# NOT rewrite this decision's prose in place, and never reuse a number (see README).
Supersedes: -
Amended-by: -
Date: 2026-08-24
Deciders: Core Maintainer
---

# ADR-0011: `.agent/` 是 harness 机器配置，不是 Agent 的发现面

> **Related**: ADR-0010（rules 切片）、ADR-0019（协议装载废弃）

## 1. 上下文 (Context)

把口头约束落到磁盘的初衷，是让 k3dge 换会话、换模型仍一致（ADR-0001 / 0011）。目录名 `.agent/`、`_find_workspace` 以它为 workspace 标记，里面同时放 `manifest.json` / `rules/` / `docs.toml`，本应让 Agent 打开这个目录就自说明。实证否决了「Agent 会自己发现这个目录」：主流 harness（Grok / Codex）自动加载的是仓库根 `AGENTS.md`，不扫 `.agent/`；Agent 列目录工具默认不显示点目录。因此「给 Agent 用的目录」若依赖被发现才起作用，它就没按设计起作用。`k3dge check` 写死 `MANIFEST_PATH = ".agent/manifest.json"` 仍成立——那是进程硬编码，不需要被逛到，对标 `.git`。

## 2. 决策 (Decision)

1. **Agent 的发现面只有 `AGENTS.md`**（自动加载）。需要 Agent 做的事必须写在（或由 §12 从）这份文件指向具体路径。禁止再设计成「Agent 会自己找到 `.agent/`」。
2. **`.agent/` 是 k3dge 进程的配置目录**，三件套职责固定：
   - `manifest.json`：机器事实源（域路由）。`k3dge check/sync` 读这个，不读 README。
   - `docs.toml`：人读文档生成配方，给 Agent 收尾用，不是门禁输入。
   - `rules/*.md`：协议切片（ADR-0010），由 AGENTS.md **点名路径**去读（尤其 Rule 02），不靠浏览目录。
3. `_find_workspace` 继续把 `.agent` 当 workspace 标记。这是进程探测，不是给 Agent 看的路标。
4. `.agent/README.md` 必须写明上面分工，避免下一任再把隐藏目录当成 Agent 入口；init 仍写出该文件（给打开它的人/工具）。AGENTS.md **不再**说「从 `.agent/README.md` 开工」。
5. 不删除 `.agent/`、不挪走 `manifest.json`。省略目录会拆掉门禁地址簿；要换路径须另开 ADR。

## 3. 产生后果 (Consequences)

- **正**：设计与实测一致；不再用「Agent 会发现隐藏目录」当自说明。
- **负**：目录名 `.agent` 仍像给人看的。改名成本高、且不是本条范围。
- **何时重开**：主流 harness 开始自动加载 `.agent/` 或显示点目录；或把 manifest 迁出隐藏路径。
