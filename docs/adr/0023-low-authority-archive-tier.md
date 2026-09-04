---
Status: Proposed
# Append-only after Accepted. Revise via `Amended by` / `Superseded by` below — do
# NOT rewrite this decision's prose in place, and never reuse a number (see README).
Supersedes: -
Amended-by: -
Date: 2026-09-03
Deciders: Core Maintainer
Note: -
---

# ADR-0023: 低权威层归属（archive 契约；不建 legacy 目录，也不维护历史编号映射）

## 1. 上下文 (Context)

系统结构大改（四 harness 拆分、Diátaxis 分层、编号两次重排）之后，仓里存在两类"旧东西"，权威性质相反：

- **旧正文**：大改前的整篇文档、废弃协议、旧报告。只在考古某个未拆净的部分时看一眼。
- **旧编号引用**：重排前写下的 `ADR-00NN`。它们的处置方式此前是一张 `docs/adr/README.md` 的映射表（处置见 §2.3）。

已核事实（决定成本，非推测）：

- 低权威层机制**已存在**：`docs/{memo,reviews,tasks}/archive/` 三处；`engine/doc_catalog.py:70-78` 的 `iter_managed_files(..., include_archive=False)` 已让 `doc list` / `build_docs_index` / `where` / `search` 默认跳过归档件（`doc_catalog.py:455` 同）。缺的是契约，不是目录。
- 新建顶层类型的固定成本：类型本身由目录推导（`doc_catalog.iter_doc_types:55-63`，只排 `SKIP_TYPES={generated}` 与点开头目录，无需登记），但 `scripts/pre-commit:4-8,52-57` 对每个 `docs/<type>/` 硬性要求 `README.md` + `AUTHORING.md`，缺任一 **commit 被拦**；再要下游同步则牵模板资产与四个 peer 仓。
- 归档件现状（实测）：三处 `archive/` 共 **106 份 `.md`**，带任何去向标记的 **0 份**。
- 旧号对照的需求面积（实测）：归档语料里对重排前编号的引用共 **1 次 / 1 个文件**；现行文档里同号引用 **134 次 / 61 个文件**，含义均为现行号。⇒ 任何"旧号解析 / 歧义告警"机器只服务 1 处引用，却要覆盖 134 处正常引用。

`ADR-0012` 的既有取向继续约束本决策：真伪与质量不进门禁，机器只判结构事实。

## 2. 决策 (Decision)

### 2.1 低权威层 = 各类型 `archive/`，不建 `docs/legacy/`

过期正文一律进该类型的 `docs/<type>/archive/`。**不新建顶层 legacy 类型**：`archive/` 已提供"默认隐身 + 显式可取"，新顶层类型只多付两份治理件与全仓模板同步，换不到任何新能力。

### 2.2 归档契约（进 `archive/` 的三条件）

1. 文件顶部必须有一行去向：`Superseded-by: <现行权威路径>`，或 `Legacy note: <仅供 X 场景考古；判定以 Y 为准>`。二者皆无 ⇒ 不算归档完成（归档不是藏起来）。
2. 引用归档件必须写**含 `archive/` 的完整路径**。写全路径本身就是"我在引旧账"的声明；裸引已归档文件名按悬空处理（现行索引里没有它）。
3. 归档件不参与现行索引与 `doc list`（已是事实，此处升为契约）；需要它的调用方必须显式传 `include_archive=True`，不得改默认。

### 2.3 历史编号不维护映射表，也不做任何机器出口

- **删除** `docs/adr/README.md` 的 `## Legacy numbers` 表。按号引用若逻辑不通，读者按标题与内容在 `docs/adr/` 里重找即可 —— 编号是检索的辅助，不是主键。
- 「号不复用」继续由 `README` 与 `AUTHORING` 的既有句子守（`Numbers are never reused`），取号看现存文件名即可；不引入"已烧号"清单、不让任何工具读某张表来判号。
- Non-goal 明确：不建旧号重定向、不加歧义告警、不新增 `check` 规则、不引入 `Note:` 之外的任何编号元数据。理由即 §1 的实测需求面积。

### 2.4 引用编号的写法（软规则，k3dit 判，不进闸）

- 带号引用附标题短语（`ADR-0017 报告 schema v2`）。本仓多数文档已在这样做；它是"删掉映射表之后仍然可解"的代价最低保障，因此与 §2.3 是一体两面。
- 描述历史上某个号曾指什么时，写事件而不是裸号（"2026-08 重排前的那个号"）。

### 2.5 非目标 (Non-goals)

- 不为归档件增设结构闸（内容质量归 k3dit 与人）。
- 不批量补历史归档件的去向标记（存量 106 份按 §2.2 只对增量生效）。
- 不做"顺手清理旧文档"：物理删除需人显式授权。
- 不把 `docs/generated/` 当低权威层（它是机器重算的投影）。
- 不引入跨仓共享的 legacy 区或共享编号表（peers 各管各的 `archive/`）。

## 3. 产生后果 (Consequences)

- **Up**：`archive/` 从"看不见"变成"可追溯地看不见"；本仓不维护一张几乎无人查、却要人更新的历史对照表；不引入围绕它的工具与规则；避开一次顶层类型扩张。
- **Down**：重排前的旧号引用失去官方对照，只能靠标题/内容重找（实测代价：归档内 1 处）；§2.2 的第 1 条若无提醒会退化（提醒设计见关联 task，非阻断）。
- **Reopen when**：① 归档件数量或误引频率实际上升到可见程度（目前 0 标记 / 1 处误引，不构成理由）；② `archive/` 需要按里程碑分层检索；③ 出现第三轮重排且确实产生持续误引。

