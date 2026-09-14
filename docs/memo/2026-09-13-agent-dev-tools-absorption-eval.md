# Memo: Agent 开发工具吸收评估——codegraph / open-code-review / worktrunk

- **类型**: 可落地（三源；clean-room，许可均宽松）
- **念头**: 扫 workspace 下三个开源项目（codegraph MIT、open-code-review Apache-2.0、worktrunk MIT/Apache-2.0），判**哪些能增强 k3dge 系统的能力**（而非扩基建/囤储备）。
- **触发场景**: 2026-09-13 维护者道"下了 codegraph/open-code-review/worktrunk，评估直接用或吸收"；随后定方针：**不是扩基建/增储备，而是 enhance 系统、增强能力**。
- **Date**: 2026-09-13

## 0. 判据（方针）
**"它让 k3dge/k3dit 新能做**什么**、或让既有**能力明显更准**吗？"**
- 是 → **能力增量**，做。
- 只是多一层存储 / 多一个 peer / 多一张"以后再说"的票 → **基建/储备**，不做。
- **增强 ≠ adopt**：可**借其技术**增强，不背其**平台**（Node/Rust/SQLite 平台、自带 LLM/agent）。

## 1. codegraph（MIT；TS + Rust kernel）
tree-sitter 解析 20+ 语言 → 本地 SQLite 知识图（symbols/edges/files + FTS5）；MCP 单工具 `codegraph_explore`；CLI `affected`/`impact`/`callers`/`callees`；监听自动增量同步。

- **能力增量**: 依赖/影响从**近似 → 可用**（真代码图 / 调用链 / blast radius）+ **changed→affected tests**。我们现只有 `import_graph` 近似。
- **落法（借技术不背平台）**: stdlib 把 `import_graph`/`blast_radius` 升到"边更全 + **模块→测试映射**"，喂既有 `check --with-tests`；**不引 Node/Rust/SQLite 平台**。
- **不做的（基建）**: 换 SQLite+FTS 存储（换存储不产生新能力；某闸确需图边时，把**最小图边**并入该能力即可——本 memo 已并入 `affected_tests`）。作 service peer / 拉平台 = 基建，需 ADR 且非本方针首选。

## 2. open-code-review（Apache-2.0；Go）
AI 代码评审 CLI（`ocr`）；核心＝**确定性工程 × Agent 混合**：精确选文件、Smart file bundling、**模板引擎式规则匹配**、**外置 positioning/reflection**；含 `scan`、delegation mode、session viewer、**AACR-Bench**。

- **能力增量**: **审计保真度**——定位(positioning)+反射(reflection) 把"席判易漂"→"确定性校正"；模板化规则把判定从散文→机制。
- **落法**: 机制进 k3dit（确定性后处理 pass + 规则声明化）；**不引进其自带 LLM/agent**（与 Hall 席位重叠，越位 ADR-0006）。
- **AACR-Bench** = k3dit `feat-eval_harness` 的实操蓝本（指标/数据集/纪律）。

## 3. worktrunk（MIT/Apache-2.0；Rust）
git worktree 管理器（为并行 agent）：`switch/list/merge/remove` + hooks + 共享 build cache。

- **能力增量**: **选测更准**（`cargo-affected` 覆盖驱动选测 + `[metadata.affected.rule]` 输入规则防漏）——与 codegraph `affected` 同源，并入该能力。
- **非能力（不囤）**: worktree 生命周期本身 k3dge 已够（`worktree.py`＋落点闸）；hook 命名 / `wt list` 美观 = 体验，非能力。

## 4. 能力增量 vs 基建/储备
| 项 | 类别 | 处置 |
| --- | --- | --- |
| 规则声明/模板化（OCR） | **能力**（闸更准） | 做 → k3dit `feat-rule_template_matching` |
| 定位+反射后处理（OCR） | **能力**（审计更真） | 做 → k3dit `feat-position_reflection` |
| 依赖感知 + affected tests（codegraph/worktrunk） | **能力**（check/CI 更准） | 做 → k3dge `feat-affected_tests`（含最小图边 + 防漏选测） |
| AACR-Bench 蓝本（OCR） | **能力**（评测可测） | 并入既有 k3dit `feat-eval_harness` |
| FTS/explore 检索参照（codegraph） | 参照 | 并入既有 k3che `absorb_p3_recall_reflect_guard` |
| SQLite+FTS 符号平台 | 基建（换存储） | **不囤**（并入 affected 的最小图边） |
| 单强 MCP 工具 | 体验（非能力） | **不囤** |
| Smart file bundling | 覆盖/体验 | **不囤**（并入参照，不单列） |
| worktree 生命周期/hook | 已够 | **不囤** |
| codegraph 作 peer / OCR 作 code-lens 后端 | **adopt 平台** | 仅 ADR 评估，非本方针 |

## 5. 净效果
k3dge 仍是"小而确定的闸"，但**闸更准（依赖感知）、审计更真（定位/规则机制化）**——**增强能力**，不是变大。

## 6. 相关
- 吸收规范：`.agent/rules/09-absorption.md`（clean-room / 去品牌 / 路由 peer / 1 行署名）。
- `docs/adr/0001`（零依赖）、`docs/adr/0006`（peer 方向性不变量 / sidecar 不重粘 work+check）、`docs/adr/0025`（审计模块）。
- 既有吸收先例：`docs/memo/archive/2026-09-06-deeptutor-absorption-eval.md`、`.../2026-09-05-industry-benchmark-vs-4-harness.md`。
