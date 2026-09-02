# Architecture — 系统全貌（System Overview）

> 人写常驻 + `k3dge sync` 聚合校验。域级契约在 `docs/specs/<domain>/spec.md`，本文件只讲**域间关系与全局不变量**。
> 本文档遵循 **Diátaxis**（`guides`=教程/操作指南、`generated`=Reference 自动生成、`architecture` 本文件=`解释`）与 **C4-C1** 上下文视图。

## 0. C4-C1 系统上下文

```mermaid
C4Context
    title k3dge 在 Vibe Coding 链路中的位置
    Person(dev, "开发者/PM", "提自然语言需求")
    System(k3dge, "k3dge Harness", "一致性元门禁（自举）")
    System_Ext(auditH, "audit harness", "五轮透镜")
    System_Ext(qualityH, "quality harness", "复杂度/类型")
    System_Ext(cacheH, "cache harness", "命中率/检索")
    System_Ext(agent, "外部 Agent Harness<br/>DSH / Codex / Claude Code / OpenCode", "经 MCP 注入 k3dge，不私有重实现门禁")
    System_Ext(git, "Git", "pre-commit/CI 拦截点")
    Rel(dev, k3dge, "用 k3dge 开发并列 harness", "K3DGE_SOURCE")
    Rel(dev, auditH, "开发", "")
    Rel(dev, qualityH, "开发", "")
    Rel(dev, cacheH, "开发", "")
    Rel(agent, k3dge, "MCP stdio：check/sync/spec", "零漂移委托")
    Rel(k3dge, git, "阻断或放行", "exit code")
    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

## 1. 域地图（事实源：`.agent/manifest.json`）

| Domain | Source | Spec | Description |
| --- | --- | --- | --- |
| cli | `src/k3dge/cli` | `docs/specs/cli/spec.md` | 本仓终端/CI + 对外 harness 的 MCP 注入面 |
| engine | `src/k3dge/engine` | `docs/specs/engine/spec.md` | 门禁核心：diff / manifest / spec_schema / contract / evaluator |
| sync | `src/k3dge/sync` | `docs/specs/sync/spec.md` | spec 接口块与契约哈希回写；`docs/generated/` 机器文档（Diátaxis Reference） |
| templates | `src/k3dge/templates` | `docs/specs/templates/spec.md` | 脚手架生成器（k3dge-init.sh） |

## 2. 依赖方向

```mermaid
graph TD
    cli --> engine
    cli --> sync
    cli --> templates
    sync --> engine
    templates
```

* `engine` 为门禁判定与生命周期治理核心，不依赖 `cli/sync/templates`。
* `sync` 依赖 `engine.contract`。
* `cli` 分两路：`main` 本仓；`mcp` 外部 harness 注入（ADR-0006）。
* `templates` 仅 `scaffolding`；`cli→templates` 仅 `init` 装配（ADR-0014）。

## 3. 数据流（提交门禁）

```mermaid
flowchart LR
    A[git diff<br>base...HEAD + porcelain] --> B[manifest 域路由]
    B --> C[spec 结构校验]
    C --> D[contract 哈希比对]
    D --> E[GateReport]
    E -->|pass| F[放行]
    E -->|drift| G[k3dge sync 重算]
    G --> E
```

## 4. 全局不变量

* `GateReport.passed ⇔ violations.is_empty` —— 门禁语义基线（ADR-0001）
* `Contract Hash` 锚定公开签名；改 `src/<domain>/` 公开接口须 `k3dge sync` 回写哈希（双向绑定）—— ADR-0001
* `TEMPLATE_DRIFT` 仅自举、不 import `templates/` —— ADR-0014（`pairs.py:1`）
* spec 是契约、ADR 是决策事实源：操作层以指针引用 ADR 编号，不复写其正文 —— ADR-0001 / docs/adr/README.md
* 文档类型合同：`docs/<type>/AUTHORING.md`（软）+ `docs/<type>/.schema.json`（硬闸）；寻址公式在 `AGENTS.md`；薄索引 `docs/generated/docs-index.json` —— ADR-0018 / ADR-0019
* 协议仅 audit 两层 fallback，配置在 `.agent/pipeline.toml`，由 `PIPELINE_PROTOCOL_NOT_FOUND` 校验 —— ADR-0019
* MCP 为外部 harness 调用 engine 事实/工具的唯一面，禁止私有重实现门禁 —— ADR-0006

## 5. 组件解耦（通用模板）

```mermaid
C4Context
    title Harness 隔离（Agent 编排 + k3dge sidecar + 并列外部 harness）
    System(agent, "Agent Harness (DSH/Codex/Claude/OpenCode)", "编排者：读 pipeline，调 k3dge 与外部 harness 的 MCP")
    System_Ext(k3dge, "k3dge (sidecar MCP)", "一致性门禁 / 契约事实")
    System_Ext(audit, "Audit Harness (k3dit)", "透镜（外部 MCP，不进 engine）")
    System_Ext(cache, "Cache Harness", "记忆/检索（外部 MCP）")
    System_Ext(quality, "Quality Harness", "度量/证伪（外部 MCP）")
    Rel(agent, k3dge, "MCP stdio", "check/sync/status/incident — 零漂移委托")
    Rel(agent, audit, "MCP", "透镜不进 engine")
    Rel(agent, cache, "MCP", "Observer 异步")
    Rel(agent, quality, "MCP", "verify")
    UpdateLayoutConfig($c4ShapeInRow="4", $c4BoundaryInRow="1")
