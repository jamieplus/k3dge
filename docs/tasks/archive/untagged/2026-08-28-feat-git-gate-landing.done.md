# 落地 k3dge 一致性门禁：trunk + branch protection + 封装黑盒 + 票据生命周期

- **Status**: done
- **Priority**: P1
- **可检索摘要**: 把 memo 2026-08-27-vibe-coding-controllable 的门禁设计收敛为可实现的落地方案：弃用 git 分支 merge 模型（A 方案），锁定 trunk-based + branch protection + CI gate 为不可绕硬地板；新增 `k3dge commit`/`k3dge edit` 封装黑盒（裸 git 绕过由本地 pre-commit 哨兵 + CI 硬地板拦截，**原「票据生命周期」已收敛为轻量 session 清单**，不再维护 ACQUIRED/STAGED 状态机与残留扫描）；L1/L2 双级 detect/log 闭环；固化本地=快反馈、CI=全量硬门分工。
- **上下文/切入点**: 讨论「本项目 git 用法 vs memo 记录」起，逐层推翻分支隔离先进性，落到工程收益/成本平衡。memo 已归档至 `docs/memo/archive/`。
- **触发条件**: 无（已确认做）。
- **原话备查**: "raise cost + detect，不追求数学 0 绕过"；"票据：改前开标记、commit 末核销，残留即绕过"。
- **Date**: 2026-08-28

## 锁定决策
- 推翻 memo A（git merge 模型）：分支 merge 与 trunk+CI 门禁等价但更重/留痕多/防绕过无需隔离。
- 硬地板 = branch protection（平台无关：GitHub branch protection / GitLab protected branches / Bitbucket merge checks / Azure branch policies / Gitea）+ Require PR + Require `gate` status。不用 server-side pre-receive（SaaS 不可部署）。buffer branch 不采纳。
- 哲学：软关卡 + incident 纸痕（接原 memo line 18），不追数学 0 绕过。

## 方案五块
### #1 提交封装黑盒 `k3dge commit`
接口 `k3dge commit [<files>...] [-m MSG] [-a]`；链：add（`git add -- <files>`，审计 GIT-01 `--` 隔离防 `-` 开头文件名注入）→ 内置 conventional 校验 → **票据单点校验（#4：本次提交涉及 require_attend zone 的 `(zone,task_id)` challenge 验证，STATE-01 兼容直提）** → `k3dge check --staged` → `git commit -m <MSG> --no-verify`（exec list，禁 `shell=True`，置 `K3DGE_COMMIT_ACTIVE=1`）。跳过 hook 安全因内部 check 覆盖≥hook 且 CI 全量兜底。

### #4 硬控层（违反 rule 后）：attend 口令 + 流程票据，两独立机制
protocol-resolver 是 rule 维护执行层（因）；本 #4 是其后硬控层（果）。**两项验证不可混淆**：

