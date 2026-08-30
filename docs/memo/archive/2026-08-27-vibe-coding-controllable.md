# Memo: k3dge 的存在理由 = 个人 AI 开发的技术债可控层

- **Date**: 2026-08-27
- **Type**: 设计立意（已收敛为完整落地方案，2026-08-28 升级为 task，见末「落地方案」）
- **最后复核**: 2026-08-28（推翻 A→锁定 branch protection；整合 #1-#5 + 票据生命周期为落地方案；设计闭环，升级 task）

## 核心

k3dge 不是"让 agent 更靠谱/更自主"，而是 **让 vibe coding 对个人 AI 全职开发者可控**。
敌人在"前期巨快、后期技术债缠身"，不在"agent 写错"。

## 为什么是这个形态（不是硬闸）

1 个人 + AI 的死穴：高效用 AI 且摸清项目每处细节几乎不可能 → 只能让系统*可用*，而非前期冲速。
由此推出整条架构链：

- agent 够得到的一切（钩子/凭证/协议文件）都只是约定，可绕过/编造 → **硬闸不可行，软关卡才是真形态**（ADR 0022 修订）。
- 稀缺资源是**人在 review 时的注意力**，不是 agent 的服从度 → 系统该把注意力花在"暴露例外"，不花在"盯梢"。
- 所以正确三件套：**L3 CI 硬地板**（合不进主干就过不了）+ **incident 纸痕**（劝返无效的偏离写 `docs/incidents/`）+ **协议=最小不变量**（审计 12 列 / 复审三态闭环，solo 记不住但必须不破）。

## 反噬警告（已修正：伪→真）

原判断"协议泛滥成债、必须压到 4~5 个"**过度悲观，已修正**。
- 真风险不是*文件数量*，是*一次把全部协议装进上下文*（那才 Context Dilution）。
- 路径路由让每次写只注入**那一条**相关协议（ephemeral），agent 同时只持一份 → 协议多几份无妨。
- 结论：**按职责分区多加协议是对的**，agent 记几份绰绰有余；别怕数量，怕"全量加载"。

## 路径路由（本轮 affirmed）

- 依旧按路径找协议，不退回显式 task_type 为主。
- 目录职责不重叠是**正确性前提**：每个路径只担一种职责→只映射一个协议。`docs/reviews/**`↔audit、`tests/**`↔verify 天然不交即可，无需"最具体 glob 胜出"（那是重叠时的补丁，非机制）。
- 重叠 = 布局 bug：应在 `validate_protocols_config` 加**路径重叠不变量**（实际仓库文件命中 ≥2 个 glob 即报 `PROTOCOL_REGISTRY_INVALID`）。把"目录职责不重叠"从口头约定变成 gate 红叉。
- 布局不干净的仓库退回显式 task_type，不硬走路径。

## 写入口收敛（本轮 refined）

- **协议感知入口 = 永远通用**（所有写都走它，强调注意力）；**硬门（ACL/`k3dge apply`）= 选配**，仅关键文件按需开启，非默认。
- 协议感知分层 fallback（入口永远先做"找规范"这一步）：
  1. 有**协议配置**（`.agent/protocols.toml` 的 `[paths]`/`[protocols]` 命中）→ 读注册协议文件。
  2. 无配置 → 读**路径所在目录的 README.md**（该区自建操作规范）。
  3. 无 README → **无协议**，走 base spec。
- 含义：跨切面高危协议（audit/verify）进中央注册表；其余分区靠本目录 README 自文档化，无需逐目录注册 → 协议份数天然有界（呼应"怕全量加载不若怕份数"）。
- 警惕：硬门滑成"全仓默认"即退回**蠢**区——**协议感知必通用，硬门必选配**。

### 硬门机制（apply，本轮 refined → 定为 **A：git merge 模型**）

- **apply = 协议门控的 merge**（已选 A，ACL 弃用）。
- agent 在自己分支/worktree 改（权威存储=git 历史，agent 不在 main 上工作）；`apply` 跑协议门控（resolve/challenge/ticket/check）后 **branch → main 提升**。
- 原子性/历史/回滚 = git 白送；"复制→原子覆盖"无需手搓；apply 不 exec agent 代码。
- **ACL 免设**：无需 OS 文件锁，靠"agent 天然在分支、不碰 main"。
- **硬地板保留（唯一）**：真·不可绕 = **远端分支保护 + CI**（merge 受保护 main 必须过 apply/check）。本地 agent 同用户仍可技术上绕过，故硬只在远端。
- **智能门控可扩展**：merge 时插 reviewer（人/第二个 agent），即 PR review 模型，ADR 0008 的 sibling peer；分层可配：静态 check + 可选 reviewer + 可选人审。

