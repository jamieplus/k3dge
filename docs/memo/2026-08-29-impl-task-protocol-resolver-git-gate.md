# Memo：Protocol Resolver + Git Gate 两 Task 实现全记录（2026-08-28 双任务落地）

- **Date**: 2026-08-29
- **类型**：实现记录（非闪念；对应 `docs/tasks/2026-08-28-feat-protocol-resolver.md` 与 `docs/tasks/2026-08-28-feat-git-gate-landing.md`，两文件 `Status` 已置 `done`）
- **触发场景**：用户要求"把两个 task 里所有任务落地"，并"把从上至下的所有细节记入一篇 memo"
- **范围**：协议路由（resolver / 重叠不变量 / IO 中介命令 / 索引搜索）+ 一致性门禁（commit 封装 / attend 两阶段 / 会话清单 / 哨兵）

---

## 1. 执行轮次（自决顺序）

1. **协议资产落地**：4 份 Tier1 协议（`adr/incident/task/meta_protocol`）写入 `docs/protocols/` 与 `assets/protocols/`（字节一致），同步 `pairs.py` / `scaffold.py` / `test_template_sync.py` / `.agent/protocols.toml`（四件套锁，含修复既有的 `verify_default.md` 漏写 scaffold 漂移）。
2. **protocol.py**：补 `require_attend` 输出；实现特异度三元组 + 同三元组重叠平局 → `PROTOCOL_REGISTRY_INVALID`（盲区 3 核心缺口）；resolver 按三元组降序取首命中。
3. **marker.py（新建）**：会话清单单一 owner；`epoch_id` 自治；`attended_zones` 仅正解写入；SEC-01 路径逃逸拦截；原子写。
4. **search.py（新建）**：符号索引 `build_symbol_index` / `where` / `search`（ripgrep + python 兜底，snippet 窗口钳 ≤3 行）。
5. **evaluator.py**：加 `staged` 模式（`_staged_files`）。
6. **cli/main.py**：新增 `get/search/where/edit/put/index/end/commit/incident` 子命令；`protocol attend` 动作；`check --staged`；`search --path` 列举模式。
7. **sentinel 脚本 + 接入**：`scripts/pre-commit-sentinel.sh`，scaffold 非破坏式安装到 `.git/hooks/pre-commit`；`.gitignore` 忽略 `session.json`。
8. **测试 + 验证**：单测 + 端到端（临时仓库）验证；`k3dge sync` 更新 contract hash。

---

## 2. 逐模块细节

### 2.1 `src/k3dge/engine/protocol.py`
- `ProtocolRef` 新增字段 `require_attend: bool = False`；`resolve()` 命中协议时固定置 `True`（设计判断：所有已注册协议即 Tier1 `require_attend` 区，无需在 `protocols.toml` 另开 `[require_attend]` 段）。
- 新增模块级 `specificity(pattern) -> (LiteralSegments, -WildcardSegments, PathDepth)`：按 `/` 切段，`*`/`**` 计为 wildcard。例 `src/modules/*/handler.py` → `(3,-1,4)`；`src/modules/**` → `(2,-1,3)`。
- `_match_path()` 由原先 `pat.count("/")` 改为按 `specificity()` 三元组降序取首命中（平局由 `validate` 拒绝，resolver 永不面对歧义）。
- 新增 `_repo_files(workspace)`：`git ls-files -c -o --exclude-standard` 优先，失败则回退 `rglob("*")` 排除 `.git`/`.tmp`（保证无 git 的测试目录也能扫描）。
- `validate_protocols_config()` 末尾新增**等价类分组 + 重叠扫描**：按 `specificity` 分桶，仅 `|Ck|>1` 的同三元组组内，对仓库真实文件做 `fnmatch` 重叠命中；任一文件被 ≥2 个同组 glob 命中即报 `PROTOCOL_REGISTRY_INVALID`。不同三元组的重叠由 resolver 按"最高特异度"确定性选一，不报红。本仓 `docs/adr|incidents|tasks|protocols/**` 虽同三元组 `(2,-1,3)` 但前缀互斥，零误报（已用 `test_valid_config_passes` 回归）。
- 既有 `challenge/expected_constraints/validate_ticket/verify/write_incident` 未动；`attend` 答案校验逻辑下沉到 `marker.py` + CLI。

