# Architecture Decision Records (ADR)

本目录收录 k3dge 的**架构决策记录（Architecture Decision Record, ADR）**：每一条固化一次已确定的、具全局约束力的架构取舍——只记结论与不可变的理由，不记过程与闲聊。

- **用途**：把"为什么这样设计"沉淀下来，使后续改动能追溯到决策与权衡，而非凭记忆重审。
- **组织**：按四位零填充序号 `NNNN` 递增、全仓唯一；每条独立成文件 `NNNN-<slug>.md`，并在下方索引表登记编号与标题。
- **怎么写**：新增 / 修订 ADR 的写法与机检契约见本页 `## 文档编撰规则` 段（取代早先 `Status ∈ {Proposed, Accepted, Deprecated, Superseded}` 的约定，存量 ADR 同样适用，无祖父豁免）。
- **怎么读**：从索引表按主题检索；被他处引用的 ADR 编号即契约锁定，不得改写或重用。

## 文档编撰规则 (Document Authoring Rules)

> **事实源**：`k3dge` 仅验"文件存在 / 注册一致"（`k3dge check`）；本文件载 ADR 的机检契约，叙事质量由评审保证。
> 本协议取代此前 `Status ∈ {Proposed, Accepted, Deprecated, Superseded}` 的约定；自采用之日起**全部** ADR（含存量）须符合本协议 frontmatter 与三段式，无祖父豁免。

### 交付

`docs/adr/NNNN-<slug>.md`，`NNNN` 为四位零填充序号，全仓唯一。每次增 / 删 / 改 ADR，必须在 `docs/adr/README.md` 索引表同步登记（编号与标题对应）。

### Frontmatter 契约

文件头部以 YAML frontmatter 声明：

- `Status`: `Accepted` | `Amended by ADR-NNNN` | `Superseded by ADR-NNNN` | `Draft`
- `Date`: `YYYY-MM-DD`
- `Deciders`: 决策人或核心维护组
- `Amends`: 可选，指向被修订的 `ADR-NNNN`
- `Supersedes`: 可选，指向被废弃的 `ADR-NNNN`

修订既有 ADR 时，原记录 `Status` 改为 `Amended by ADR-NNNN` 或 `Superseded by ADR-NNNN`，新记录以 `Amends` / `Supersedes` 反向锚定。

### 三段式章节

每条 ADR 必须含且仅含以下三个一级章节（顺序固定）：

- `## 1. 上下文 (Context)`：仅陈述客观约束与痛点；严禁对话记录、时间线、人称叙事。
- `## 2. 决策 (Decision)`：仅陈述系统全局不变量、架构契约与显式不做的事。
- `## 3. 产生后果 (Consequences)`：分述正面收益、负面权衡与明确的「何时重开判据」。

### Constraints

L2 入场券须逐条确认：

- 文件名满足 `^\d{4}-[\w-]+\.md$` 且序号在 `docs/adr/` 内唯一（无撞号，参考 `INC-20260827` 事故）
- 含 frontmatter `Status`（上述枚举）与 `Date`（YYYY-MM-DD）
- 含 `## 1. 上下文 (Context)` / `## 2. 决策 (Decision)` / `## 3. 产生后果 (Consequences)` 三节
- 不得删除或改写已被他处引用的 ADR 编号（引用即契约锁定）
- 语言洁净禁令（Anti-Narrative Lint）：严禁流水账（如「XX 分钟后」「讨论后决定」）与拟人 / 对话化表述（如「用户指出」「制作 Agent 发现」）

## 索引

| ADR | Title |
| --- | --- |
| 0001 | k3dge Architecture Baseline |
| 0002 | Docs Reference vs Architecture Semantics |
| 0003 | Tasks / Backlog / Merge |
| 0004 | Milestone Lifecycle Governance |
| 0005 | Local-First and Layer Cuts |
| 0006 | MCP Foreign Harness Injection |
| 0007 | Self-Hosting Bootstrap |
| 0008 | Sibling Harnesses Under k3dge |
| 0009 | Unsolicited Doc Triggers |
| 0010 | Agent Aligns to Settled Design |
| 0011 | Purpose: Reduce Agent Failure Modes |
| 0012 | Agent Rules Are Protocol Slices |
| 0013 | Agent Dir Is Self-Description |
| 0014 | Agent Dir Is Harness Config |
| 0015 | Assertion Evidence Chain |
| 0016 | Living Doc Relocation |
| 0017 | Version and Changelog |
| 0018 | Template Drift in Engine |
| 0019 | Downstream-First Domain and Protocol Pack |
| 0020 | Pattern Absorption Protocol |
| 0021 | Audit Report Schema v2 (12 columns) |
| 0022 | Protocol Dispatch: Path-Routed Deterministic Load (Workshop/Helmet/Passphrase) |