- **统一会话清单（轻量，审计 k3d9e 张力 1 采纳简化）**：单一 `.agent/session.json`（`session_id` 强制 `^[a-zA-Z0-9_-]{1,64}$` 白名单）。结构：`{session_id, epoch_id, attended_zones: list[{zone, epoch}]}`（审计 k3d9e-a4 诊断 1 采纳：移除 `edited_files` 死汇点，未提交状态由 `git status --porcelain` 实时投射，无冗余存储；`epoch_id` 由 `engine/marker.py` 在外部未传入时自动生成 `uuid4().hex[:8]`，见盲区 4 校准）。所有 `rel_path` 写入前必须 `Path(resolve()).is_relative_to(workspace_root)` 校验（审计 SEC-01，防 `../` 遍历 / 软链逃逸）。**不引入状态机、不记录 `base_commit_sha`、不做残留差集扫描**——逃逸主防线是本地 pre-commit 哨兵（拦无 `K3DGE_COMMIT_ACTIVE` 的提交）+ CI Branch Protection 硬地板（防御纵深：哨兵本地快拦、CI 不可绕，非冗余）。会话清单仅承担单一轻量职责：attend 跨轮次提示。
- **#4a attend 口令（验证办事者是否知会 rule，审计 k3d9e 张力 2 修正 + a3 优化 3 采纳）**：针对 protocol-resolver 标 `require_attend` 的 zone，**协议内容在每次 IO 边界（`get`/`edit`）强制注入当前上下文**（强调注意力，防 Context Dilution），并须通过**按 `(zone, task_id)` 绑定的动态 challenge** 证明本次上下文已装载（ADR 0022 的 load-proof；task_id 变则挑战变，天然抗跨轮次 / Sub-Agent 失忆）。`session.json` 的 `attended_zones` 仅为**提示性记录、不构成全局免检**——绝不因磁盘记录跳过 IO 边界注入与 challenge；且 `attended_zones` **绑定 `epoch_id`**（每轮次 / 新 Sub-Agent 重置），确保磁盘记录永不作为跨轮次免检，跨 compaction / 子代理后上下文遗忘时注入与 challenge 照常触发，消除「免检盲区」。`attended_zones`（epoch 绑定）即跨离散 CLI 进程的因果凭证记录，时序严格两阶段（盲区 2 校准，防因果倒挂）：**阶段 1（发题/读取）** `k3dge get <file>` 仅注入协议全文并回传本次 `task_id`，**不接收 `--answer`**（Agent 此刻尚未读到协议、无法预知 `sha256(normalize(protocol)+task_id)[:12]`）；**阶段 2（解题/登记）** Agent 本地算出 sha 后，经 `k3dge protocol attend --path <file> --answer <sha>` 或在随后 `k3dge put/edit <file> --answer <sha>` 中附带答案完成登记；命中才写 `attended_zones[zone].epoch`，绝非"访问即写"——否则退化为无意义访问日志；commit 读取做**软性 advisory 校验**；审计 k3d9e-a4 诊断 3 采纳其"跨进程闭环"意图，但**拒**其 `attend_tokens`/`expires_at` 状态机——与 ADR 0022 软关卡一致，不重造硬凭证）。
- **#4b 流程票据（轻量编辑触发）**：`k3dge edit`/`put` 仅触发 attend 边界校验（**废除 `k3dge begin`**），不再维护编辑声明存储（未提交态由 Git 投射）。**逃逸检测收敛至 `k3dge commit` 单点校验**（审计 k3d9e 张力 1）：`k3dge commit` 校验本次提交涉及的 require_attend zone 均已通过 challenge；裸 `git commit` 被哨兵拦截、CI 兜底，票据不重复造轮子。**L2 ③ 触发点（自审计补全）**：attend 为 advisory 且 `session.json` 仅本地（CI 无 session 可重验），故 `k3dge commit` 在单点校验时若发现某 require_attend zone 缺合法 `(zone,task_id)` challenge 凭证，于 advisory 告警**同时直接产出 L2 incident**（本地即唯一可触发点，不依赖 CI 回看 session）；CI 的 `k3dge check` 不重验 attend。
  - **`k3dge put` 自闭环幂等（a3/二 采纳）**：直接 attend 校验 + 原子写回（无需前置 edit 声明，因不再维护编辑清单）。
  - **`k3dge commit` 状态兼容（STATE-01 采纳）**：edit 后直接改文件并提交不死锁，commit 内部统一校验后提交。
- **发行 / 回收时机**：
   - #4a attend：随 IO 边界每次注入 + 按 challenge 验证；`attended_zones` 提示性，session 结束 / `k3dge end` 清空。
   - #4b 编辑触发：发行 = `k3dge edit`；放弃 → `k3dge end`/`abort` 清空 `attended_zones`（同 epoch）。

> 二者验证维度分离：#4b 编辑声明验"流程痕迹"、#4a 验"知会"，但真正硬地板是哨兵 + CI；会话清单为轻量辅助，非分布式事务层。

