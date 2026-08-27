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
* `cli` 分两路：`main` 本仓；`mcp` 外部 harness 注入（ADR 0006）。
* `templates` 仅 `scaffolding`；`cli→templates` 仅 `init` 装配（ADR 0018）。

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

* `GateReport.passed ⇔ violations.is_empty`
* `Contract Hash` 锚定公开签名，`TEMPLATE_DRIFT` 仅自举（`pairs.py:1`）

## 5. 组件解耦（通用模板）

```mermaid
C4Context
    title Harness 隔离（示例：k3dge 元门禁 + 3 并列）
    System(meta, "Meta Harness", "一致性门禁")
    System_Ext(audit, "Audit Harness", "透镜")
    System_Ext(cache, "Cache Harness", "记忆/检索")
    System_Ext(quality, "Quality Harness", "度量/证伪")
    Rel(meta, audit, "MCP/文件", "透镜不进 engine")
    Rel(meta, cache, "MCP", "Observer 异步")
    Rel(meta, quality, "MCP", "verify")
    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

## 6. Milestone 状态机（通用）

```mermaid
stateDiagram-v2
    [*] --> DRAFT
    DRAFT --> ALIGNED: milestone align
    ALIGNED --> AUDITING: HUMAN_CHECKPOINT y
    ALIGNED --> SEALED: N/60s timeout
    AUDITING --> AUDITED: 5-Pass 闭环
    AUDITED --> SEALED: milestone seal
    SEALED --> [*]
```

## 7. 对齐协作时序（通用模板）

```mermaid
sequenceDiagram
    participant Agent
    participant Meta as Meta Harness
    participant Quality as Quality Harness
    participant Audit as Audit Harness
    participant Cache as Cache Harness
    Agent->>Meta: milestone align
    Meta->>Quality: verify
    Quality-->>Meta: VERIFIED
    Meta->>Audit: run-audit (5-Pass)
    Audit-->>Meta: 9 列报告
    Meta->>Cache: inject_summary
    Cache-->>Meta: HARNESS_SKIP/OK
    Meta-->>Agent: HUMAN_CHECKPOINT y/N
    Agent->>Meta: milestone seal
```

## 8. 决策与有意留索引

* 已定案决策：`docs/adr/README.md`（按编号索引）
* 有意留：`docs/reviews/SUMMARY.md` 顶部常驻表为唯一事实源（历史 `overview.md §5.1` 已迁移至此，此处不再维护）
