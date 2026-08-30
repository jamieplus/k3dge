---
Status: Accepted
Date: 2026-08-24
Deciders: Core Maintainer
---

# ADR 0014: `.agent/` 是 harness 机器配置，不是 Agent 的发现面

- **Amends**: ADR 0013（保留三件套清单；撤回「Agent 打开这个目录即自说明」）

## 1. 上下文 (Context)
ADR 0013 把 `.agent/` 写成 Agent 自说明根：换会话打开这个目录就知道怎么治理。实证否决了这条。

制作 k3dge 的 Agent 在多轮审计、对齐、改门禁时**没有第一时间发现 `.agent/`**。用户指出后才对上。原因是机制，不是疏忽：

1. 主流 harness（Grok / Codex）自动加载的是仓库根 `AGENTS.md`，不扫 `.agent/`。
2. Agent 列目录工具默认**不显示点目录**。名为 `.agent` 的文件夹对「逛仓库」不可见。
3. 因此「给 Agent 用的目录」若依赖被发现才起作用，它就没按设计起作用。

`k3dge check` 写死 `MANIFEST_PATH = ".agent/manifest.json"` 仍然成立：那是进程硬编码，不需要被逛到，对标 `.git`。把「机器知道这条路径」说成「Agent 会打开这个目录」是把两件事混了。

## 2. 决策 (Decision)

1. **Agent 的发现面只有 `AGENTS.md`**（自动加载）。需要 Agent 做的事必须写在（或由 §12 从）这份文件指向具体路径。禁止再设计成「Agent 会自己找到 `.agent/`」。
2. **`.agent/` 是 k3dge 进程的配置目录**。`manifest.json` 给 check/sync；`docs.toml` 给 generate-docs；`rules/` 仍是协议切片（ADR 0012），由 AGENTS.md **点名路径**去读（尤其 Rule 02），不靠浏览目录。
3. `_find_workspace` 继续把 `.agent` 当 workspace 标记。这是进程探测，不是给 Agent 看的路标。
4. `.agent/README.md` 必须写明上面分工，避免下一任再把隐藏目录当成 Agent 入口。init 仍写出该文件（给打开它的人/工具），但 AGENTS.md **不再**说「从 `.agent/README.md` 开工」。
5. 不删除 `.agent/`、不挪走 `manifest.json`。省略目录会拆掉门禁地址簿。要换路径须另开 ADR。

### 2.1 怎么干 / 在哪干（2026-08-24 措辞）

- `AGENTS.md` **广播**：harness 启动注入，Agent 不必去「发现」它。管「该怎么干」。
- `.agent/manifest.json` **按路径直取**：AGENTS.md 写死这条路径。管「活在哪个域」（where）。
- `.agent/rules/*.md` 也是按路径直取的 **how 切片**（尤其 02），不是第二份 where。冲突仍以 AGENTS.md 为准（ADR 0012）。
- 点前缀的**现行用法**：不要当普通目录去逛。真正读到它是因为 AGENTS.md 给了路径，不是因为 `ls` 看见了。点前缀的**来历**仍是旧名（对象曾被设想成 Agent + 学 `.git`）；0014 没有「为了防逛才改成点目录」这一步，目录本来就叫这个。

## 3. 产生后果 (Consequences)

- **正**：设计与实测一致；不再用「Agent 会发现隐藏目录」当自说明。
- **负**：目录名 `.agent` 仍像给人看的。改名成本高、且不是本条范围。
- **何时重开**：主流 harness 开始自动加载 `.agent/` 或显示点目录；或把 manifest 迁出隐藏路径。