- **资源/效率**：边际 ~50 行（单一 session 清单含 `attended_zones`），毫秒级，性价比高 → 保持主责。
- **因果定位**：protocol-resolver（通用软引导）保证文档正确性、按 rule 办事（全路径）；#4a 验知会、#4b 验逃逸、S3 内 check 验合规——三者构成 rule 被违反时的硬控，非重叠。
- 与 S1/S2/S3 关系：S1 拦非 `--no-verify` 裸 git（与 #4b 部分重叠）；S2 远端硬地板（异步）；S3 管提交动作规范 + 内嵌 check 验合规。#4 补 #4a 知会 + #4b 逃逸的本地同步层。
- 补 #3 难点 C（哈希查改动合规，#4a 查知会，#4b 查逃逸）。陷阱：误报（逃逸判定已收敛至 `k3dge commit` 单点 + 哨兵 + CI，不再做残留差集扫描）；可信度（agent 能删 session 记录，属 raise-cost，CI 兜底）；并发（按 session 隔离）；提交消息注入（git 调用须用 exec list + `--` 隔离，禁 `shell=True`）。

### #3 detect/log 双级
L1 诊断（不落盘）：本地同步 GateReport + CI PR 状态/artifact。L2 事故（落 `docs/incidents/INC-<date>-<type>-<slug>.md`）：阈值=①绕过强合入（如管理员 Bypass Merge 强制合入）②契约 Hash 破坏 ③require_attend 区域合入但缺失合法 `(zone,task_id)` challenge 凭证（原"Marker 残留逃逸"悬空边已删，审计 k3d9e-a4 诊断 2 采纳）；处置=开 incident+挂起（**不做自动化 `git revert`，审计 a4/四 采纳**：Trunk-Based + Branch Protection 下未经 gate 绿灯在物理上不可能合入 main，auto-revert 属职责错配且引发二次代码震荡）。反向提示通道暂缓。#3 物理裁判 / #4 语义约束，#4 判定喂 #3 出 GateReport。

### #5 本地/CI 分工固化
本地=同步快反馈（`k3dge commit` 内嵌 check --staged，范围仅 staged diff）；CI=不可绕硬地板（ci.yml `k3dge check --force-full --with-tests`+pytest，push main+PR，branch protection 要求 gate 通过）；协议规定 agent 只走 `k3dge commit`/`k3dge edit`。
- **本地 pre-commit hook 退化为极轻量哨兵（审计 a3/四 采纳）**：不再内嵌全套 `engine.evaluate_workspace`，仅一行脚本检测环境变量 `K3DGE_COMMIT_ACTIVE=1`，缺失则直接报错并提示 `Forbidden: Use 'k3dge commit' instead of raw git commit`；所有实际合规校验 100% 收敛至 `k3dge commit` 内核，避免两套逻辑漂移。