### 2.2 `src/k3dge/engine/marker.py`（新建）
- 常量 `SESSION_ID_RE = ^[A-Za-z0-9_-]{1,64}$`；`session.json` 结构 `{session_id, epoch_id, epoch_started_at, attended_zones:[{zone,epoch}]}`。
- `_safe_rel(workspace, zone)`：SEC-01，`(workspace/zone).resolve()` 必须落在 `workspace` 内，否则 `ValueError`（`../` 遍历 / 软链逃逸拦截）。
- `_atomic_write`：`os.replace(tmp, target)` 防中断半截 JSON。
- `ensure_epoch(workspace, epoch_id=None)`：`epoch_id` 缺省时生成 `uuid4().hex[:8]`；若既有 epoch 超过 `_EPOCH_TTL_SECONDS=3600` 视为 stale 自动轮换；返回当前 `epoch_id`。
- `register_attendance(workspace, zone, answer, expected, epoch_id=None) -> (ok, epoch)`：**仅当 `answer == expected` 才写入** `attended_zones`（绝不"访问即写"，否则退化为无意义访问日志）。
- `is_attended` / `attended_zones`：按 `epoch` 过滤，保证跨 compaction / 子代理失忆不沿用旧轮次凭证。
- `reset_session`：`k3dge end` / 超时清空（删文件，下次 `ensure_epoch` 重新生成）。

### 2.3 `src/k3dge/engine/search.py`（新建）
- `Location` dataclass：`file / line / snippet` + `render()`（`file:line: snippet` 或 `file:line`）。
- `_domain_src_dirs(workspace)`：优先读 `manifest` 各域 `src`；无 manifest 时回退扫描 `src/<pkg>/`（含 `__init__.py`）——保证测试仓库与下游仓库都能建索引。
- `build_symbol_index`：遍历各 `src` 树 `.py`，`ast.parse` 取顶层**公有** `def/class`（非 `_` 前缀）的 `(name, lineno)`，产出 `{symbol:[{file,line}]}`。
- `write_symbol_index` 落 `docs/generated/symbol-index.json`（sort_keys，可重现）；`where(workspace, symbol)` 直接查索引返回 `file:line`，零 grep 发现、零模型判断。
- `search(workspace, query, snippet=True, context=2, max_snippet=240)`：优先 `_run_ripgrep`（`rg -n --with-filename`，`-C` 钳制 ≤`_MAX_CONTEXT=3`），无 `rg` 则 `_python_search` 兜底；`_snippet_window` 取命中行 ±context 行、总宽截 ≤240 字符，杀 Context Ping-Pong。

### 2.4 `src/k3dge/engine/evaluator.py`
- 新增 `_staged_files()`：`git diff --cached --name-only --diff-filter=ACMR`（超时/缺失返回 `[]`）。
- `evaluate(..., staged=False)`：`staged=True` 时文件集取 `_staged_files()` 而非全量 `get_changed_files`；后续 domain/version/template/protocol/pipeline 校验照常跑。

