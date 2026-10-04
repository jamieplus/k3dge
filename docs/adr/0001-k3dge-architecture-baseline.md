---
Status: Accepted
Supersedes: -
Amended-by:
  - 🅰1 | Core Maintainer | 2026-09-19 | §2 条 8：硬闸契约的声明面从 `.agent/gates.toml` 改为 `.agent/pipeline.toml`（`[checks.*]` + `[gates.*]`），声明面收为一处
Landed-by: src/k3dge/engine/evaluator.py
Date: 2026-08-19
Deciders: Core Maintainer
Note: 修订痕迹见 git 历史。
---

# ADR-0001: k3dge 架构设计与工程治理基线

## 1. 上下文 (Context)
在基于 LLM 的自主编码与 Vibe Coding 流程中，Agent 容易出现跨会话语义漂移、随意修改底层抽象，以及"代码与文档脱节"。
现存方案多依赖 Soft Prompting 约束，缺乏机器层面的确定性硬门禁。

## 2. 决策 (Decision)
构建 `k3dge`——一套轻量级工程治理 Harness。
它基于 Python 3.10+ 标准库（核心零依赖，tree-sitter 为可选 extra），支持"目录契约 + 双向一致性校验 + Git 门禁拦截"。

### 核心架构约束：
1. **标准源码布局**：采用 `src/k3dge/` 布局，按 `engine`、`cli`、`sync`、`templates` 严格划分模块子域。
2. **分层门禁**：
   - L0 结构门禁：spec 章节完整性（正则/结构校验，非字符串匹配）。
   - L1 契约门禁：公开接口签名归一化哈希（内容寻址绑定）。
     - Python 用 stdlib `ast`，TypeScript 用 tree-sitter（可选依赖）。
     - **L1 同时产出符号级 diff**：`GateReport` `--json` 可读，列出增 / 删 / 改名 / 改参的公开符号。
     - 哈希只证「未同步」，符号 diff 证「改了契约」。
     - 形状变化须留人（维护者）写痕迹，见决策点 6；否则仅刷新指纹不算闭环。
   - L2 行为门禁：Verification Matrix 关联真实测试。
     - 执行口径：矩阵测试存在 + `--with-tests` 跑触及域 + `align` 跑 Full Matrix；见 ADR-0004。
     - **矩阵行带稳定 `id` 且可解析到具体测试**：函数名 / marker / 显式 id。
     - 文件在、场景不在即红（属 L0 家族，非定理证明）。
     - 某域公开哈希变化时，跑 `manifest` 中声明 `depends_on` 该域的域测试，而非全仓 pytest。
3. **确定性双向绑定**：代码为源，`spec` 为锁。
   - 任何对 `src/k3dge/<domain>/` 公开接口的改动，必须使 Contract Hash 与代码派生的哈希一致。
     - Contract Hash 在 `docs/specs/<domain>/spec.md`。
   - 哈希是锁，而非自由编辑的真相。
   - spec 的 §1/§3 人读段仅供人与 Agent 阅读，`check` 不解析自然语言。
4. **按 branch 门禁**：校验基准为 `merge-base(main, HEAD)`。
   - code 可先落地，spec 在分支内收敛即可；不做"同 commit 强制绑定"。
5. **确定性自愈**：`k3dge sync` 从代码生成 spec 的接口块（投影）与哈希。
   - 自愈的是投影，不是批准改抽象；`Agent 只审阅不发明` 仍在。
   - 审阅本身没有工具面（属实现，不在本 ADR 展开）。
6. **契约边界的机器消费者（补全规格闸）**：`spec` 的 §1 边界 / §3 不变量 / §4 矩阵必须有消费者，不能只锁 §2 哈希。
   - **域依赖声明**：`manifest.domains[].depends_on` 声明可达依赖方向。
     - engine 机检逆向 import 禁止；将现有 `engine ↛ templates` 的 `TEMPLATE_DRIFT` 特例升为通用规则。
     - `docs/architecture/overview.md` 的依赖图仍是判据，可执行副本在 manifest；见 ADR-0018。
   - **不变量具名（书写约定，未机检）**：§3 每条不变量应具名。
     - 理想上每条都对应某 Verification Matrix 行；有名字无测试 = 结构红。
     - 该「具名不变量须出现在矩阵行」的对应关系当前未机检，仅作书写约定，不阻断。
   - **形状变化留痕**：增 / 删 / 改名 / 改参公开符号属形状变化。
     - 须伴 `CHANGELOG.md ## [Unreleased]` 一行或 `spec` §1 边界句，提及该域与符号；仅刷新指纹不算闭环。
     - 首版为 `WARN` 不阻断，避免合法重构被罚。
