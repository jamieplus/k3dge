# 协议路由：ProtocolResolver 分层 fallback + 路径重叠不变量

- **Status**: done
- **Priority**: P2
- **可检索摘要**: 落地归档 memo 路径路由/写入口收敛的设计：按路径解析协议（注册协议 → base 两层 fallback，取消普通 `README.md` 注入），并在 `validate_protocols_config` 加路径重叠不变量（特异度三元组 + 最长前缀优先；同特异度平局判 `PROTOCOL_REGISTRY_INVALID`），把"目录职责不重叠"从口头约定变 gate 红叉。
- **上下文/切入点**: 源自归档 memo 2026-08-27-vibe-coding-controllable「路径路由」「写入口收敛」节；与 git 门禁 task（2026-08-28-feat-git-gate-landing）正交，故拆出独立跟踪。
- **触发条件**: 无（已确认做）。
- **Date**: 2026-08-28

## 方案
### 物理隔离：k3dge 作为 agent 唯一文件 IO 中介（本层核心机制）
- agent 不经 k3dge 不得直接读/写/搜文件——实现 memo 原「agent 不直接碰权威存储」的物理隔离意图（raise-cost 层面：默认走受控面，裸操作由本地 hook + CI 兜底，不追数学 0 绕过）。
- 受控 IO 面（全 IO 中介，参数用**真实相对路径**，无需逻辑虚拟化）：
  - `k3dge get <real-rel-path>`：返回内容并注入该路径协议上下文（强调注意力）。真实相对路径本就含 zone 信息，k3dge 直接路由协议注入，**无需逻辑↔真实映射表**。
  - `k3dge edit`/`put <real-rel-path>`：接收改动写回，在 IO 边界触发 attend 校验与流程票据。**写的收益在防破坏（硬隔离）**。
  - `k3dge search`：**合并 `find`，用 `--path <glob>` 区分路径列举模式**（默认文本检索）。**降噪硬约束：默认回 `path:line: snippet`，snippet = 命中行 + 窄上下文窗口（默认 `-C 2`，总宽截断 ~5 行 / ≤240 字符），禁止大段上下文展开（`-C` 不得 >3）**——grep 噪声根因是 `-C 10` 把整段函数/类灌进 context；窄窗口既切断噪声又让 Agent 在搜索阶段鉴别命中、避免纯坐标导致的 `get` 往返膨胀（Context Ping-Pong，审计 k3d9e 张力 3 采纳）。`--no-snippet` 退回纯坐标（极限模式）。
- 上下文聚焦靠 **get 时路径路由注入**（真实路径已携带 zone），不靠另建命名空间；契合「强调注意力、防 Context Dilution」。统一经 k3dge 最一致，代价是 IO 面实现成本上升（get/put/edit/search 命令）。
- 与 branch git 的关系：分支隔离（memo A，已否）同源于"物理隔离"意图，但手段是 git 分支（重、留痕）。本中介手段更轻、且覆盖读+写+搜全链路，坐实「分支隔离意图对、实现错」的结论。门禁 task #4 的 attend/流程票据发行时机前移至 IO 边界（get/edit），而非仅 commit。
- **OS 级隔离归宿主 harness**：Codex/Claude Code/OpenCode 等本身提供 OS 沙盒；k3dge 定位 sidecar、不拥 runtime（ADR 0006），不做内核隔离。故「agent 不知真实路径 / 结构 0 绕过」由 harness OS 沙盒覆盖，k3dge 逻辑层不重造（不建虚拟命名空间、不定义逻辑路径空间），IO 中介统一用真实相对路径参数。

