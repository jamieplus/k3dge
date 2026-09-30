---
type: DOCS
severity: P2
status: closed
---

# Incident: 恒真的取证命令——`grep` 漏 `-E` 且用全角分隔符，"零命中"被当成已验证

## 1. 现象与证伪证据 (B-T-D Evidence)

- **预期行为 (Baseline)**：票与报告里的"取证"行必须**能证伪**——同一条命令在标记存在时要有命中
  （`AGENTS.md §13`：证据链要给出可复算的产物＋判据，"名字/意图"不算证据）。
- **现存破损 (Treatment)**：`docs/tasks/2026-09-21-M11-docs-docs_align_m11.done.md` 取证块写
  `grep -l "ARCH_TABLE_DRIFT｜ARCH_STATE_DOC_DRIFT｜_refresh_projections｜doc_gate｜INIT_DELIVERED_DOCS" docs/adr/*.md → 零命中`。
  两个错叠在一起：① 没 `-E` ⇒ `|` 是字面字符（这里还是**全角 `｜`**）；② 于是整个模式是一个不可拆的
  字面串，对任何仓库都必然"零命中"。**重跑正确命令得两条命中**（ADR-0004 / ADR-0018）：

  ```bash
  grep -lE "ARCH_TABLE_DRIFT|ARCH_STATE_DOC_DRIFT|_refresh_projections|doc_gate|INIT_DELIVERED_DOCS" docs/adr/*.md
  # docs/adr/0004-milestone-lifecycle-governance.md
  # docs/adr/0018-doc-readme-anchor-governance.md
  ```

- **复现路径**：见上命令；错误原文在该 done 票 L16（由 k3dit 09-29 bundle 审计 code-21 抓到）。

## 2. 根因剖析 (5 Whys)

1. 为什么"零命中"被接受？——它是**结论**而不是**判据**：命令的形状与被验事实（标记在不在 ADR 里）无关。
2. 为什么会写成这样？——取证行是从别的票**照抄的模板**，抄的时候只保留了"看起来像验证"的外壳。
3. 为什么没被发现？——票/报告的机检面只验**结构与新鲜度**（schema、指针、新鲜度闸），不执行证据命令。
4. 为什么会漏 `-E` 又混进全角？——中文正文里 `｜` 与 `|` 视觉同形，纯人写无回读校验。
5. 为什么这类错只在文档面？——代码面的同类洞都有测（`facts_of`/反向机检），**散文里的命令**没有对端。

## 3. 防退化动作清单

- 该票不历史改写：在 `## 回填` 追加更正 + 正确命令的真实输出（已完成）。
- 规则面（已有机检承接，无需新闸）：`AGENTS.md §13` 要求三件证据（产物/消费者/到达），
  "恒真命令"缺第一件的**可复算性** ⇒ 判 `unverified`，按规则即须问人。
- 待议（不改判据）：审计侧可在下一轮把"证据命令必须能证伪"作为 k3dit 透镜的读项清单条目；
  进程侧若要机检，形状是"票里的代码块命令在声明前后各跑一次比对"——成本高、易误伤，先归人/k3dit。

## 4. 经验灌入

- 进 `docs/reviews/LEFTOVERS.md` 的判据段：**写"取证"必须写"能失败的东西"**——
  先问"若这件事没做，这条命令的输出会怎么变"，答不出来就不是证据。
