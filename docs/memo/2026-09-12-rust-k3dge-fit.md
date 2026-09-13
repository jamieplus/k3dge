# Memo: Rust × vibe coding 契合性——Rust k3dge 可行性

- **类型**: 暂无法落地（需先 supersede `ADR-0001` 的「Python 标准库」实现约束；建议先做尖刀实验）
- **念头**: 用 Rust 重写 k3dge 的价值不在"快"，而在**语言本身即护栏**：enum + 穷尽 `match`、`Result`、所有权/借用、类型化契约，把"漏分支/吞错/别名/形状错"变成**编译期错误**——对人是啰嗦限制，对 agent 是**规则明确、抽象得当、少自由裁量**，恰好贴 k3dge「Hard Gate / 防漂移」的原意；兼性能与内存管理。
- **触发场景**: 2026-09-12 会话，维护者问「开发 rust k3dge 的可行性/优缺点」，并明确关注"与 vibe coding 的契合性"。
- **Date**: 2026-09-12

## 1. 命题
k3dge 是**状态机 + 契约校验 + 硬闸**。Python 的动态 dict/`except: pass`/隐式边，正是漂移温床；
Rust 的静态类型与穷尽匹配让"未处理的边"无法通过编译——这与"把规则固化成机制、不靠自觉"同构。

## 2. 特性 × 防漂移
| Rust 特性 | 对 agent 的护栏 |
| --- | --- |
| `enum` + 穷尽 `match` | 状态机**漏一分支＝编译错**（相位/状态迁移不可漏） |
| `Result<T,E>` | 显式错误，根治 k3dge 的「空 `except` 吞错」债 |
| 所有权/借用 | 无别名/数据竞争，确定性强 |
| 类型化结构体 | 信封/契约是类型而非 dict，形状错编译期抓 |
| trait + 模块可见性 | 天然映射"事实归属/边界"纪律（规则 08） |
| 默认不可变 | 少意外变更 |

## 3. 代价 / 风险
- **模型熟练度**：语料远少于 Python → agent 更易在借用/lifetime 上打转，"防漂移"可能变成"编译错空转"。
- **自举丢失**：现 `pip install -e` 改完即用；Rust 加编译步，dogfood 变慢。
- **多语言碎片**：k3dit/k3che/席包装/Hall 全 Python，k3dge 成 Rust 孤岛（跨进程传输仍可行）。
- **生态**：tree-sitter 是 Rust 友好（Py+TS 一套）；但 MCP Rust 生态弱于 Python `mcp`。
- **工作量**：engine/contract/doc_catalog/milestone/MCP/CLI/tests/模板全重写。
- **冲突**：`ADR-0001` 明定「Python 3.10+ 标准库（核心零依赖）」——重写须**新 ADR supersede**，且 crates 依赖与"零依赖"相抵。

## 4. 尖刀实验（建议）
只把 **contract 引擎**（AST 提取 + 归一化哈希 + spec schema）做成 Rust crate（tree-sitter 一套覆盖 Py+TS），
对比指标：**捕捉率 / agent 迭代次数 / 上下文量 / 借用类错误率**；lifecycle/MCP 暂留 Python。
几千行内即可验证核心命题，避免全量重写的沉没成本。

## 5. 替代（更低成本）
Python + `uv`/`PyInstaller`/`shiv` 打单件（解决"分发/`k3dge not found`"），或 `maturin` 做 Rust 扩展加速热点——
先拿到"分发"收益，不背重写风险。

## 6. 结论
Rust 与 vibe coding 的"规约即护栏"确实契合，值得试；但**别全量重写**，先尖刀验"类型系统是否真降 agent 漂移"。
若走，须先立**新 ADR supersede `ADR-0001` 的实现语言约束**。

## 7. 尖刀实验 Phase-1 结果（2026-09-13，crate `../k3dge-contract-rs`）
**做法**：Rust + `tree-sitter`/`tree-sitter-python`/`sha2` 移植 contract 引擎（公开接口提取＋归一化＋sha256），与 `engine/contract.py` 做**散列 parity**。

**硬结果**：对 k3dge `src/k3dge/engine`，parity **初版 0/40 → 修 `future_import_statement`＋逐-alias import 后 14/40 (35%)**。26 个未达标分 4 类**语义**分叉（非类型问题）：① 引号归一（`ast.unparse`→单引号，CST 双引号）；② 模块注解常量 `X: T = v` 丢 `: T`；③ CST 把 `# 注释` 折进值；④ 括号式 `from m import (a,b)` 需按 CST 解析 alias。达 parity 需在 Rust 里**重造 Python 表达式 unparser**。

**关键发现（反命题）**：Rust 的「漏一分支＝编译错」**只在闭 `enum` 且不写 `_` wildcard 时**成立。初版漏 `future_import_statement` 时**编译器没拦住**——因为 `match node.kind()` 是**字符串匹配＋`_ => {}` 兜底**，与 Python 一样静默吞边；而 contract 引擎的输入是**外部字符串语法**，tree-sitter 的 `kind: &str` 天然削弱护栏。

**修正后的判断**：
- Rust 化在 k3dge **自有可枚举的状态机/信封/契约**上是**能力增强**（漏分支/形状错→编译期错）；
- 在「**解析外部语言语义**（contract 提取）」上是**高成本重写**（自造 unparser＋非零依赖），类型系统帮不上。
- 故：**不宜据 Phase-1 就 supersede `ADR-0001`**；先做 **Phase-2**（自有闭枚举状态机）验「是否真降 agent 漂移」再定。

## 8. 尖刀实验 Phase-2 结果（2026-09-13）
自有**闭枚举状态机**（crate `../k3dge-contract-rs` `src/phase.rs`：`TaskState` + 穷尽 `advance`，无 wildcard）：`compile_fail` doctest 证明漏一状态 ⇒ **编译错 E0004**；对照 Python 同漏分支静默。→ **护栏在自有闭枚举上成立且可证**。合 Phase-1：Rust 化**只在"自有状态机/信封/契约"上是能力增强**，在"解析外部语言语义"上是高成本重写。**不据尖刀 supersede `ADR-0001`**；若走，宜**混合**（核心闸/状态机 Rust，解析留 Python）或仅把护栏用于新增自有逻辑。

## 9. 尖刀实验 Phase-3 结果（2026-09-13，双语言对照）
同变更「新增状态并处理所有消费点」：Rust 只加 `TaskState::Blocked`（不改 match）⇒ `cargo build` **E0004 逐点列出 2 处待更新**；补点即绿（迭代 2）。Python 对照：`if/elif` 漏分支⇒**静默 None**，`dict` 漏键⇒**仅调用时 KeyError**（静态不可知）。→ 自有闭枚举上 Rust 把"漏分支"从**人自觉/运行时**变**编译期强制**（能力增强）；外部语义解析上不成立。详见 crate `../k3dge-contract-rs/EXPERIMENT.md`。
