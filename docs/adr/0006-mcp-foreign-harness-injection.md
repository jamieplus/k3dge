---
Status: Accepted
Date: 2026-08-24
Deciders: Core Maintainer
---

# ADR-0006: 对外 harness 注入面与并列 harness 集成

> **Related**: ADR-0005（本地自用 / 职责切分）、ADR-0010（rules 切片）

## 1. 上下文 (Context)

k3dge 先在本仓自用（ADR-0007 自举），下一步是用 k3dge 去开发另外三套并列 harness（audit / quality / cache）而不把它们长进 `src/k3dge`。两者都涉及"k3dge 如何与外部 harness 对接"，易与"MCP 是给本仓终端用户的第二套界面"混淆。实际：MCP 是其它 Agent harness（DSH / Codex / Claude Code / OpenCode）注入 k3dge 事实、调 `check`/`sync`/`milestone` 的兼容层（ADR-0005 §2.2）；并列 harness 是挂同一份 k3dge 门禁的独立仓。

## 2. 决策 (Decision)

- **CLI**（`k3dge.cli.main`）：本仓人/脚本原生入口（shell、pre-commit、CI）。
- **MCP**（`k3dge.cli.mcp`）：对外兼容层，只委托 `engine` / `sync` / `milestone`，零漂移；消费者是外部 harness，不是第二套交互设计。仍放在 `cli` 域（都是传输，不判定）。
- **并列 harness 模型**：k3dge 是**一致性元门禁**；下列三者各是独立仓（或即将拆出的独立仓），各自挂 k3dge（`K3DGE_SOURCE` 指向本检出）：

  | Harness | 守什么 | 不守什么 |
  | --- | --- | --- |
  | **k3dge**（本仓） | 契约哈希、spec 结构、milestone 证据 | 好不好、怎么审、记不记得住 |
  | **audit** | 五轮/8 维透镜、12 列报告（ADR-0017） | 不跑 `k3dge check` 的判定 |
  | **quality** | 圈复杂度、重复、类型（ruff/mypy 等） | 不替代契约闸 |
  | **cache** | 提高 Agent 命中率的检索/缓存 | 不进 engine、不做门禁出口码 |

  - 禁止把 audit/quality/cache 做成 k3dge 的第五、六、七域。审计种子是 `docs/protocols/audit_default.md` / `verify_default.md`；透镜与 `check-report` 在 **k3dit**。
  - 新仓 init 之后与自举 k3dge 同一套 Agent 协议（门控、`AGENTS.md` §12 文档/里程碑触发、MCP 只走固定剧本）；`k3dge check` 在该仓 pre-commit 硬拦。脚手架幂等不覆盖已有 `AGENTS.md`/`scripts/init.sh`——协议升级要再同步这两份，不是 init 行为回退。
- **透镜审计不在 `src/k3dge`**（ADR-0005 §2.6）：MCP prompt 只指路，不在桥里演进规程。
   - **信任边界**：本机 stdio 信任边界 = 调起该 MCP 的 OS 用户（S-13）；网络化后再重开鉴权。
   - **`pipeline.toml` 是第三根门禁支柱**：并列 harness 的调用编排只写在 `.agent/pipeline.toml` 的 `[peers]` / `[pipelines]`（`manual` / `mcp` / `cli` / `skip` 传输与 fallback）。旧键 `[harnesses]` / `[hooks]` 必须 `PIPELINE_SCHEMA_INVALID`，不得当空 `peers` 放行。`k3dge check` 只验 schema / 符号引用 / 协议文件存在，**不连 MCP、不跑 CLI**；编排执行失败走 fallback / skip，不改变一致性判定（T-01，见 `docs/reviews/README.md` 有意留表）。
   - **harness 身份不混用**：其它并列 harness 自定入口，禁止共用 `k3dge_*` 工具名装成一个进程。

## 3. 产生后果 (Consequences)

- **正**：外部 harness 接 k3dge 只配 MCP server，不要在那些工具里再写一份 hash 逻辑；层仍干净，质量闸不进本闸。
- **负**：多仓要记得 `K3DGE_SOURCE`；k3dge 契约一变，子仓都要 `k3dge sync`/`check`。
- **何时重开**：主流 harness 开始默认扫描 `.agent/` 或显示点目录（见 ADR-0011 发现面结论）。
