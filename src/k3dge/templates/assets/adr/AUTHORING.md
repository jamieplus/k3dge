# Authoring

Copy `_template.md`. Soft rules (k3dit may judge text quality; k3dge does not):

- Context: constraints only — no chat log, no timeline, no "the user said".
- Decision: invariants and explicit non-goals.
- Consequences: upside, downside, reopen criterion.
- Wrong: "Twenty minutes later we decided…" / "the agent found…". Right: name the constraint and the choice.

Do not judge whether the decision is a *good* idea (soft; value window of the audit module). The audit role may flag two Accepted Decision sections that directly negate each other.

## 先并入，后新建 (merge-before-new)

**新建前先找同类 ADR——一类问题一条。** 很多决策描述的是**同一类问题**；散在多篇里就退化成一族散文，谁也读不全。

- 能扩写现有 ADR（就地增补 / `Amended by`）的，**不新开**。
- 只有确属**新决策类**（现有 ADR 都不覆盖）才 copy `_template.md`。
- 判断"同类"看**不变量与所有权**，不看措辞；同一条不变量被两篇各写一半＝应并。
- 合并不降清晰：宿主 ADR 用子节收编，被并者**移入 `obsolete/`** 并写清去向（`merged-into`），全仓指针重指；号随之永久退役（见「编号分配」）。

## 人读优先 (readability)

软规则，k3dit 文审按此判（结构另有 `.schema.json` 硬闸）：

- **决策先行**：每节/子节第一句写规则本身；理由、边界、实现随后。
- **一行一点**：一条 bullet 只讲一件事，过长拆子项；行宽目标 ≤ ~100 字，长机制拆编号步骤。
- **细节下沉**：函数名 / 文件路径 / 命令序列 / 内部状态机 → `docs/specs/` 或 task；ADR 只留不变量、契约与权衡（复述实现＝第二源）。
- **引用放句末**：`见 ADR-XXXX §Y` 收在句尾，不打断主句；同段不重复引同一处。
- **少叠括号**：括号不嵌套；加粗只标规则关键词，不标整句。
- **标题用名词短语**：不堆斜杠（「人工入口 / Checklist / loop」拆节或取中心词）。
- **语言**：中文为主；代码标识符用行内 `code`，不把英文术语串当句法。
- **缘起回指（PURPOSE）**：重大透镜/规则修订，在 `Decision` 里写驱动它的 pattern/缘由（一条即可），使决策可追溯到动机；并入本惯例，不新开机制。

## 术语（canonical terms）

同一概念只用一个词；改词不改义，语义变更走 ADR。

| 概念 | 用 | 不用 |
| --- | --- | --- |
| 账本（ledger） | 账本 | 台账 |
| 消费仓（被审仓） | 消费仓 | 市民、被审仓 |
| 判读窗（群）/ 判读席 | 判读窗、判读席 | 判断窗、判断席 |
| 钉（pin） | 钉；动作＝收钉，产物＝收成 | 标记、指针（pin 义） |
| Hall（大厅） | Hall；首现注"大厅" | 大厅（除场地比喻句） |
| 闭环 | 闭环（`audit_closed`） | 收口（名词义） |
| 落盘 | 落盘 | 落位 |
| 降级 / 兜底 | 降级＝传输链事件；兜底＝manual 档位 | 混用；fallback 只留代码/工具名 |
| 人 | 人（维护者） | 裸"人" |

例外：stub 类标记仍叫"标记"（`guide-stub` / `align-stub`）；task→报告的 `report:` 指针仍叫"指针"。

## Record lifecycle (from `README.md`; enforce where a machine can)

### 修订制度

已 Accepted 的 ADR 有两种修订操作：

| 操作 | 场景 | 做法 |
| --- | --- | --- |
| **Supersede** | 决策被推翻；选了完全不同的方案；两条 ADR 合并后冗余的那条 | 新 ADR frontmatter 写 `Supersedes: ADR-旧号`；旧 ADR 被自动标记 `Status: Superseded` + `superseded_by: ADR-新号` 并移入 `obsolete/`（闸统一处理，见下方归档闸表格） |
| **Amend** | 适用范围扩大/缩小；措辞歧义澄清；新增不变量；术语统一 | 就地改正文 + `Amended-by` 列表留痕 + Markdown footnote 标记 |

**判断口诀**：原来的选择还是对的吗？是 → Amend；不是 → Supersede。

### Supersede 判定标准

以下任一成立即 Supersede：

1. 决策本身被推翻（选了相反方案）
2. 不变量被反转
3. 选了完全不同的技术方案
4. 两条 ADR 合并，冗余的那条（原 ADR 的决策仍然成立，但已并入另一条）

### Frontmatter 格式

```yaml
---
Status: Accepted
Supersedes: -                    # 仅新 ADR 填写：替换了哪条；旧的不写 Superseded-by
Amended-by:                      # 修订记录列表，无则 `-`
  - 1 | Core Maintainer | 2026-09-14 | §2.3 第 2、8 条加作用域声明
Landed-by: src/k3dge/cli/mcp.py
Date: 2026-08-24
Deciders: Core Maintainer
Note: -                          # 非修订类元信息（过闸口径、历史痕迹摘要等）
---
```