### ProtocolResolver 分层 fallback
入口永远先做"找规范"：1) 有协议配置（`.agent/protocols.toml` 的 `[paths]`/`[protocols]` 命中）→ 读注册协议文件；2) 无配置或目录无显式协议 → 无协议，走 base spec。
- **取消普通 `README.md` 协议注入**（审计 a3/R2 采纳）：真实仓库目录 `README.md` 多为人类安装说明/业务闲聊，缺乏结构化协议格式，默认注入会致 Context Dilution 与 Prompt 投毒。仅允许命名为 `.agent/protocol.md` 或在 `protocols.toml` 显式登记的文档作为协议源；无显式协议直接 Fallback 至 base spec。

### 路径重叠不变量（特异度三元组 + 最长前缀优先）
目录职责不重叠是正确性前提（审计 a1/LATTICE-01 + a2 反过度设计 采纳）：
- **特异度三元组（Specificity Tuple）**：对每条 glob 计算 `Specificity = (LiteralSegmentsCount, -WildcardSegmentsCount, PathDepth)`；命中多规则时**最长前缀/最高特异度优先（first-match-wins 取最具体者）**，如 `src/**` 与 `src/auth/**` 对 `src/auth/x.py` 取后者（父提供基础、子特化，无歧义）。
- **仅同特异度精确平局才判 `PROTOCOL_REGISTRY_INVALID`**：两个 glob 特异度三元组完全相同且重叠命中同一文件（真·同级冲突）时 gate 红；其余按最高特异度确定性选一，**不引入偏序半格 / 反链代数求解**（a2 判定该形式化为理论自嗨、报错反人类，推翻 a5/二 的 `PROTOCOL_REGISTRY_AMBIGUOUS_LATTICE`）。
- **等价类分治（审计 k3d9e-a4 诊断 4 采纳）**：`validate_protocols_config` 按特异度三元组划分等价类 $C_k = \{r \mid Specificity(r)=k\}$；仅对 $|C_k|>1$ 的同特异度组内做 GlobSet 重叠命中扫描，单元素等价类直接跳过，避免全量 $O(|R|^2)$ 盲目两两判定（R≤30 下性能可忽略，纯清晰度收益，无新增数据结构）。
- 布局不干净的仓库（真·同级冲突）退回显式 task_type，不硬走路径。校验须用 `git ls-files -c -o --exclude-standard`（含未暂存新建文件，LATTICE-01 采纳）+ 编译态 GlobSet 单次遍历（O(N×M) 优化），并对 `.agent/protocols.toml` 自身哈希做缓存，仅配置变更或 CI 全量模式才跑完整检测。

### 因果衔接（与门禁 task 的前后手）
本 task 是 **rule 的维护与执行层**：按路径加载独有上下文强调注意力，保证文档正确性并分层 fallback（注册→base），使 agent 按 rule 办事（全路径通用软引导）。门禁 task（2026-08-28-feat-git-gate-landing）#4 票据是本 task 之后的 **硬控层**：当 rule 被违反时验证办事者是否知会 rule（attend）与 rule 是否执行。resolver 对每个 zone 输出 `require_attend: bool`（高危协议区 audit/verify 标 true），即**因果节点**——软引导全路径生效，硬控仅对该标志为 true 的 zone 触发，不自重定义受保护区。两 task 是因果前后手，非解耦。

## 文档空间协议分级治理（审计 k3d9e-a6 采纳）
按「该路径能否被 AST/哈希/正则硬门禁 100% 咬住、且 Agent 极易写出伪合规退化产物」的尺子对文档空间分级：

- **Tier 1（必须配 Protocol，history 已发真实事故）**：`docs/adr/**`（撞号 ADR 0016/0019）、`docs/incidents/**`（伪复现 / B-T-D 缺失）、`docs/tasks/**`（摘要截断回归 `INC-20260826-REG-m3-task-truncate`）、`docs/protocols/**`（四件套脱节 `INC-20260827-AST-template-sync-protocols`）。均 `require_attend: true`。
- **Tier 2（建议轻量，选配）**：`docs/branches/**`、`docs/memo/**`（结构化较弱，按需）。
- **Tier 3（禁止配 Protocol）**：`docs/generated/**`（机器生成、禁手改）、`docs/specs/**`（L0+L1 硬门禁）、`docs/guides/**`（人类导读、非 SOP）、`docs/architecture/**`（ADR 驱动、低频）。

