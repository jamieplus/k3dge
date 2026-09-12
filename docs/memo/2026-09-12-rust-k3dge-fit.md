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