#### 工程复核（2026-08-28 · 推翻 A 方案）
- 上述「A：git merge 模型」作为**门禁**不成立。分支 merge 与 **trunk + 受保护 main + CI gate** 在「门禁不可绕」上**完全等价**：硬地板都在 server-side CI，git 对其无 `--no-verify` 开关；本地 `--no-verify` 只是跳过反馈、不影响权威。
- 分支模型不提供任何门禁层面的先进性，反而三项皆劣：
  1. **更重**：多分支管理 / PR 摩擦 / worktree 开销；
  2. **留痕更多**：分支本是不该留痕的中间产物，显式命名/推送/清理增加全局记录负担；
  3. **防绕过无需隔离**：把 `k3dge` 封装成 agent 唯一可用的提交黑盒，底层 git 不可见，agent 无动机绕过——「提高绕过成本」已够，不追求数学 0 绕过（任何现实工程都是收益/成本平衡）。
- **结论**：`apply` 不应实现为 branch→main merge。门禁 = **trunk + 受保护 main + CI 强制 `k3dge check`**；agent 提交走**封装黑盒工具**；漂移靠 `Contract Hash` 检测 + 提示/log 兜底（绕过即提示+log 即可）。若有 `k3dge apply`，只是「提升时绑定 zone 协议 + agent 已 attend」的**语义层**，而非 git 分支隔离层。

##### 硬地板机制锁定（2026-08-28）：branch protection + required CI status
- **受保护 main 的具体形态 = branch protection（平台无关语义）**：禁直推 main + Require PR + Require status checks 通过（勾 CI 的 `gate` job）。这是**跨托管标配，非 GitHub 独有**：GitHub *branch protection rules* / GitLab *protected branches* / Bitbucket *merge checks* / Azure *branch policies* / Gitea *branch protection*，能力同构（非 main + CI 绿 + 合 main）。
- **不用 server-side pre-receive**：SaaS（GitHub / GitLab.com…）不开放服务器 hook，无法部署；仅裸自托管 server 可。本项目用 GitHub，故取 branch protection 作等价硬地板（git 对其无 `--no-verify` 绕过开关）。
- **buffer branch 不采纳**：曾议「远端固定 branch 做 CI 缓冲」，本质是同门禁逻辑的**候选区退化版**——用常驻固定 branch 替代每 PR 临时 branch，更重、丢并发/冲突处理、多留痕，无新增门禁能力。直接用平台原生 branch protection 即可（buffer 即其弱重造）。
- **分工固化**：本地 pre-commit（`.pre-commit-config.yaml` → `scripts/gate.py` → `k3dge check`）= 快反馈；CI（`.github/workflows/ci.yml` 已跑 `k3dge check --force-full --with-tests` + pytest）= 不可绕硬地板。本地/CI 分工细则见下「落地方案 #5」。

## 落地方案（锁定 2026-08-28）：trunk + branch protection + 封装黑盒 + 票据生命周期

### 架构总览
- 门禁模型：**trunk-based + branch protection**（禁直推 main + Require PR + Require `gate` status）为不可绕硬地板；本地 `k3dge commit` 黑盒为同步快反馈与降绕过成本；`Contract Hash` + **票据生命周期**做漂移/流程 detect；L1/L2 双级 log。
- 哲学：不追求数学 0 绕过（raise cost + detect，收益/成本平衡）；硬闸不可行，软关卡 + incident 纸痕（接 line 18）。

### #1 提交封装黑盒 `k3dge commit`（含票据核销）
- 接口：`k3dge commit [<files>...] [-m MSG] [-a]`。
- 内部链：`add` → 内置 conventional 校验 → **票据核销校验（见 #4）** → `k3dge check --staged`（快模式）→ `git commit -m --no-verify`。
- 安全前提：跳过本地 hook 安全，因 (a) `k3dge commit` 内 check 覆盖 ≥ 本地 hook；(b) CI 全量 `--force-full` 才是真硬地板。内置 conventional 校验须**等价**原 commit-msg hook 规则（否则缝隙）。
- 价值：单点语义操作面，剪枝裸 git 危险参数（`--no-verify`/`-am`/交互编辑卡死）。

### #4 apply 语义层 = 票据生命周期（begin → edit → commit 核销）
- `k3dge begin <files>`：开票据，写 `.agent/markers/<session>_<path>.json`（zone / attend_state / opened_at）。
- agent 编辑；`k3dge commit` 成功后**核销**（删票据）。
- 检测：`k3dge check` 扫残留票据——若 path **已 commit（git 无未提交 diff）却仍带未核销票据** → 裸 git 绕过 k3dge → 报警（L1 阻断 / 疑似 L2）。
- 这是 #4「提升绑定 zone 协议 + attend」的运行时载体，且补 #3 难点 C（哈希查"改了啥"，票据查"怎么改的"）。
- 陷阱：误报（仅"已 commit 仍带标记"报，进行中不报）；可信度（agent 能删标记，属 raise-cost，CI 兜底）；并发（按 session+path 隔离）。