默认协议注册（与既有 `audit_default.md`/`verify_default.md` 同公约）：

| 路径 | task_type | 默认协议文件 |
| --- | --- | --- |
| `docs/reviews/**` | audit | `docs/protocols/audit_default.md`（已存在） |
| `tests/**` | verify | `docs/protocols/verify_default.md`（已存在） |
| `docs/adr/**` | adr | `docs/protocols/adr_default.md`（待建） |
| `docs/incidents/**` | incident | `docs/protocols/incident_default.md`（待建） |
| `docs/tasks/**` | task | `docs/protocols/task_default.md`（待建） |
| `docs/protocols/**` | protocol | `docs/protocols/meta_protocol.md`（待建） |

**`## Constraints` 机检/散文二分（关键）**：协议文件的 `## Constraints` 仅承载**机检项**（如 frontmatter 必填字段、`Status/Priority` 枚举、ADR 编号唯一性断言），供 `ProtocolResolver.expected_constraints` 抽取并机验；**叙事质量项**（B-T-D 证据链、5 Whys 根因、自包含可检索摘要）以协议散文承载、advisory 不机检——避免把不可机检项伪装成可机检而制造"伪合规"（正合上述尺子）。

## 实现清单
1. `ProtocolResolver`：按路径返回协议（注册→base；`.agent/protocol.md` 或显式登记文档为协议源，禁止普通 `README.md`）。
2. `validate_protocols_config` 路径重叠不变量：按 `Specificity = (LiteralSegmentsCount, -WildcardSegmentsCount, PathDepth)` 计算每条 glob 的特异度三元组，按三元组划分等价类仅对同组做 GlobSet 重叠命中扫描；**同三元组且重叠命中同一文件 → `PROTOCOL_REGISTRY_INVALID`**，否则最长前缀/最高特异度优先确定性选一（不引入半格/反链判定）。**注意（盲区 3 校准）**：当前 `engine/protocol.py` 的 `validate_protocols_config` 仅校验文件存在与 path 映射合法性，**尚未实现三元组与平局判定**，编码期须补齐该机制，否则下方验收「故意重叠布局报红」无法通过；且验收用例中的平局示例本身须修正（见验收第 3 条）。
3. `k3dge get <path>`：受控读 + 注入协议上下文（IO 边界强调注意力）。
4. `k3dge search`：受控搜索/列举（合并原 `find`，`--path <glob>` 走路径列举模式；替代裸 grep/ls，补齐物理隔离）。默认回 `path:line: snippet`（命中行 + 窄上下文 `-C 2`，总宽截断 ~5 行 / ≤240 字符）；`--no-snippet` 退回纯坐标，`-C` 可调上限 3（见上方硬约束）。
5. `k3dge where <symbol>`：符号级确定性寻址（替代"虚拟路径树"被否后丢失的快速寻址能力）。索引由 `engine/search.py` 维护，返回 `file:line`，零模型判断、零 grep 发现成本——这正是虚拟路径树承诺的"按名定位"，但建在真实路径 + 索引之上，不重映射命名空间。
   - 寻址 → 降噪 的完整闭环：**定位（`where`/`search` 只回坐标，低噪）→ 加载（`get <path>` 只加载真正要改的那一个文件，并注入协议上下文）**。受控 IO 面统一经 k3dge，agent 不裸跑 grep/ls。