```

## 6. Milestone 状态机（通用）

```mermaid
stateDiagram-v2
    [*] --> DRAFT
    DRAFT --> ALIGNED: milestone align (Full Matrix, 无人问)
    ALIGNED --> AUDIT_SUGGESTED: 量化触发(账齐/C2≥5/体积≥8)
    AUDIT_SUGGESTED --> DRAFT: 要不要审? N（继续干活；无倒计时）
    AUDIT_SUGGESTED --> AUDITING: k3dge milestone audit
    AUDITING --> AUDITING: audit+quality 待修>0 + agent 修（倒计时默认修；重审各报告）
    AUDITING --> AUDITING: 位置钉 k3dit:pending <ID>（check/status 报 pending=N）
    AUDITING --> ESCALATED: verify 连续 >3 次未闭环 → 转人工
    AUDITING --> SEAL_READY: audit 与 quality 两份报告均 待修=0（审计闭环=真界限）
    SEAL_READY --> DRAFT: 要不要封? N（里程碑继续挂着）
    SEAL_READY --> SEALED: k3dge milestone seal（align→归档+版本+指针）
    SEALED --> [*]: 收摊=上下文压缩(closure.md → 设计文档 → 提交)
```

> **两问拆开**：封板没有尺子（全 done/硬闸绿/零 task 都能说"可封"），界限是**审计环收口 = audit + quality 两份 12 列报告都到 待修=0**。自动触发只服务「要不要审」，「要不要封」只在闭环后出现一次。未审计调 `seal` → `audit_needed`。发现用 `k3dit:pending <ID>` 钉在 `位置` 处（仅指针，处置仍以报告+tasks 为准），`check`/`status` 报 `pending_findings`。外来审计源经 `k3dge milestone audit-submit`(或 MCP `k3dge_submit_audit_report`) 落盘即计入闭环。架构/`overview.md` 更新**不是钩子**，在 closure 里做。详见 ADR-0004 §2.1.4–§2.1.8。

## 7. 审计→封板时序（通用模板）

```mermaid
sequenceDiagram
    participant Agent as Agent Harness (DSH/Codex/Claude/OpenCode)
    participant K3 as k3dge (sidecar MCP)
    participant Audit as Audit Harness (k3dit, ext MCP)
    participant Quality as Quality Harness (k3lity, ext MCP)
    Agent->>K3: read .agent/pipeline.toml (on_seal_enter / on_pre_seal)
    Agent->>K3: k3dge check / status（硬闸绿）
    K3-->>Agent: [NEXT] audit_suggested + reasons（量化触发；非建议封）
    Agent->>K3: milestone align（Full Matrix，无人问）
    K3-->>Agent: 问「要审吗？」(无倒计时；N=继续干活)
    Agent->>K3: milestone audit <id>
    Agent->>Audit: k3dit.actions.audit（mcp→cli→manual；fallback=default 自审须转人工）
    Agent->>Quality: k3lity.actions.quality（mcp→cli→manual；人填不造假分）
    Note over Agent,Audit: 外来审计源：人贴报告 → k3dge_submit_audit_report 落盘(--kind audit|quality)
    Audit-->>Agent: 审计 12 列报告（含 待修/有意留/已修）+ 位置钉 k3dit:pending
    Quality-->>Agent: 质量 12 列报告（k3dge:kind: quality）
    Agent->>Agent: 任一报告 待修>0? 问「agent 修？」(倒计时默认修) → 重审各报告；>3 次 → escalated 转人工
    K3-->>Agent: [NEXT] seal_ready（两份报告 待修=0，唯一界限达成）
    Agent->>K3: milestone seal <id>
    K3-->>Agent: 问「封板？」(无倒计时；否=不封，里程碑挂着)
    K3->>K3: align→归档+版本+指针；写 *-closure.md 收摊清单（上下文压缩+设计文档由人/agent 补齐）
```

> 命令结果末尾统一附 `[NEXT] state=… milestone=…` 一行提示（MCP 同构 JSON `next` 字段），只给合法下一步、不替人决定；优先级 `pending_findings > seal_ready > audit_suggested`，状态与 reasons 的唯一来源在 `engine/nextstep.STATE_OPTIONS` + `engine/audit_trigger.py`，与本节同一张状态机。新建 `src/` 域给 `new_domain`（是否算持久设计、写得对不对仍归 k3dit/人）；`overview.md` 更新已移出钩子、进 closure。
>
> **T-01 边界（doc-audit，ADR-0021）**：`check` 恒静态、不跑透镜。docs 改动时 `check` 绿后给 `[NEXT] doc_audit`，由 `k3dge doc-audit`（**之后**、**非阻断**）出 k3dit 报告 + 建带 `Milestone` 的 task；task 进 backlog 由封板「全 done」闸兜底。ADR 冲突/覆盖只在里程碑审计，不进每次 commit。

## 8. 决策与有意留索引

已定案决策：寻址用 `k3dge doc list --type adr`；主题与旧号映射见 [`docs/adr/README.md`](../adr/README.md)。

有意留（活文档常驻表）：[`docs/reviews/LEFTOVERS.md`](../reviews/LEFTOVERS.md) 为唯一事实源。
