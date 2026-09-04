---
Status: Accepted
# Append-only after Accepted. Revise via `Amended by` / `Superseded by` below — do
# NOT rewrite this decision's prose in place, and never reuse a number (see README).
Supersedes: -
Amended-by: -
Date: 2026-08-24
Deciders: Core Maintainer
Note: -
---

# ADR-0012: Agent 对仓库的断言必须带证据链

## 1. 上下文 (Context)
`.agent/` 曾被断言成「给 Agent 的发现面 / 自说明根」。制作 agent 与后续 agent 都写过这类句子。实证：主流 harness 自动加载的是 `AGENTS.md`，列目录工具默认不显示点目录，按协议干活可以整段不打开 `.agent/`。断言没有消费者、也没有「怎么到达消费者」这一环，只靠目录名和意图。

`k3dge check` 拦不住这种话：哈希与 spec 结构都不读「这个目录是给谁的」。ADR-0009 要收的失败态包括幻觉；这一条是幻觉的一种——把命名当证明。

用户确认：要补进本 harness。不进 `engine`（无法机器判定自然语言断言），进 `AGENTS.md` 协议。

## 2. 决策 (Decision)

对**本仓库的事实断言**（某路径是干什么的、谁消费、某能力还在不在、没有设计问题、Agent 会发现 X），同一轮必须给出三条链，缺一则不许下结论：

1. **产物**：磁盘路径或命令输出（打开过 / 跑过）。
2. **消费者**：engine / `k3dge check` / CI / `AGENTS.md` 自动加载 / 无。
3. **到达方式**：硬编码路径、harness 自动加载、`AGENTS.md` 点名路径。禁止用「Agent 会逛到隐藏目录」当到达方式。

**不是证据**：目录名、注释里的愿望、上一轮聊天、「我没提过所以没问题」、未打开的文件。

**不要求三条链**：复述用户原话、说「我去读某文件」、提出问题、按 spec 改代码（那是 L0/L1 的事）。

缺链时写「未核」或问一句，禁止用完整陈述冒充已核。本条不增加 `k3dge check` 规则。

## 3. 产生后果 (Consequences)

- **正**：`.agent/` 那类「名字像给 Agent、实际无人加载」不能再当事实说出去。
- **负**：Agent 可能啰嗦。用三条链卡住范围，禁止把每句闲聊都做成引用列表。
- **何时重开**：若要机器抽断言做闸，那是质量/审计 harness，不进 `src/k3dge`。
