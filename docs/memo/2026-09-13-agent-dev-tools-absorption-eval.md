# Memo: Agent 开发工具吸收评估——codegraph / open-code-review / worktrunk

- **类型**: 可落地（三源；clean-room，许可均宽松）
- **念头**: 扫 workspace 下三个开源项目（均为**宽松许可**：codegraph MIT、open-code-review Apache-2.0、worktrunk MIT/Apache-2.0），判"可直接用 / 可吸收(clean-room)"与归属（`Consistency→k3dge` / `Audit→k3dit` / `Memory→k3che`）。
- **触发场景**: 2026-09-13 维护者道"下了几个开源项目（codegraph/open-code-review/worktrunk），扫描评估直接用或吸收的可能"。
- **Date**: 2026-09-13

## 1. codegraph（MIT；TS + Rust kernel）
**是什么**: 本地语义代码图。tree-sitter 解析 20+ 语言 → 本地 SQLite 知识图（symbols/edges/files + FTS5）；MCP **单一强工具** `codegraph_explore`（一次调用＝verbatim 源码 + 调用链 + blast radius）；CLI `affected`/`impact`/`callers`/`callees`/`query`；文件监听自动增量同步 + 每文件 **staleness banner**。

- **可直接用**: 作**外部 service peer**（MCP）喂席/agent "surgical context + blast radius"。合 ADR-0006 peer 模型（service，`mcp→skip`）；不进 k3ge 本体，不破零依赖。**纯 Python 小仓收益相对我们已有 `import_graph`/`blast_radius` 有限。**
- **可吸收（clean-room；k3ge 可 stdlib 落地）**:
  - ⭐ **SQLite(stdlib `sqlite3`) 符号/边图 + FTS** 取代扁平 `docs/generated/symbol-index.json`——不破零依赖，最大吸收点。
  - ⭐ **`affected`**：传递 import → 受影响**测试文件**（我们 `blast_radius` 已有下游模块，缺"测试映射"）→ 直接喂 `check --with-tests` 选择性 L2。
  - **单工具 MCP 论**（"one strong tool 胜过菜单"）→ 评估把 k3ge MCP 面收敛一个 `k3dge_explore`（NEXT+事实+指针）。
  - **staleness banner**（点名 pending 文件）→ 与 `DOC_INDEX_STALE` 同类，吸收其"显式点名"诚实模式。

## 2. open-code-review（Apache-2.0；Go）
**是什么**: 阿里内部育出的 AI 代码评审 CLI（`ocr`）。核心＝**确定性工程 × Agent 混合**：确定性侧＝精确选文件/过滤、**Smart file bundling**（按亲和分单元+子 agent 隔离上下文+并发）、**模板引擎式细粒度规则匹配**、**外置 positioning/reflection 模块**；Agent 侧＝动态决策+检索。含 `scan`（无 diff 全量审）、**delegation mode**（宿主自带 LLM，OCR 只出选文件+规则）、session viewer、**AACR-Bench**（50 repo/200 PR/1505 真值；F1/precision/recall）。

- **可直接用**: 作 k3dit **code-lens 后端候选**（pipeline peer：CLI/MCP/delegation）。许可允许；但其自带 LLM+agent 与 k3dit Hall/席位**架构重叠**，直用前需 ADR/契约评估。
- **可吸收（clean-room；价值高）**:
  - ⭐ **positioning + reflection 后处理模块**——专治"位置漂移/内容不准"，正对应我们"位置钉/钉漂移"。可立后处理 pass（复核窗或 Hall）校正 findings 的 `location` 与内容一致性。
  - ⭐ **AACR-Bench 评测法**＝ k3dit `feat-eval_harness` 的**实操蓝本**（指标/数据集/纪律）。
  - **模板引擎式规则匹配** → 强化 k3dit **窗卡 + `JUDGE_TYPE_DOMAIN`** 走向声明/模板驱动。
  - **Smart bundling** → k3dit 窗/批改进（相关文件绑成一个 review 单元）。
  - **精确选文件/过滤** → k3dit 物化/范围裁选。
  - **delegation mode** → 与"席在机构侧、k3dge 不代笔"同构，**外部佐证**。

## 3. worktrunk（MIT/Apache-2.0；Rust）
**是什么**: `wt` = 为并行 agent 设计的 git worktree 管理器（`switch/list/merge/remove` + hooks + LLM commit + 共享 build cache reflink + branch 寻址）。

- **可直接用**: 纯 git worktree 操作可**局部委托 `wt`**；但 k3ge `worktree.py` 含 spec-gate 专属（baseline ref、`merge_back` accept_dirty、`strip_pins`、落点闸），**不可整体替换**。
- **可吸收（clean-room；k3ge）**:
  - **pre-merge / post-merge hooks** ↔ 我们"落点闸先验后并"（`merge_back`）——吸收其 hook 类型划分。
  - **"与 main 同 commit ⇒ 后台自动 remove worktree"** → 强化 `prune_finished`。
  - **`wt list` 状态表**（ahead/behind/dirty/unpushed/CI）→ `status`/`audit status` 观测面参考。
  - **`cargo-affected`（覆盖驱动选测）+ `[workspace.metadata.affected.rule]` 输入→测试规则**：与 codegraph `affected` **同一思路**；"快照读不到覆盖 ⇒ 强制选测防漏"值得吸收，对齐我们**选择性 L2**。

## 4. 交汇点（公共信号）
1. **changed→affected tests**（codegraph `affected` ≡ worktrunk `cargo-affected`）＝ k3ge **选择性 L2** 的正解。
2. **审计质量可测**（OCR AACR-Bench）＝ k3dit `eval_harness` 蓝本。
3. **worktree 生命周期 + hook 化**（worktrunk）＝ k3ge 审计线编排。

## 5. 归属与处置（已转票；见 Related）
- k3ge：`feat-affected_tests`、`feat-symbol_graph_store`、`feat-single_mcp_tool`、`chore-worktree_lifecycle`。
- k3dit：`feat-position_reflection`、`feat-rule_template_matching`、`feat-file_bundling`；**AACR-Bench 蓝本并入既有 `feat-eval_harness`**。
- k3che：FTS/`explore` 检索面参照并入既有 `feat-absorb_p3_recall_reflect_guard`。
- **直用（非吸收）**：codegraph 作 service peer、OCR 作 k3dit code-lens 后端——**均需先 ADR/契约评估**，本 memo 不自动立项。

## 6. 相关
- 吸收规范：`.agent/rules/09-absorption.md`（clean-room / 去品牌 / 路由 peer / 1 行署名）。
- `docs/adr/0006-mcp-foreign-harness-injection.md`（peer 方向性不变量）、`docs/adr/0025-hall-harness-topology.md`（审计模块）。
- 既有吸收先例：`docs/memo/archive/2026-09-06-deeptutor-absorption-eval.md`、`.../2026-09-05-industry-benchmark-vs-4-harness.md`。