### 2.5 `src/k3dge/cli/main.py`
- 模块级：`_CONV_RE`（Conventional Commits 校验）、`_conventional_ok(msg)`、`_rel_within_workspace(workspace, p)`（SEC-01 复用 marker 思路）。
- `cmd_get`：解析路径→`resolve_by_path` 注入协议全文（若存在）→ 读文件内容 → 打印随机 `TASK_ID`（agent 据此本地算 `sha256(normalize(protocol)+task_id)[:12]`）。**不接收 `--answer`**（盲区 2 时序：get 仅发题）。
- `cmd_search`：`--path <glob>` 走列举模式（`workspace.glob` 列文件，替代 `find`）；否则调 `engine.search.search`，`--no-snippet` 退回纯坐标，`--context` 默认 2（钳 ≤3）。
- `cmd_where`：调 `search.where`，无命中返回 rc=1。
- `cmd_edit`：逐文件 `resolve_by_path`；`require_attend` 区注入协议 + 打印 `TASK_ID` 与 `attend` 口令提示（触发 attend 边界，不维护编辑清单）。
- `cmd_put`：从 stdin 读内容；`require_attend` 区强制 `--answer`，重算 `challenge` 比对，不符则拒写；正解经 `marker.register_attendance` 记录后原子 `os.replace` 写回（自闭环幂等）。
- `cmd_index`：`write_symbol_index`。`cmd_end`：`marker.reset_session`。
- `cmd_commit`：①`git add -A`(`-a`)/`git add -- <files>`（GIT-01 `--` 隔离）；②`_conventional_ok` 校验；③单点 attend 校验——遍历 staged 中 `require_attend` 区，未 `is_attended` 则 stderr 告警 + `write_incident` 产 L2（**软，不阻断**）；④`ConsistencyEngine(...).evaluate(staged=True)` 硬闸，不过则返回 1；⑤`git commit -m <MSG> --no-verify` 带 `env K3DGE_COMMIT_ACTIVE=1`（内部 check 已覆盖 ≥ hook，CI 兜底）。
- `cmd_incident`：`--from-ci <json>` 或 stdin 读 `{path,task_type,task_id,detail}` → `write_incident`。
- `cmd_protocol` 新增 `attend` 动作：算 `challenge(target, task_id)` 与 `--answer` 比对，正解调 `marker.register_attendance`（支持 `--epoch-id` 显式传入，缺省由 marker 自举）。
- parser：新增 9 子命令；`protocol` 动作加 `attend` 与 `--answer`/`--epoch-id`；`check` 加 `--staged`；`search` 加 `--path`。

### 2.6 `src/k3dge/templates/scaffold.py`
- 新增 `SENTINEL_TEMPLATE = _asset("pre-commit-sentinel.sh")`；`scaffold()` 写入 `scripts/pre-commit-sentinel.sh`（可执行）。
- 新增 `_install_sentinel_hook(target)`：仅当 `.git/hooks/pre-commit` 不存在时拷贝并赋执行位（**非破坏式**，不覆盖既有 hook）。
- 协议写入补齐：`VERIFY/ADR/INCIDENT/TASK/META` 模板常量 + 6 份 `_write_if_missing`（修复 `verify_default.md` 旧漂移）。

### 2.7 同步锁与清单
- `engine/pairs.py`：`PAIRS` 新增 `pre-commit-sentinel.sh` + 4 份协议（audit/verify 已在）。
- `tests/unit/templates/test_template_sync.py`：`expected` 清单补 `pre-commit-sentinel.sh` + 4 协议。
- `.gitignore`：追加 `.agent/session.json`（本地凭证不入库，防多开发者/CI 脏状态）。
- `.agent/protocols.toml`：`[protocols]` 注册 `adr/incident/task/protocol`；`[paths]` 注册 `docs/adr|incidents|tasks|protocols/**` → 对应 type（默认 `audit`）。

### 2.8 `scripts/pre-commit-sentinel.sh`（新建）
- 一行哨兵：`K3DGE_COMMIT_ACTIVE != "1"` 即 `echo Forbidden...` + `exit 1`；`k3dge commit` 内部置位后放行。

---

## 3. 我替你拍板的设计决策（确认类）

1. **`require_attend` 取"命中即 True"**：未引入 `protocols.toml` 的 `[require_attend]` 段（resolver 当前无该字段解析），所有已注册协议即 require_attend 区。如需分协议细化，后续加段即可。
2. **epoch 自举**：`epoch_id` 缺省 `uuid4().hex[:8]`；`session_id` 缺省 `"sess-"+8hex`；TTL 3600s 硬编码常量。SEC-01 校验对象是 `zone` 路径（外部不可注入 `session_id`，故不校验它）。
3. **attend 时序严格两阶段**（盲区 2）：`get` 只发题（协议 + `TASK_ID`），`--answer` 仅经 `attend`/`put`/`edit` 在阶段 2 提交；`get --answer` 不存在。
4. **commit 的 attend 校验为软**（原 ADR 0022，已随 ADR-0019 废弃；attend/load-proof 机制整体移除）：缺凭证仅 stderr 告警 + 产 L2 incident，不阻断；硬阻断在 `check --staged`。
5. **tie 检测扫描真实文件**：用 `git ls-files` 优先 + `rglob` 兜底；本仓同三元组 glob 前缀互斥 → 零误报。
6. **`search --path` 兼作 find 替代**：列举模式与文本模式同一命令，`--no-snippet` 退回纯坐标。
7. **`k3dge sync`**：因新增 `cmd_*` 公有符号与 `search/marker` 新模块改动了 `cli`/`engine` 契约，已运行 `k3dge sync` 重生 `docs/specs/{cli,engine}/spec.md` 的 contract hash（check 由红转绿）。

