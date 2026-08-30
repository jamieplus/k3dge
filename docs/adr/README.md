# Architecture Decision Records (ADR)

按编号索引。每条决策独立成文件 `NNNN-<slug>.md`，新决策递增编号。

## 文档编撰规则 (Document Authoring Rules)

- 文件名 `docs/adr/NNNN-<slug>.md`，四位零填充递增且唯一；新增须在下方索引登记。
- frontmatter：`Status`（`Accepted` | `Amended by ADR-NNNN` | `Superseded by ADR-NNNN` | `Draft`）/`Date`（YYYY-MM-DD）/`Deciders`，可选 `Amends`/`Supersedes`。修订既有 ADR 时原记录 `Status` 改为 `Amended by`/`Superseded by`，新记录反向锚定。
- 三段式：`## 1. 上下文 (Context)` / `## 2. 决策 (Decision)` / `## 3. 产生后果 (Consequences)` 顺序固定。
- 语言洁净禁令：禁流水账、禁拟人/对话化表述。

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
| 0023 | Adopt ADR Authoring & Governance Protocol (Frontmatter / 3-Section / Anti-Narrative) |
| 0024 | Entry Convergence: Single Dispatch Funnel (collapse AGENTS.md routing → `k3dge protocol resolve --path`) |