### #3 detect / log 双级闭环
- **L1 诊断（不落盘）**：本地 `k3dge commit`/pre-commit 同步输出 GateReport；CI gate 红 → PR 状态 + CI artifact。
- **L2 事故（落 `docs/incidents/INC-<date>-<type>-<slug>.md`，接 line 18）**：命中任一硬阈值——① 绕过门禁强行合入（管理员 override，罕见）；② 自动 revert 失败 ≥2 次；③ 受保护契约 Hash 破坏。处置 = 自动 `git revert` + 开 incident + 挂起任务。
- **反向提示通道（CI→agent）：暂缓**，solo 阶段 PR 状态 + 本地同步足够。
- **#3/#4 正交**：#3 物理裁判（格式/AST/exit/git），#4 语义约束（zone/attend/hash）；#4 判定喂 #3 出 GateReport。

### #5 本地 vs CI 分工固化（防漂移）
- **本地层 = 同步快反馈**：`k3dge commit` 内 `k3dge check --staged`（仅暂存 diff）；裸 git 走 pre-commit hook（`.pre-commit-config.yaml` → `scripts/gate.py`）兜底。范围 = 本次 staged diff，非全工作区。
- **CI 层 = 不可绕硬地板**：`.github/workflows/ci.yml` 跑 `k3dge check --force-full --with-tests` + pytest，事件 push main + PR；branch protection 要求 `gate` status 通过方可 merge。
- **branch protection = 合并阻断**：禁直推 main + Require PR + Require status check（平台无关，见硬地板锁定）。
- 协议规定：agent 只走 `k3dge commit` / `k3dge begin`，不裸 git（写进协议/agent 指令，非 git 强制）。

### 实现清单（设计已闭环，以下为工程落地件）
1. `k3dge commit` 子命令（src/k3dge/cli/commit.py）：add + conventional 校验 + 票据核销 + check --staged + `git commit --no-verify` + 结构化 GateReport。
2. `k3dge begin` 子命令：开 `.agent/markers/<session>_<path>.json` 票据。
3. `k3dge check` 加 staged-only 模式 + 残留票据扫描（需 `engine.evaluate_workspace` 支持 `check_staged_only`）。
4. CI auto-revert workflow：ci.yml `on: push: [main]`，gate 红 → `git revert` + 调 incident 生成器。
5. incident 生成器：`k3dge incident --from-ci <json>` 或 CI 步骤，按 L2 模板写 `docs/incidents/`。
6. branch protection 配置：GitHub 设 main 保护（禁直推 + Require PR + Require `gate`）；文档附 GitLab / Bitbucket / Azure / Gitea 等价物。
7. 协议声明：agent 只走 `k3dge commit`/`k3dge begin`（落 `.agent/protocols.toml` 或 README 协议区）。
8. `ProtocolResolver` 分层 fallback（注册协议 → 目录 README → base）。
9. `validate_protocols_config` 路径重叠不变量（命中 ≥2 glob 报 `PROTOCOL_REGISTRY_INVALID`）。

### 设计完整性声明
选型（推翻 A → branch protection）、五块方案（#1-#5）、票据生命周期、双级 detect 均已闭环；无未决设计项。剩余均为上列 9 项工程实现 → 升级为 task 跟踪落地。

## 空间 vs 时间 apply（用户洞察，已吸收）

- git = **时间上的 apply**（commit 把状态压进历史）；k3dge apply = **空间上的 apply**（把改动压进协议 zone）。
- 同构：不可信 actor 只产候选，可信进程校验后原子提升，绝不原地直改权威存储。
- 定性修正：k3dge 不是新原语，是 **git 的空间治理被做成 agent-native + 协议感知**；新增值=提升时绑定"该 zone 协议 + agent 必须已 attend（challenge/ticket）"。
- **〔工程复核 2026-08-28 修正〕** "绝不原地直改权威存储"**不要求分支隔离**：trunk + 受保护 main 下，未过 CI 的提交同样不进权威，候选与权威在 server-side 分离。git（纵向 commit/PR ref）与 k3dge apply（横向 zone）同为"候选→校验→提升"的**几何形态差异，功能等价**；分支模型无独占先进性，仅当多 agent 并行持独立候选时是并发便利（非门禁需求）。

## 零散灵感（raw，待蒸馏）

- 用户灵感零散、常一句带过，非连续主题；本 memo 直接吸收，迭代时去伪存真。

## 措辞尺子

对外不讲"k3dge 让 agent 更靠谱"，讲"k3dge 让 agent **可治理、可证明**"——两件事。
定位是 *agent 的操作系统 / CI*，不是 *更好的 agent 框架*（ADR 0006：sidecar 门禁，不拥 runtime）。

## 关联

- ADR 0006（sidecar 不拥 runtime）
- ADR 0022（协议调度：软关卡 + 上报 + CI 硬地板）
- 与前沿 harness（Anthropic/OpenCode/Codex 卷"更自主的 agent"）**不同赛道**：他们卖能力上限，k3dge 卖确定性/可审计。
