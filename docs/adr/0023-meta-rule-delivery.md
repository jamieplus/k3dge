---
Status: Draft
# Append-only after Accepted. Revise via `Amended by` / `Superseded by` below — do
# NOT rewrite this decision's prose in place, and never reuse a number (see README).
Supersedes: -
Amended-by: -
Date: 2026-09-02
Deciders: Core Maintainer (待 k3dit/人 复核后转 Accepted)
---

# ADR-0023: 元规则如何抵达 agent（证据链这类全局认知的投递通道）

## 1. 上下文 (Context)

跨切元规则（ADR-0012 证据链、不编排、先读后写、两问拆分…）反复栽在同一个坑：**规则写了，但投递方式错了**——放在 `docs/adr/` 里、靠 AGENTS.md 顶部一句"read first: ADR-xxxx"去指。指针要 agent 主动跳一跳才生效，且随轮次衰减出视野。

ADR-0012 自己已把这条路判死：**"'Agent 会回头读/会去逛隐藏目录'不算到达方式"**。所以"顶部指针 + 信任回头读"不是到达通道。

本会话实证（非臆造，均可复跑）：AGENTS.md 起手 read-first 里点了 ADR-0012，我仍跳过，并杜造"k3dge 已有 ADR-0013 A/B compare harness（`tools/eval/`、6 指标）"写入已提交 ledger。核实反证：`ls tools` → 无此目录；`find tools/eval -type f` 空；`sed -n '1,14p' docs/adr/0013-*.md` → 首行 `# ADR-0013: 自动版本与变更日志`。即：**规则在场、指针在场，断言照样杜造**——证明"读 first"不是投递。

问题不是"再写一遍规则"，是"用哪条**每轮真被加载/真被读**的通道把不变量送到决策当刻"。

## 2. 决策 (Decision)

元规则只经以下通道投递；**"真伪判断"永不进闸**（见 2.4 + ADR-0012 §2「不增加 k3dge check 规则」、§3「机器抽断言属审计 harness」）。

### 2.1 通道一：AGENTS.md 正文内联不变量（唯一每轮在场）
对**极少数**跨切元规则，把**不变量本身一行**写进 AGENTS.md 正文，而不是只放"读 ADR-xxxx"链接。指针要跳，一行原话直接在场。ADR-0012 的那一行即：
> 对仓库事实下任何"有/没有、还在不在、谁消费"断言前，先给 **产物/消费者/到达** 三条链；没跑过命令、没打开过文件 → 只写"未核"，禁止完整陈述冒充已核。
成本：AGENTS.md 胀。约束：只放真正每轮生效的元规则，一条一行，链接后置。

### 2.2 通道二：`[NEXT]` / 工具回执 时机投递（动作当刻，非开场）
复用生命周期已建的 `[NEXT]`/MCP `next` 通道：让 `k3dge status`/`check`/`doc` 在**相关动作**时附一条 `[META]` 元提醒（如首次在会话里做仓库断言→点 ADR-0012）。这是本仓证明"agent 每轮真读"的唯一输出面。约束：**限频**（会话首个相关动作一次即可），防刷屏；选项文本仍单一源（`engine/nextstep.STATE_OPTIONS`），命令不手抄。

### 2.3 通道三：k3che "未读回执"——把"注意到"变可观测（最治本，待实现）
不靠 agent 自觉，而由 **k3che**（本就记录 agent 读了哪些）维护"元规则读取回执"：`k3dge status` 缺项即报 `unseen_meta_rules: ADR-0012, …`（某元规则自本会话/某 hash 起未被打开）。把"到达"从"信任记忆"降级为"当场缺给你看"。
- 落点：k3che（记忆侧）；k3dge `status` 展示。需先定"读"的定义（`doc where`? 打开文件? transcript 命中）与回执失效边界（里程碑/commit）。
- 状态：**未实现**（本 ADR 仅定机制；实现另批，先定上述语义再写，避免"设计了没人建"）。

### 2.4 承认的边界（不可投递的部分）
- **不落 artifact 的聊天断言**：无文件可闸、无命令可回执 → 只能靠行为（先贴 `ls/rg/sed` 输出再下结论）。诚实记一句：**闸与回执都够不到"只存在于对话里"的杜造**。
- **落盘的那半可确定性堵**：committed 文档里"存在断言"型路径引用（`docs/**`/`tools/**`/`src/**`/`ADR-NNNN`）应能在盘上解析到。**注意：此闸目前不存在**——本仓现有文档闸只有 `ADR_FILENAME_MISMATCH`/`ADR_FRONTMATTER_MISSING`/`ADR_SECTIONS_MISSING`/`ADR_SECTION_ORDER`/`ADR_NUMBER_COLLISION`（`docs/adr/.schema.json`）、`DOC_INDEX_STALE`、`TEMPLATE_DRIFT`（`src/k3dge/engine/doc_catalog.py`/`evaluator.py`），没有"路径引用↔真实文件"检查，所以这是一项**新建**、非"同族已实现"。前置未决：**"存在断言" vs "将来/示例路径"的标记语义**没定之前不实现（否则满屏假红）。属 k3dge 结构闸，不判真伪。

## 3. 产生后果 (Consequences)

- **Up**：元规则从"顶部会衰减的指针"升级为"在场的一行 + 当刻的回执 + 可观测的未读"；本会话两类杜造（能力存在、路径存在）各有一道确定的拦截。
- **Down**：AGENTS.md 顶胀；k3che 回执需 transcript 可达且先定义"读"；[NEXT] 限频要拿捏；2.4 的标记语义不定会误报。**且 2.3 只是决定，未落地**——别把"写了 ADR"当"已生效"。
- **Reopen when**：宿主若改为每轮自动重投系统提示/元规则，则 2.2/2.3 可降级；若真需要机器判自然语言真伪，那属 k3dit 审计透镜（sidecar ADR-0006），不进 `src/k3dge`。