---

## 4. 验证

- **单测**：`tests/unit` 全绿 —— 138 passed / 1 skipped / 73 subtests passed。新增 `test_marker.py`、`test_search.py`，并在 `test_protocol.py` 加 `TestProtocolSpecificityTie`（同三元组重叠报红、梯度不报）。
- **`k3dge check`**：`passed=True, violations=0`（sync 后）。
- **端到端（临时 git 仓库）**：
  - `k3dge init` → `k3dge sync` → `k3dge commit -a -m "chore: scaffold"` 成功；改文件后再 `commit -a` 成功（无 `put` 也不死锁，STATE-01）。
  - 裸 `git commit -m "raw"` 被 `.git/hooks/pre-commit` 哨兵拦截（`Forbidden...`，rc=1）。
  - `get` 发题 → 本地算 sha → `protocol attend --path ... --task-id ... --answer <sha>` 成功写 `session.json`（epoch 自动生成）；错答 `attend` rc=1 不写入。

---

## 5. 已知缺口 / 后续（非阻塞）

- **branch-protection 跨平台文档**：任务清单 #6 提及的"跨平台文档（GitHub/GitLab/...）"属平台配置、非代码产物，未单建文件；CI 硬闸（`ci.yml` 跑 `k3dge check --force-full --with-tests`）已就位，无 auto-revert workflow 可删（本仓原本就无）。
- **epoch TTL / session 结构** 为硬编码常量，未抽配置。
- **`require_attend` 分协议细化**：当前粗粒度（命中即 True），若需 `tests/**` 等豁免，需在 `protocols.toml` 加 `[require_attend]` 段并在 resolver 解析。
- **`docs/generated/symbol-index.json`** 为生成物，当前未纳入 `.gitignore`（与既有 `docs/generated/` 同处理）；如需可加忽略。

---

## 6. 粒度补全（逐文件 / 逐符号 / 逐测试）

### 6.1 文件清单

**新建**
- `src/k3dge/engine/marker.py`（会话清单单一 owner）
- `src/k3dge/engine/search.py`（索引 / where / search）
- `tests/unit/engine/test_marker.py`
- `tests/unit/engine/test_search.py`
- `docs/protocols/{adr_default,incident_default,task_default,meta_protocol}.md`（资产源）
- `src/k3dge/templates/assets/protocols/{adr_default,incident_default,task_default,meta_protocol}.md`（与上式字节一致，过 `PAIRS` 锁）
- `scripts/pre-commit-sentinel.sh`（仓库侧，含可执行位）
- `src/k3dge/templates/assets/pre-commit-sentinel.sh`（资产源）
- `docs/memo/2026-08-29-impl-task-protocol-resolver-git-gate.md`（本 memo）

**修改**
- `src/k3dge/engine/protocol.py`（require_attend / specificity / tie）
- `src/k3dge/engine/evaluator.py`（_staged_files / staged 模式）
- `src/k3dge/cli/main.py`（9 新子命令 + attend 动作 + --staged + --path；`import re` 补丁）
- `src/k3dge/templates/scaffold.py`（SENTINEL 模板 + 安装 + 6 协议写入）
- `src/k3dge/engine/pairs.py`（PAIRS 增 5 项：sentinel + 4 协议）
- `tests/unit/templates/test_template_sync.py`（expected 增 5 项）
- `tests/unit/engine/test_protocol.py`（增 `TestProtocolSpecificityTie`）
- `.gitignore`（增 `.agent/session.json`）
- `.agent/protocols.toml`（增 4 协议 + 4 路径）
- `docs/specs/cli/spec.md`、`docs/specs/engine/spec.md`（k3dge sync 重生 contract hash）
- `docs/generated/symbol-index.json`（运行时生成物）

### 6.2 `.agent/protocols.toml` 最终全文

