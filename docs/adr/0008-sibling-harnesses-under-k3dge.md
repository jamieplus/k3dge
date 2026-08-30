---
Status: Accepted
Date: 2026-08-24
Deciders: Core Maintainer
---

# ADR 0008: 用自举级 k3dge 开发并列 harness（audit / quality / cache）

## 1. 上下文 (Context)
k3dge 已能作为本仓硬门禁（ADR 0007 自举）。下一步不是发行 PyPI，而是 **用 k3dge 去开发另外三套 harness**。它们必须和 k3dge 并联，不能长进 `src/k3dge`（质量不进本闸见 memo 2026-08-21；审计独立见 ADR 0005 §2.6）。

## 2. 决策 (Decision)

k3dge 是 **一致性元门禁**。下列三者各是独立仓（或即将拆出的独立仓），各自挂 k3dge（`K3DGE_SOURCE` 指向本检出）：

| Harness | 守什么 | 不守什么 |
| --- | --- | --- |
| **k3dge**（本仓） | 契约哈希、spec 结构、milestone 证据 | 好不好、怎么审、记不记得住 |
| **audit** | 五轮/8 维透镜、9 列报告 | 不跑 `k3dge check` 的判定 |
| **quality** | 圈复杂度、重复、类型（ruff/mypy 等） | 不替代契约闸 |
| **cache** | 提高 Agent 命中率的检索/缓存（规格、ADR、失败分支） | 不进 engine、不做门禁出口码 |

- 每个 harness 自己的 `.agent/manifest.json`、`docs/specs/`、pre-commit 里挂 `k3dge check`。
- **禁止**把 audit/quality/cache 做成 k3dge 的第五、六、七域。
- 本仓 `harnesses/audit/` 是自举期的种子；audit 仓开工时把 PROTOCOL 与 CLI 迁到 **k3dit**，本仓只留指针。
- **新仓 init 之后与自举 k3dge 同一套 Agent 协议**：写入的 `AGENTS.md` 即生产级模板（门控、§12 文档/里程碑触发、MCP 只走固定剧本）。`k3dge check` 在该仓 pre-commit 硬拦。脚手架幂等不覆盖已有 `AGENTS.md`/`scripts/init.sh`——协议升级要再同步这两份，不是 init 行为回退。
- 给 Codex / Claude Code / OpenCode / DSH 用时：k3dge 走 MCP 注入（ADR 0006）；其它 harness 各自决定入口（CLI / 另一个 MCP），不要共用 k3dge 的工具名假装成一个进程。

## 3. 产生后果 (Consequences)
- **正**：自举范围从「开发 k3dge」扩成「用 k3dge 开发工具链」；层仍然干净。
- **负**：三仓 + 本仓要记得 `K3DGE_SOURCE`；k3dge 契约一变，三个子仓都要 `k3dge sync`/`check`。
- **下一步（未做）**：建三个工作区并 `K3DGE_SOURCE=<k3dge> k3dge-init`。未建仓前不要在本仓 `src/` 里预埋它们的实现。
