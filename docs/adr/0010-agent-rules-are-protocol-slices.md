---
Status: Accepted
Supersedes: -
Amended-by: -
Landed-by: .agent/rules/07-audit.md
Date: 2026-08-24
Deciders: Core Maintainer
Note: 修订痕迹见 git 历史。
---

# ADR-0010: `AGENTS.md` 是唯一发现面；`.agent/` 是进程配置（rules 是其协议切片）

> **Related**: ADR-0018（协议装载废弃）、ADR-0018（成对物动前须有 ADR）

## 1. 上下文 (Context)

- `AGENTS.md` 是主流 harness（Grok / Codex / Claude Code / Cursor）自动加载的面；`.agent/` 是目录名兼 `_find_workspace` 的 workspace 标记，内含 `manifest.json` / `rules/` / `docs.toml`。
- 实证否决「Agent 会自己发现 `.agent/`」：harness 只加载仓库根 `AGENTS.md`，不扫点目录；列目录工具默认不显示点目录。依赖"被发现"才起作用的目录＝没按设计起作用。
- `.agent/rules/*.md` 没有自动加载消费者；与 `AGENTS.md` 重叠时若无「谁赢」会漂。
- 成对物（`AGENTS.md` ↔ `.agent/rules/`）动前必须有 ADR（ADR-0018）；本条是那张卡。
- `k3dge check` 写死 `.agent/manifest.json`——那是进程硬编码，不需被逛到（对标 `.git`）。

## 2. 决策 (Decision)

1. **Agent 的发现面只有 `AGENTS.md`**（自动加载）。需要 Agent 做的事必须写在（或由 §12 从）这份文件指向具体路径；**禁止**再设计成「Agent 会自己找到 `.agent/`」。
2. **活协议只有一份**：仓库根 `AGENTS.md`（§12 触发表在此）。`k3dge check` 不读 rules，也不该读。
3. **`.agent/` 是 k3dge 进程的配置目录**，三件套职责固定：
   - `manifest.json`：机器事实源（域路由）；`k3dge check/sync` 读这个，不读 README。
   - `docs.toml`：人读文档生成配方，给 Agent 收尾用，不是门禁输入。
   - `rules/*.md`：**协议切片**——给只扫 `.agent/rules/` 的工具，以及 Rule 02 这份不进门禁的简化规程（质量闸属合并审计模块，ADR-0025）；由 `AGENTS.md` **点名路径**去读，不靠浏览。不是第二套指令。
4. **冲突时 `AGENTS.md` 赢**；同一任务改 rule 文件对齐，禁止只改一边。
5. **init 必须写出完整 `00`–`10`**（内容与 `src/k3dge/templates/assets/rules/` 及本仓 `.agent/rules/` 相同）；禁止空标题；`_write_if_missing` 仍不覆盖已有文件。
6. **Agent 何时读 02**：用户要求简化 / 删死代码 / 拆冗余，或里程碑 C2 勾了深层嵌套 → 先按 02 举证再动（写入 §12）。00/01/03 不要求再读。
7. **`_find_workspace` 继续把 `.agent` 当 workspace 标记**（进程探测，不是给 Agent 看的路标）。
8. `.agent/README.md` 写明上面分工；`AGENTS.md` **不再**说「从 `.agent/README.md` 开工」。
9. 不删 `.agent/`、不挪 `manifest.json`；要换路径须另开 ADR。

## 3. 产生后果 (Consequences)

- **正**：设计↔实测一致；协议单一；成对物有据；init 后 Rule 02 完整、overview 指针不断。
- **负**：`AGENTS.md` 与各份 rule 仍可能手工漂 → 用 `test_template_sync` 锁「`assets/rules` ↔ `.agent/rules`」与「`assets/agents.md` ↔ `AGENTS.md`」。
- **何时重开**：主流 harness 开始自动加载 `.agent/` 或显示点目录 → 再考虑把 §12 表下沉到 rules、`AGENTS.md` 改成索引；或把 manifest 迁出隐藏路径。在那之前不要把 `AGENTS.md` 拆空。
