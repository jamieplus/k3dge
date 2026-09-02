---
Status: Draft
# Append-only after Accepted. Revise via `Amended by` / `Superseded by` below — do
# NOT rewrite this decision's prose in place, and never reuse a number (see README).
Supersedes: -
Amended-by: -
Date: 2026-09-02
Deciders: Core Maintainer (待 k3dit/人 复核后转 Accepted)
---

# ADR-0021: doc-audit 后置、非阻断（T-01 的边界）

## 1. 上下文 (Context)

T-01 定死 `k3dge check` 是**静态**硬闸：只做 TOML 结构 / stage 可解析 / manual 协议文件存在，**不连 MCP、不跑 CLI/LLM**。否则外部透镜挂死会把 GateReport 变成假失败/假通过。

新需求：文档（`docs/**`）改动也要过 authoring 合规审计并留下 review + task。若把它塞进 `check`，就破 T-01；若只做触发词、不留产物，又会"规则没进这一轮上下文"（发现留 `docs/reviews/`、代码/文档无人动）。

## 2. 决策 (Decision)

- **doc-audit 在 check 之后，不在 check 之内**。`check` 仍静态；绿了之后经 `[NEXT] state=doc_audit` 指一条非阻断的后续步：`k3dge doc-audit`。
- **doc-audit 不阻断，只出两样**：
  1. **报告**：路由 `k3dit.actions.audit`（`mcp→cli→manual`）做 authoring 合规；k3dit/人 产 12 列报告，k3dge 不伪造发现。
  2. **task**：`k3dge` 机械地建一个带 `Milestone: <当前>` 的 `doc-audit` task（幂等，同里程碑仅一个未关闭项）。
- **耐久保证 = task 归里程碑**：task 挂当前里程碑，封板硬闸要求"本里程碑任务全 done"，所以**即便人这一轮不改，里程碑收口轮也必须改**（否则 seal 不过）。这是"不阻断"却不丢的机制。
- **范围切分**：doc-audit 只管 **authoring 合规**。**ADR 冲突/覆盖检测留在里程碑审计**（用 `k3dge_adr_index` 事实、k3dit 判），不在每次 commit 的 doc-audit 里做。
- **非阻断 ≠ 无后果**：doc-audit 命令恒返回 0；但产出的 task 进入里程碑 backlog，由既有 seal 闸兜底。

### 2.1 明确非目标

- 不把 k3dit/MCP/LLM 调用塞进 `check`（破 T-01）。
- 不在 `check` 里自动写 review/task（check 保持只读静态）。
- doc-audit 不判"值不值得写"（k3lity/人），只走 authoring 合规透镜。

## 3. 产生后果 (Consequences)

- **Up**：T-01 保住（check 恒静态）；文档审计有产物、可寻址、由 seal 兜底；`[NEXT]` 把"你忘了审文档"递到动手那一刻。
- **Down**：文档改动会产生额外 task，需人/agent 在里程碑内消化；manual 兜底时报告质量归人。
- **Reopen when**：需要 doc-audit 阻断（如合规硬要求）时——那要重新界定"进 check 之前还是之内"并付 T-01 的代价。