6. `k3dge edit`/`put <path>`：受控写（IO 边界触发 attend/流程票据，见门禁 task #4）。
7. **文档空间协议分级治理（审计 k3d9e-a6 采纳）**：扩展 `.agent/protocols.toml` 注册 `adr`/`incident`/`task`/`protocol` 四类默认协议（路径 `docs/adr/**`、`docs/incidents/**`、`docs/tasks/**`、`docs/protocols/**`，均 `require_attend: true`），并新建 `docs/protocols/adr_default.md`、`incident_default.md`、`task_default.md`、`meta_protocol.md`（与既有 `audit_default.md`/`verify_default.md` 同公约）；各文件 `## Constraints` 仅载机检项，叙事质量项作 advisory 散文（见下方分级治理节）。**「四件套同步」锁（盲区 1 校准，防 `INC-20260827-AST-template-sync-protocols` 退化）**：新建 4 份协议时须成对改动四处——① 写入 `src/k3dge/templates/assets/protocols/` 资产；② 在 `engine/pairs.py` 的 `PAIRS` 追加 4 对映射（字节锁）；③ 更新 `templates/scaffold.py` 的写入逻辑（当前 `PROTOCOL_TEMPLATE` 仅硬编码 `audit_default.md`，须为 4 份新增 + **既有的 `verify_default.md`** 各加 `_write_if_missing` 调用，消除已存在的部分漂移）；④ 更新 `tests/unit/templates/test_template_sync.py` 的 `expected` 预期清单计数。任何一处遗漏即触发 `TEMPLATE_DRIFT` 红闸。

### 代码落位（对齐现有域）
- `ProtocolResolver` + 重叠不变量 + `require_attend` 输出 → **`engine/protocol.py`**（文件已存在，扩写非新建）。
  - **路径解析（规模适宜，不做 trie 过度优化，审计 k3d9e 张力 4 采纳）**：规则集通常仅数十条，`[paths]` 解析用**按特异度排序的线性匹配**（O(M)，微秒级）即可，"最长前缀优先"由 Specificity Tuple 降序取首命中实现；CLI 冷启动（30~50ms）远大于此，前缀树/符号 trie 的渐进增益被启动耗时吞没，属微观优化倒挂，故不引入树结构。
- **寻址与受控搜索 → 新建 `engine/search.py`**（单一 owner，勿堆 cli）：`build_symbol_index(workspace)` 扫描 `manifest` 各域 `src`（复用 `engine/contract.py` 的顶层符号提取器）产出 `docs/generated/symbol-index.json`；`where(workspace, symbol) -> list[Location]` 查索引返回 `file:line`；`search(workspace, query, *, snippet: bool = True, context: int = 2, max_snippet: int = 240) -> list[Location]` 封装 ripgrep，默认回 `path:line` + 窄上下文窗口（匹配行 ±`context` 行，总宽截断 `max_snippet` 字符），`snippet=False` 仅回坐标（审计 k3d9e 张力 3：窗口防 Ping-Pong、上限 `context≤3` 防噪声）。`Location` 为 `file: str` + `line: int | None` + `snippet: str | None` 的轻量结构。
  - **索引形态（采纳 a2 反过度设计 / 推翻 a5/四）**：仅存 `symbol -> (file, line)`，不引入 AST 锚点（`ast_path_hash`/`relative_offset`）——跨语言 AST 运行时属过度工程；行号漂移由 `k3dge sync` 增量刷新（按文件 blob sha，PERF-01 采纳）兜底，Agent 经 `k3dge get` 取全文自行定位。
  - **符号索引查询（不做 trie，审计 k3d9e 张力 4 采纳）**：`where` 走 hash 查表（O(1) 已最优）；前缀/`search --path` 查询规模极小，线性过滤即可，不建符号 trie，避免树遍历复杂度。
- 索引再生：接入 `k3dge sync`（与既有 `docs/generated/` 机器文档同出口），或独立 `k3dge index` 子命令；CI 全量模式重算，`sync` 增量复用缓存。
- IO 中介命令（`get`/`search`/`where`/`edit`/`put`）→ **`cli` 子命令（薄封装）**，FS 逻辑落 `engine`（勿堆 cli）；`search`/`where` 调 `engine/search.py`，`get`/`edit`/`put` 调 `engine/protocol.py` 做路径→协议路由。
- 会话清单（`attended_zones` 维护）读写 → **`engine/marker.py` 统一归属**（单一 owner，轻量无状态机），跨本 task 与门禁 task 代码层合一，避免 cli/engine 各写一半。