7. **TEMPLATE_DRIFT 登记表属 engine，不 import templates**（原独立 ADR，合并入本条）：
   - `PAIRS` 在 `src/k3dge/engine/pairs.py`；`evaluate` 只从本域 import；**禁止** `engine → k3dge.templates`。
   - 比对的是磁盘上的 `templates/assets` 文件（非 templates 包运行时 API）；仅自举仓生效，下游（k3dit 等）跳过。
   - `templates` 仍是脚手架孤岛：`scaffold` 不读 `engine.pairs`；`test_template_sync` 可 import `engine.pairs`（测试不是域运行时依赖）。
   - 不拆第五域；MCP check 与 `milestone align` 都走 `evaluate`，同一把锁。
   - 重开：templates 运行时需读 `PAIRS` 时，把表抽到两边都能 import 的无依赖模块（仍禁止 engine import templates）。
8. **硬闸契约（`.agent/pipeline.toml` 的 `[checks.*]` + `[gates.*]`）**[^🅰1.1]：闸的**声明式阈值/开关**与**编排单元**在此声明；缺省在 `engine/gates.DEFAULTS`（唯一源，必须完整），执行器读契约；配置缺失/坏 ⇒ 回落缺省（**闸不因配置坏而失效**）。
   - 契约只承载**数据**，不含逻辑/表达式（不长第二套判定语言）。
   - **编排单元**：`[checks.<kind>].preconditions` 声明该单元消费的闸 id（全绿才继续）、`actions` 声明 k3dge **内部**动作 id（注册表）、`stages_<phase>` 声明**外部** peer 的 action ref（用角色名，交 `run_action` 走传输链）；两类 id 不混一张词表（ADR-0026 §2.1/§2.7）。`seal` 首批＝`tasks_all_done/audit_closed/evidence_chain/align_pass/guides_filled/adrs_all_accepted/adr_landed`。未实现的 id 视为配置错（拒绝）。
   - **ADR＝事实源**：封版要求范围内 ADR 全 `Accepted` 且各带**可解析落地指针** `Landed-by: <路径> [§节]`（`engine/adr_gate`）；只验结构事实，不判决策内容（归 k3dit）。
9. **实现语言基线（Rust 重写否决）**：保留 Python 3.10+ 标准库（核心零依赖），**不 Rust 重写**。
   - 依据尖刀实验（`../k3dge-contract-rs` Phase-1/2/3）：Rust 护栏（漏一分支＝编译错 `E0004`）**只在"自有闭枚举且无 `_` wildcard"时成立**；在**解析外部语言语义**（contract 提取：公开签名归一化哈希）上**不成立**且成本高（需自造 `ast.unparse` 等价 + tree-sitter crates，破零依赖）。
   - 护栏纪律**以 CI 级完备性检查近似吸收**（零依赖、3.10）：自有状态机声明为 `Transition` 表 + 显式 `TERMINAL_STATES`，`engine/state_machine.check_completeness` 在 pytest/`check` 里检**终态/死锁/确定性/目标合法/可达**；消费者走 `resolve()`（**表驱动＝无手写分支可漏**）。**保证面＝commit/CI（非编译期，不引类型检查器）**；只护**声明表**，手写 `match/if` 的消费点不在保护面。
   - 重开：仅当**自有状态机/契约**抽为独立 crate 且证明收益 > 多语言碎片/构建成本时，另立 ADR（不复用本条）。

本 ADR 只定实现；目的语言（减少漂移、幻觉、修局部坏整体等，不必穷举）见 ADR-0009。

## 3. 产生后果 (Consequences)
- **正面影响**：阻断 LLM 的无意识抽象破坏；跨会话状态下 100% 可追溯的规格说明书。
- **负面影响 / 权衡**：变更公开接口需额外跑一次 `k3dge sync`；跨语言契约校验依赖可选 tree-sitter 依赖。
- **何时重开**：要把质量/审计/检索做成门禁出口码，或 L1 从签名哈希扩到函数体。
  - 在那之前，不把透镜或语义检索长进 `src/k3dge`。

---

[^🅰1.1]: 修改：声明面从 `.agent/gates.toml` 改为 `.agent/pipeline.toml`。理由（实测）：仓内曾并存两处编排声明——`.agent/gates.toml`（阈值 + `[checks.*]`）与 `pipeline.toml` 的 `[pipelines.on_seal_enter/on_pre_seal].stages`；后者**只有 schema 校验、没有任何执行者**（AGENTS.md §12 却声称它驱动必做审计，缺 §13 的"到达"环），前者本仓已删（曾是 `DEFAULTS` 的冗余副本且漂移过：覆盖列表漏了 reconcile ⇒ 功能静默死亡）。收敛为一处后：`.agent/gates.toml` 若仍存在 ⇒ `PIPELINE_SCHEMA_INVALID` 红一次逼迁移（不静默忽略）；`[pipelines.*]` 同为迁移守卫。不变量未变（缺省完整、坏配置回落、未知 id 拒绝、契约只承载数据）。
