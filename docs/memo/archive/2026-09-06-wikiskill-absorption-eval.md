# Memo: WikiSkill 论文吸收评估（Google Research, arXiv:2608.27454）

> **Legacy note（归档 2026-09-12）**: §1 提案接受史落 k3dit `feat-proposal_log`；§2 隔离实证落 k3dge `docs-adr_isolation_evidence`＋k3dit `docs-protocol_absorption_backfill`；§3 PURPOSE 回指落 k3dge `docs-adr_isolation_evidence`、index 形态落 k3che `docs-index_entry_form`。

- **类型**: 可落地（3 条机制；思想借鉴，论文无代码可粘，不涉许可）
- **念头**: WikiSkill 做 skill evolution：Raw（不可变执行轨迹）/ Wiki（累积结构化知识）/ Skill（可回滚程序知识）三层 + Inference→Maintainer→Proposer→Gating&Rollback 四组件循环。5 模型×5 benchmark 全胜，ablation 给了关键数字。
- **触发场景**: 2026-09-06 会话，维护者贴论文问"有什么可以借鉴"
- **Date**: 2026-09-06

## 1. 吸收：skill-impact.md（提案接受史，防重复提案）

- **论文机制**（§3.2.4）：每次提案记 metadata + target + unified diff + 验证分 + Accepted/Rejected，wiki 永不回滚；Proposer 首读 impact 史，"DO NOT repeat rejected approaches"。Figure 3 案例：Iteration 0 被否的 goal-directed-action，其 diff 留档，Iteration 1 的 break-repetition-loop 明确写"Previous attempt rejected for being too abstract"。
- **我方缺口**：rounds 账本有 claim/complete，但**没有"被拒提案"记录**——被否的透镜修改/审计结论会换个措辞再提一次（memo 废案表是静态的，不是执行轨迹驱动的）。
- **落点**：审计模块账本加 proposal log（提案 diff + 接受史）；复核窗/Proposer 开工首查 impact 史。随 G4（声明模型同批：都是账本形态扩展）或 G7 测试。
- **不搬**：LLM 自动 proposer（我方 proposer 是席/人，不做自动进化循环）。

## 2. 吸收：执行席隔离 wiki 的实证（ablation Table 3）

- **论文数字**：Proposer 有 wiki 时，给 Inference Agent 开 wiki 访问 → 平均 63.7%→60.9%（LiveMath 72.6%→64.8%）。假设：执行席直接从 wiki 拿答案，轨迹信息量下降，skill 质量降。
- **我方映射**：这正是 W1/β 粒度（执行席只读当轮材料，不读累积知识）的**第三方实证**。我方此前只有论证（memo h8m2k-a1），现在有对照实验数字。
- **落点**：引用进 ADR-0025 W1 依据（Reopen when ② 的反向证据：若放开隔离，需先复现此 ablation）；seat_prompt 加"不读账本历史，只读本轮材料"红线（现已有"不知为何这么写"纪律，补数字脚注）。
- **不搬**：它的全套进化循环（我方不做自动 skill evolution）。

## 3. 吸收：三层分离的语义（raw 不可变 / wiki 只增 / skill 可回滚）

- **论文语义**：skill 被拒只回滚 skill，wiki 永不回滚（Algorithm 1 line 16-18）；PURPOSE.md 把 skill 回指 motivating patterns；index 条目=PROBLEM+ROOT CAUSE+FIX 一句可判（§E.2 Index Quality）。
- **我方映射（验证多于新增）**：
  - k3che learn 只增不改（update_learned 去重幂等）→ 语义正确，wiki 层合格；
  - protocol 透镜修改走 check 绿 + ADR → 门控合格；
  - 缺的是 **PURPOSE 回指**：透镜节改了，哪条 pattern 驱动的？protocol 对口表有"对口"无"缘起"。补：重大透镜修订在 ADR Decision 里写缘起 pattern（已部分有，如 ADR-0004），立为惯例而非新机制。
  - index 条目形态（问题+根因+修复一句可判）→ k3che search 结果的 title/snippet 形态可照抄（P2，k3che task）。
- **不搬**：自动 wiki 剪枝（论文 Limitations 自认无 prune 机制——我方也不做；k3che 索引 refresh 的 drop 已删已够）。

## 4. 排除（附因）

- 全自动进化循环（Inference→Maintainer→Proposer→Gating 无人值守跑 K 轮）：我方审计每轮要人章（W5），循环无人化与章在人手冲突。
- 跨模型 skill 迁移结论（小模型 skill 可胜大模型）：有趣但属执行能力研究，与审计判断无关。
- 中性验收门槛批评（论文自认 strict gating 排除中性提案）：我方 escalated/有意留已有三态，比它细，无需改。