## 验收
- resolver 对给定路径返回正确协议层；
- 故意制造重叠布局，config 校验报红（`PROTOCOL_REGISTRY_INVALID`）。
  - 通配符存在**特异度阶梯**时按最高特异度确定性选一、不报错（如 `src/modules/**` → (2,-1,3) 与 `src/modules/user/handler.py` → (4,0,4) 同命中 `src/modules/user/handler.py`，前者三元组小于后者，确定性取更具体者）；**仅当两 glob 特异度三元组完全相同且重叠命中同一文件才是严格平局，报 `PROTOCOL_REGISTRY_INVALID`**（修正原用例中 `src/modules/*/handler.py` 与 `src/*/user/handler.py` 同取 (3,-1,4) 却写「确定性选一」的自相矛盾，盲区 3 校准）。
- `k3dge where <已知顶层符号>` 返回精确 `file:line`（来源 `symbol-index.json`，无 grep 发现调用）。
- `k3dge search <意图词>` 默认回 `path:line: snippet`（命中行 + `-C 2` 窄窗口，总宽 ≤~5 行/240 字符），足以在搜索阶段鉴别命中、避免 `get` 往返；**禁止** `-C >3` 的大段上下文灌入（噪声断言 = 上下文窗口不得 >3 行）。
- `k3dge search --no-snippet` 仅回 `path:line` 坐标集合（极限模式，一行一坐标，无内容）。
- 索引可重现：`k3dge index`（或 `sync`）重跑后 `symbol-index.json` 内容确定（同输入同输出，除时间戳外）。
- `resolve_by_path` 按 Specificity Tuple 降序取首命中（最长前缀优先），规则集规模下为 O(M) 微秒级，不引入树结构（审计 k3d9e 张力 4 采纳）。

## 审计采纳回填（两轮穿透审查 · 最终判定）
本 task 经两轮审计（a 轮推崇形式化、b 轮反过度设计），最终以「取舍判断」收口：
- **采纳 a3/R2 取消普通 `README.md` 协议注入** → `注册协议 → base` 两层。
- **采纳 a3/一.3 合并 `search`/`find`** → 统一 `k3dge search`（`--path` 走列举），裁撤 `find`。
- **采纳 a1/LATTICE-01** → 重叠扫描改用 `git ls-files -c -o --exclude-standard`（含未暂存新建）。
- **采纳 a2 反过度设计（推翻 a5/四）** → 删除 AST 锚点（`ast_path_hash`/`relative_offset`），索引仅 `symbol -> (file, line)`，漂移靠 `sync` 增量刷新（PERF-01 采纳：按文件 blob sha 增量）。
- **采纳 a2 反过度设计（推翻 a5/二 的半格）** → 删除 `PROTOCOL_REGISTRY_AMBIGUOUS_LATTICE` 与偏序半格代数；保留 Specificity Tuple + 最长前缀优先，仅同特异度平局报 `PROTOCOL_REGISTRY_INVALID`。
- **搜索降噪折中（融合 a 轮 R5 与 b 轮 Ping-Pong 批评）** → 默认 `path:line: snippet`（窄窗口 `-C 2`、总宽 ≤5 行），`--no-snippet` 退回纯坐标（避免 `get` 往返膨胀）。
- **采纳 k3d9e 张力 3** → 搜索默认给窄上下文窗口（非严格单行），在搜索阶段即可鉴别命中，消 Ping-Pong。
- **采纳 k3d9e 张力 4（推翻上轮自加的 trie）** → 规则基数极小，CLI 冷启动吞没树优化增益；`resolve_by_path` 退回按 Specificity Tuple 降序线性匹配，不建 radix/symbol trie。