## 实现清单（设计已闭环，以下为工程件）
1. `k3dge commit` 子命令（`cli`，薄封装；逻辑落 `engine`）：`git add -- <files>` + 内置 conventional 校验（等价 commit-msg hook）+ **单点校验（#4：本次提交涉及 `require_attend` zone 的 `(zone,task_id)` challenge 验证）**（STATE-01 兼容直提）+ `k3dge check --staged` + `git commit -m <MSG> --no-verify`（exec list，禁 `shell=True`，置 `K3DGE_COMMIT_ACTIVE=1` 供哨兵识别）+ 结构化 GateReport。
2. `k3dge edit <files>` 子命令（`cli`）：开启受控编辑会话（废除 `begin`）+ 触发 attend 边界校验（#4a），不再写编辑清单。
3. `k3dge put <path>` 子命令（`cli`）：受控写回（自闭环幂等：直接 attend 校验 + 原子写目标文件，不维护编辑清单）。
4. `k3dge check` 加 staged-only 模式（#4 逃逸检测已收敛至 `k3dge commit` 单点 + 哨兵 + CI，**不再做 marker 残留差集扫描**，审计 k3d9e 张力 1）；保留 `require_attend` zone 的 challenge 验证路径供 commit 调用。
5. `k3dge incident --from-ci <json>`：L2 事故生成器（落 `docs/incidents/`）。
6. CI 归位（审计 a4/四 采纳）：**删除 auto-revert workflow**；PR / merge-queue CI 100% 承担 gate 阻断；`main` 分支仅运行只读制品发布 / 文档构建，不做破坏性 revert。
7. branch protection 配置 + 跨平台文档（GitHub/GitLab/Bitbucket/Azure/Gitea）+ 本地 pre-commit 哨兵脚本（检测 `K3DGE_COMMIT_ACTIVE=1`）+ session 清单路径规范化与 `session_id` 白名单校验（SEC-01）；+ **盲区 4 校准**：scaffold 释放的 `.gitignore` 須含 `.agent/session.json`（本地凭证不入库、防多开发者/CI 脏状态污染）；`engine/marker.py` 首次写 `session.json` 且外部未传入 `epoch_id` 时自动生成 `uuid4().hex[:8]`，`k3dge end`/会话超时清空重置，保证无状态 CLI 下的 Epoch 闭环自治。
8. 协议声明：agent 只走 k3dge 命令（落 `.agent/protocols.toml`；仅 `.agent/protocol.md` 或显式登记文档可作协议源，禁止普通 `README.md`）。

### 代码落位（对齐现有域）
- Gate / 残留扫描 → `engine/evaluator.py`（加 `check_staged_only` + `engine/marker` 扫描）。
- **会话清单读写（轻量，无状态机）→ `engine/marker.py` 单一 owner**（single `.agent/session.json` 原子读写，仅维护 `attended_zones`；跨本 task 与 protocol-resolver task 代码层合一，避免 cli/engine 各写一半）。
- commit/edit/put/check → `cli` 子命令（薄封装，FS/状态逻辑落 engine，勿堆 cli）。
- （已拆出）协议路由能力 `ProtocolResolver` 分层 fallback + `validate_protocols_config` 路径重叠不变量 → 独立 task `2026-08-28-feat-protocol-resolver.md`，本 task 不阻塞、不重复。

## 验收
- `k3dge commit` 端到端替代裸 git 提交并通过门禁；裸 git 提交被 pre-commit 哨兵拦（`K3DGE_COMMIT_ACTIVE` 缺失）或 CI 拦。
- `edit` 后直接改文件并 `commit`（无 `put`）不死锁：commit 内部统一校验后提交（STATE-01）。
- 逃逸检测收敛至 `k3dge commit` 单点（require_attend zone 的 `(zone,task_id)` challenge）+ 哨兵 + CI；会话清单不做残留差集扫描（避免与哨兵/CI 冗余，审计 k3d9e 张力 1）；原 `base_commit_sha`/`MARKER_CORRUPTED`/`git status` 残留算法已移除。
- require_attend zone 每次 IO 边界强制注入协议 + 按 `(zone,task_id)` challenge 验证；`attended_zones` 不授予全局免检，跨 compaction / 子代理失忆时不跳过（审计 k3d9e 张力 2）。
- `k3dge edit/put/commit` 传入 `../` 或软链越界路径、`session_id` 含非法字符 → 拒绝（SEC-01）；git 调用均带 `--` 隔离符（GIT-01）。
- `k3dge get` 仅发题（注入协议 + 回传 `task_id`）**不接 `--answer`**；`--answer` 仅经 `attend`/`put`/`edit` 在阶段 2 提交（时序因果不倒挂，盲区 2 校准）。
- `.agent/session.json` 必被 `.gitignore` 忽略（不入库）；外部未传 `epoch_id` 时 `marker.py` 自动生成 `uuid4().hex[:8]`，`k3dge end`/超时清空重置（盲区 4 校准）。
- CI gate 红阻断 merge（branch protection）；无 auto-revert，L2 仅 incident+挂起。
- 本地/CI 分工写入协议，无漂移。