- **`Supersedes`**：仅新 ADR 填写。旧 ADR 被 seal 闸自动修复为 `Status: Superseded` + `superseded_by`。
- **`Amended-by`**：列表格式 `- 🅰<修订序号> | <授权席位> | <日期> | <简述>`。无修订则 `-`。
- **`Note`**：非修订类元信息，默认 `-`。修订痕迹全部进 `Amended-by`；早期长 Note 已收敛为「修订痕迹见 git 历史」。
- **frontmatter 只放数据，不放散文注释**：`---` 块里的 `#` 行会被朴素解析器当成 H1，实测污染过 `k3dge doc list` 与 `docs/generated/docs-index.json` 的 title（12/14 条 ADR 标题变成注释首行）。写法指引一律放正文的 `<!-- … -->`（见 `_template.md`）。

### `obsolete/` 归档闸

seal 时 `adr_gate.reconcile_supersedes` 统一处理不再活跃的 ADR：

| Status | 含义 | 去向 |
| --- | --- | --- |
| `Superseded` | 被新 ADR 替换 | 自动改 frontmatter + 移入 `obsolete/` |
| `Rejected` | 提议后被否决，从未生效 | 直接移入 `obsolete/` |
| `Deprecated` | 仍然有效但不推荐 | **留在** `docs/adr/`（“别这么做”的信号，需被看到） |
| `Accepted` | 生效中 | 留在 `docs/adr/` |
| `Draft` / `Proposed` | 未完成 | 留在 `docs/adr/`（阻断 seal） |

`obsolete/` 不在门禁扫描范围内（`glob("*.md")` 不递归），自动跳过。

### 内联修订标记（footnote）

Amend 时在正文被修改处紧跟 Markdown footnote：

```markdown
2. **`check` 是纯静态硬闸**[^🅰1.1]：只验盘上文件与结构…

8. **k3dge 调的是「动作」，不是「步骤」**：一次 `run_action`＝peer 侧一件完整的事。
   - k3dge 不拆解 peer 的内部轮次[^🅰1.2]；peer 暴露的参数即公共接口…
```

文末挂载详情：

```markdown
---

[^🅰1.1]: 修改：为第 2 条补充作用域声明，明确此约束只针对 `check` 命令。
[^🅰1.2]: 修改：为第 8 条补充作用域声明，删除「不得外溢成 k3dge 参数」句。
```

- 编号规则：`<修订序号>.<本次改动序号>`，如 `🅰1.1`、`🅰1.2`
- **修订序号是该 ADR 自己的序**——它在本条 `Amended-by` 列表里的第几条，第 1 次修订即 `🅰1`；`Amended-by` 与 footnote 两处同用一个号
- 不用删除线（agent 无法可靠区分“已删”与“有效”，误读为正文）
- 删除或覆盖的内容不用显式标识，交给 git

### 新建

**先查同类 ADR 并入**（见「先并入，后新建」）；确无同类才 copy `_template.md`，`Status: Proposed` → 由人/k3dit 判 `Accepted`。机验码：`ADR_SECTIONS_MISSING`, `ADR_NUMBER_COLLISION`, `ADR_FRONTMATTER_MISSING`。

### 编号分配 / 删除 / 改名 / 复用

- **分配**：下一个号 ＝ max over（`docs/adr/*.md` ∪ `docs/adr/obsolete/*.md` ∪ 退役账本表）+ 1。只增不减 ⇒ 退役号永不再发出。
- **Numbers are never reused**：号一旦分配就永久绑定那一个决策；被合并/取代/否决后**该号退役**。
- **退役只有一条路：移入 `obsolete/`**（frontmatter 写清去向：`merged-into` / `superseded-by`），由 `adr_gate.reconcile_supersedes`（挂 `k3dge sync`）执行。**不再物理删除**——物理删除会让退役号从目录消失，于是"本目录最大号 +1"必然把它重新发出（实测：19 个号被删过，其中 6 个被发出两次）。
- **退役账本** = `docs/adr/obsolete/README.md` 的「永久退役号」表。它只承载 baseline（2026-09-19 / `f749e27`）**之前**被物理删除、因而没有墓碑文件的 13 个号；baseline 之后的退役一律是 `obsolete/` 里的真文件，不进表。
- **存量不追**：baseline 之前已被复用的 6 个号（0008/0009/0010/0022/0023/0026）保持现役、不迁号——迁号会打断全仓与下游仓继承的引用。口径同 ADR-0026 §2.5。
- **机验码**（别再误信旧说法）：
  - `ADR_NUMBER_REUSE` — 新 ADR 占了退役号（查 `obsolete/*.md` + 账本表）
  - `ADR_REF_RETIRED` — 正文引用退役号 ⇒ 给出去向（比 `DANGLING_ADR_REF` 更有用：号是"曾存在"，不是"写错"）
  - `ADR_FILENAME_MISMATCH` — 文件名号 ↔ H1 号一致（**它管不了复用**，旧文声称能管，是错的）
  - `ADR_NUMBER_COLLISION` — 现役文件之间重号（`doc_catalog.validate_docs`）

### 杂项

- **Section numbers must ascend** in document order (`## 1` → `## 2` → `### 2.1` → `### 2.1.1` …). Machine-gated: `k3dge check` fails it with `ADR_SECTION_ORDER`.
- A durable design change = its own ADR, judged by k3dit/human — the same seat must not both write and ratify (ADR-0006). An agent editing an ADR without a human/k3dit pass is **not** a decision record yet.
- **本文件是这些特权的唯一投递点**：`README.md` 只写默认路径与指针，不复述例外；两者冲突以本文件为准。

Structure gate is `.schema.json` (`k3dge check`).