```toml
[protocols]
audit     = "docs/protocols/audit_default.md"
verify    = "docs/protocols/verify_default.md"
adr       = "docs/protocols/adr_default.md"
incident  = "docs/protocols/incident_default.md"
task      = "docs/protocols/task_default.md"
protocol  = "docs/protocols/meta_protocol.md"

[settings]
default = "audit"

[paths]
"docs/reviews/**"     = "audit"
"tests/**"            = "verify"
"docs/adr/**"         = "adr"
"docs/incidents/**"   = "incident"
"docs/tasks/**"       = "task"
"docs/protocols/**"   = "protocol"
```

### 6.3 四份协议资产全文（约束段）

`docs/protocols/adr_default.md`：
```
# ADR Protocol — Default
> **事实源**：`k3dge` 仅验"文件存在 / 注册一致"（`k3dge check`）；本文件载 ADR 的机检契约，叙事质量由评审保证。
## 交付
`docs/adr/NNNN-<slug>.md`，`NNNN` 为四位零填充序号，全仓唯一；含 `Status` / `Date` 表头字段。
## Constraints
- 文件名满足 `^\d{4}-[\w-]+\.md$` 且序号在 `docs/adr/` 内唯一
- 含表头 `Status`（`∈ {Proposed, Accepted, Deprecated, Superseded}`）与 `Date`（YYYY-MM-DD）
- 含 `## 上下文` / `## 决策` / `## 后果` 三节
- 不得删除或改写已被他处引用的 ADR 编号
```
`docs/protocols/incident_default.md`：
```
# Incident Protocol — Default (B-T-D 证据链)
> **事实源**：`k3dge check` 仅验"文件存在 / 注册一致"；本文件载事故报告的机检契约。
## 交付
`docs/incidents/INC-YYYYMMDD-<TYPE>-<slug>.md`，含 `背景(B)` / `触发(T)` / `处置(D)` 三段与证据链。
## Constraints
- 文件名满足 `^INC-\d{8}-[A-Z]+-[\w-]+\.md$`
- 含 `## 背景` / `## 触发` / `## 处置` 三节（B-T-D 不可缺）
- 含至少一条可机器核验的证据链接（产物路径 / 命令输出 / 消费者引用）
- 文件名日期与文件内 `Date` 一致
```
`docs/protocols/task_default.md`：
```
# Task Protocol — Default (可检索 / 状态机)
> **事实源**：`k3dge` 仅验"文件存在 / 注册一致"；本文件载 task 文档的机检契约。
## 交付
`docs/tasks/YYYY-MM-DD-<type>-<slug>.md`，含 `Status` / `Priority` 表头与「可检索摘要」。
## Constraints
- 含表头 `Status`（`∈ {in-progress, done, cancelled, pending}`）与 `Priority`（`∈ {P0,P1,P2,P3}`）
- 首段含「可检索摘要」段或 `可检索` 关键词
- 文件名满足 `^\d{4}-\d{2}-\d{2}-[\w-]+\.md$`
- 不得声明与既有 task 完全相同的 `Status: done` 重复闭环
```
`docs/protocols/meta_protocol.md`：
```
# Protocol Meta — Default (协议自身契约)
> **事实源**：本文件是"协议之协议"，约束 `docs/protocols/**` 下各默认协议的写法；`k3dge check` 仅验注册一致。
## 交付
`docs/protocols/<type>_default.md`，含 `## Constraints` 机检段与事实源注脚。
## Constraints
- 含 `## Constraints` 段，且仅承载机检项（叙事质量项作 advisory 散文，不伪装成机检）
- 含 `> **事实源**` 注脚，明确 `k3dge check` 与该协议的职责边界
- 文件名满足 `^[\w]+_default\.md$`
- `## Constraints` 下每条机检项以 `- ` 列表项呈现，供 `expected_constraints` 抽取
```
（上述四份均同步写入 `src/k3dge/templates/assets/protocols/`，与 `docs/protocols/` 字节一致。）

### 6.4 CLI 命令签名与参数（新增/改动）

新增 `cmd_*`（`src/k3dge/cli/main.py`，行号见 §6.1）：
- `cmd_get(args)` — `get <path>`：注入协议 + 打印 `TASK_ID`（随机 `uuid4().hex[:8]`），**不收 `--answer`**。
- `cmd_search(args)` — `search <query>`：`--path <glob>` 走列举（替代 `find`）；否则文本检索，`--no-snippet` 纯坐标，`--context` 默认 2（钳 ≤3）。
- `cmd_where(args)` — `where <symbol>`：索引查 `file:line`，无命中 rc=1。
- `cmd_edit(args)` — `edit <files...>`：逐文件注入协议 + 打印 `TASK_ID` 与 `attend` 口令提示。
- `cmd_put(args)` — `put <path>`：`--answer`/`--task-id`/`--epoch-id`；stdin 读内容，require_attend 区比对 challenge，正解调 `marker.register_attendance` 后 `os.replace` 原子写。
- `cmd_index(args)` — `index`：写 `docs/generated/symbol-index.json`。
- `cmd_end(args)` — `end`：`marker.reset_session`。
- `cmd_commit(args)` — `commit`：`-m/--message`(必填) / `-a/--all` / `--with-tests`；流程见 §2.5。
- `cmd_incident(args)` — `incident`：`--from-ci <json>` 或 stdin，载荷 `{path,task_type,task_id,detail}`。

改动：
- `cmd_protocol` 新增 `attend` 动作（`choices` 增 `"attend"`），新增 `--answer`、`--epoch-id` 参数；逻辑：算 `challenge(target,task_id)` 与 `--answer` 比对，正解调 `marker.register_attendance`。
- `cmd_check` 透传 `staged=getattr(args,"staged",False)` 至 `evaluate`。
- `p_check` 增 `--staged`；`p_search` 增 `--path`；`p_protocol` `protocol_action` choices 增 `attend`。

### 6.5 测试清单（逐方法）

`tests/unit/engine/test_marker.py`：
- `test_epoch_auto_generated_when_absent` — 缺省 epoch 自举为 8 位 hex，session_id 匹配白名单。
- `test_attendance_only_on_correct_answer` — 正解写入并 `is_attended` 为真；错解不写入。
- `test_session_reset_clears` — `reset_session` 删除 session.json。
- `test_escape_path_rejected` — `../escape.md` 触发 `ValueError`（SEC-01）。

`tests/unit/engine/test_search.py`：
- `test_where_returns_file_line` — `where("top_level")` 命中且 `line` 非 None。
- `test_search_returns_snippet` — `search("def top_level")` 返回带 snippet 的 Location。
- `test_search_no_snippet_coords_only` — `snippet=False` 时全部 `snippet is None`。
- `test_build_index_shape` — `build_symbol_index` 含 `top_level` 且 `line==1`。

`tests/unit/engine/test_protocol.py` 新增 `TestProtocolSpecificityTie`：
- `test_same_specificity_overlap_flags` — `src/modules/*/handler.py` 与 `src/*/user/handler.py` 同 `(3,-1,4)` 且重叠于 `src/modules/user/handler.py` → `PROTOCOL_REGISTRY_INVALID`。
- `test_specificity_gradient_no_tie` — `src/modules/**`(2,-1,3) 与 `src/modules/user/handler.py`(4,0,4) 不同三元组 → 不报红。

### 6.6 实现中踩的坑（已修复）

- **`main.py` 缺 `import re`**：新增 `_CONV_RE = re.compile(...)` 时未导入 `re`，首次 `pytest` 收集即 `NameError`；补 `import re` 于文件头（行 6）后全绿。
- **contract drift → 必须 `k3dge sync`**：新增 `cmd_*` 公有符号 + `search/marker` 新模块改动 `cli`/`engine` 契约，`k3dge check` 先报 `CONTRACT_DRIFT`；运行 `k3dge sync` 重生两 spec 的 contract hash 后转绿。
- **scaffold 旧漂移**：原 `scaffold.py` 仅写 `audit_default.md`，`verify_default.md` 已在 `PAIRS`+assets 却漏写 → 本次补齐 `VERIFY/ADR/INCIDENT/TASK/META` 全部 6 份写入，消除漂移。
- **sentinel 安装条件**：仅当 `.git/hooks/pre-commit` 不存在才拷贝（非破坏式），避免覆盖既有 hook。
- **`cmd_commit` 空 stage**：不带 `-a`/文件时 `git add` 无操作 → 后续 `git commit` 因无 staged 失败；属预期（用户须显式 `-a` 或指定文件），端到端已用 `-a` 验证通过。