## 审计采纳回填（两轮穿透审查 · 最终判定）
经两轮审计（a 轮推崇形式化/分布式状态机、b 轮反过度设计），以「取舍判断」收口：

**采纳（明确安全/可用性增益）**
- **a1/SEC-01 路径穿越防御**：所有 IO 接口 `is_relative_to(workspace_root)` 规范化 + `session_id` 白名单 `^[a-zA-Z0-9_-]{1,64}$`。
- **a1/STATE-01 直提死锁修复**：`k3dge commit` 内部统一校验后提交，edit 后直接改文件并提交不死锁（无需强制先 `put`）。
- **a1/GIT-01 参数注入防御**：git 调用统一 `--` 隔离符（`git add -- <files>` 等）。
- **a1/LATTICE-01**（见 resolver task）：重叠扫描含未暂存新建文件。
- **a3/一 废除 `k3dge begin`**、**a3/二 `put` 自闭环幂等**、**a3/四 pre-commit 哨兵化**、**a4/四 删除 auto-revert**：均保留。
- **会话清单原子写（a4/二 部分保留）**：`session.json` 单次 `os.replace` 原子写，防中断致半截 JSON；不引入 TTL / GC 扫描。

**推翻（b 轮证伪为过度工程 / 我方前次误采纳）**
- **推翻 a3/三 attend 合入逐文件 Marker（我方前次误采）**：改为 session 级清单，attend 跨 commit 持久，修正语义篡改。
- **推翻 a4/二 TTL 租约 + 分布式事务层 / a5/一 LCA 图遍历 / a2/R4 base 滚动重锚**：改为单一 session 清单 + `os.replace` 原子写，`git status --porcelain` 工作区态判定残留，天然抗 rebase 假阳性，不造 Git 之上的影子引擎。

**采纳 k3d9e 全局视角（第三轮）**
- **张力 1 票据状态机冗余**：移除 ACQUIRED→STAGED→BURNED 状态机与残留差集扫描；逃逸主防线回归哨兵 + CI，会话清单退为轻量（仅 attend 提示，编辑态由 Git 投射），`k3dge commit` 单点校验。
- **张力 2 attend 持久化盲区**：`attended_zones` 改为提示性、不构成全局免检；协议每次 IO 边界强制注入 + 按 `(zone,task_id)` challenge，抗跨轮次/Sub-Agent 失忆。**追加 epoch 绑定（attended_zones 绑 `epoch_id`，每轮次/Sub-Agent 重置，审计 k3d9e-a3 优化 3）**，从数据结构封死跨轮次免检实现陷阱。
- **张力 4 trie 微观优化倒挂**（另见 resolver task）：规则基数极小、CLI 冷启动吞没增益，路径解析退回按 Specificity Tuple 降序线性匹配，不建 radix/symbol trie。

**采纳 k3d9e-a4（第五轮图论检视）**
- **诊断 1 `edited_files` 死汇点** → 移除；未提交态由 `git status --porcelain` 实时投射，session.json 退为 `{session_id, attended_zones}`。
- **诊断 2 L2 ③ 悬空边** → 修正为「require_attend 区域合入但缺合法 `(zone,task_id)` challenge 凭证」，删 Marker 残留幽灵边。
- **诊断 4 冲突检测分治** → 配置校验按特异度等价类分组，仅 `|C_k|>1` 的同特异度组内做重叠判定（已隐含于"同特异度平局"规则，显式化；R≤30 下性能可忽略，纯清晰度收益）。
- **诊断 3 attend 跨进程凭证** → **拒** `attend_tokens`/`expires_at` 状态机：与 ADR 0022 软关卡冲突、重造硬凭证，且 epoch 绑定的 `attended_zones` 已提供跨进程因果记录（commit 做 advisory 校验）。
