# Obsolete ADRs

不再活跃的决策记录归档于此，由 `adr_gate.reconcile_supersedes` 闸自动移入：

- **Superseded**：被新 ADR 替换（自动改 frontmatter + 移入）
- **Rejected**：提议后被否决，从未生效（直接移入）

规则：
- **不进门禁**：`adr_gate` 只扫 `docs/adr/*.md`（不递归子目录），本目录内文件自动跳过。
- **不改名**：文件名保留原编号，git 历史可追溯。
- **只读**：归档后不再修改；如需澄清，在新 ADR 中说明。

## 永久退役号（账本）

**Baseline**：2026-09-19（commit `f749e27`）。此前的**物理删除不追**（存量不重编号——重编号会打断全仓与下游仓继承的引用）；此后退役一律是本目录下的**真文件**（带 `merged-into` / `superseded-by` 去向），不再物理删除。

分配规则：下一号 = max over（`docs/adr/*.md` ∪ `docs/adr/obsolete/*.md` ∪ 下表）+ 1。只增不减 ⇒ 退役号永不再发出。机验码：`ADR_NUMBER_REUSE`（新 ADR 用了下表或 `obsolete/` 里的号）、`ADR_REF_RETIRED`（正文引用退役号 ⇒ 提示去向）。

| 号 | 曾是 | 退役方式 | 去向 | 删除 commit |
| --- | --- | --- | --- | --- |
| 0002 | docs-reference-vs-architecture-semantics | 合并 | ADR-0018 | `45fae8b` |
| 0003 | tasks-backlog-merge | 合并 | ADR-0018 §2.12 | `c15e26e` |
| 0007 | self-hosting-bootstrap | 合并 | ADR-0009 | `5d8392d` |
| 0011 | agent-dir-is-harness-config | 合并 | ADR-0010 | `9c58329` |
| 0013 | version-and-changelog（另有 agent-dir-is-self-description 于 `183c9ec` 改名腾号） | 合并 | ADR-0004 §2.3 | `5d8392d` |
| 0014 | template-drift-in-engine（另有 agent-dir-is-harness-config 于 `183c9ec` 改名腾号） | 合并 | ADR-0001 §2 第 7 条 | `84a3242` |
| 0015 | downstream-first-domain-and-protocol-pack | 合并 | ADR-0005 §2.8 | `c15e26e` |
| 0016 | pattern-absorption-protocol（另有 living-doc-relocation 于 `183c9ec` 改名腾号） | 合并 | ADR-0009 | `5d8392d` |
| 0019 | protocol-load-proof-abandoned | 合并 | ADR-0018 §2.11 | `c15e26e` |
| 0020 | harness-responsibility-split | 合并 | ADR-0005 §2.7 | `0fc2d3a` |
| 0021 | doc-audit-post-check-non-blocking | 合并 | ADR-0022 §2.2 | `01ec53a` |
| 0024 | audit-evidence-exchange-topology | 合并 | ADR-0025 §2.9 | `076f993` |
| 0027 | hall-harness-topology | 改名腾号 | ADR-0025（同文重编号） | `72b55ec` |

### 曾被复用的号（存量不追，仅记账）

Baseline 之前「物理删除 + 本目录最大号 +1」这条组合把 6 个号发出过两次；它们**现役且不迁号**（迁号＝打断引用）。此后由上表 + `ADR_NUMBER_REUSE` 闸拦住。

| 号 | 旧占用（已退役） | 现役 |
| --- | --- | --- |
| 0008 | sibling-harnesses-under-k3dge | unsolicited-doc-triggers |
| 0009 | unsolicited-doc-triggers（原 0009，改名腾号） | purpose-reduce-agent-failure-modes |
| 0010 | agent-aligns-to-settled-design | agent-rules-are-protocol-slices |
| 0022 | protocol-dispatch-path-routed-load | task-maps-to-audit-report |
| 0023 | doc-readme-anchor-governance（原 0023，`183c9ec` 删） / meta-rule-delivery（`4fe735c` 删） | low-authority-archive-tier |
| 0026 | audit-evidence-exchange-topology（→0024→ADR-0025 §2.9） / mcp-workspace-root-confinement（→ADR-0006） | projection-contract |

历史最大号 = 0027 ⇒ **下一个安全号 = 0028**。
