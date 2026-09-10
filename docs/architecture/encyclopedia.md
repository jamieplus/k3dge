# k3dge 百科全书 — 知识地图（Encyclopedia / Knowledge Map）

> 定位：**开放式索引 + 术语表 + 导航**，帮任何人从任意入口快速定位事实。它补全而不是替代系统叙事——
> 域间关系、全局不变量以 [`overview.md`](overview.md) 为判据（§ 序号稳定）；决策单一事实源在 [`docs/adr/`](../adr/README.md)；
> 有意留活在 [`docs/reviews/LEFTOVERS.md`](../reviews/LEFTOVERS.md)。本文只做"指路 + 速查"，不复写正文。
>
> 文档纪律见 AGENTS.md：寻址走 `k3dge doc list / where`，正文扫描走 `k3dge doc grep`，不裸 grep `docs/`。

## 0. 怎么用本百科

| 你是谁 | 从哪读起 |
| --- | --- |
| 第一次接触的新 Agent / 开发者 | 本节 → §1 → §2 → §7，把术语卡在 §3 |
| 甲方 / 非技术读者 | [`docs/guides/client_intro.md`](../guides/client_intro.md)（人话版） |
| 要动 `src/` 代码 | §2 域地图 + 该域 `spec.md`；改公开接口另见 §6 `sync` |
| 要做里程碑封板 | §7 流程速览 + [`overview.md`](overview.md) §6–7（唯一叙事判据） |
| 要找某条决策 / 历史审计 | §5 ADR 索引 + `k3dge doc list --type reviews` |

## 1. 这是什么：一句话与核心问题

**k3dge = spec-gate harness**：给 AI 编程（Vibe Coding）配的确定性契约漂移检测门禁（`pyproject.toml` description）。
它把"口头交代"变成物理门禁，在提交点拦截三大类问题——接口改了 spec 没改、Agent 跨会话语义漂移、随意破坏底层抽象。

组合拳：

1. **分层门禁** `k3dge check`（纯静态硬闸）：
   - **L0 结构**：spec 章节完整性（正则/结构校验）；
   - **L1 契约**：公开接口签名归一化哈希比对 + 符号级 `diff`（增/删/改名/改参清单，`--json` 可读）；
   - **L2 行为**：Verification Matrix ↔ 真实测试的对应关系（矩阵行解析到具体测试）。
2. **确定自愈** `k3dge sync`：从代码回写 spec 的接口投影与哈希——自愈的是投影，不是批准改抽象。
3. **生命周期治理** `k3dge milestone`：align → audit → seal，审计闭环是封板的唯一界限。

基线事实源：ADR-0001。目的（减少漂移/幻觉/修局部坏整体）的表述见 ADR-0009。

## 2. 域地图与代码导航

事实源：`.agent/manifest.json`（域路由）。四大域：

| Domain | 源码 | 契约 Spec | 测试 | depends_on | 一句话 |
| --- | --- | --- | --- | --- | --- |
| `engine` | `src/k3dge/engine` | `docs/specs/engine/spec.md` | `tests/unit/engine` | — | 门禁核心：diff / manifest / contract / evaluator / milestone / version / pipeline / bundle / markers / doc_catalog |
| `cli` | `src/k3dge/cli` | `docs/specs/cli/spec.md` | `tests/unit/cli` | engine, templates, sync | 本仓终端/CI + 对外 harness 的 MCP 注入面 |
| `sync` | `src/k3dge/sync` | `docs/specs/sync/spec.md` | `tests/unit/sync` | engine | spec 接口块与契约哈希回写；`docs/generated/` 机器文档 |
| `templates` | `src/k3dge/templates` | `docs/specs/templates/spec.md` | `tests/unit/templates` | — | `k3dge-init.sh` 脚手架生成器 |

依赖方向：`cli → engine / sync / templates`、`sync → engine`、`engine ↛ templates`（`TEMPLATE_DRIFT` 字节锁，ADR-0014）。非 `package_root` 且非 `docs/specs/` 的文件不计入门禁范围。空 `manifest.domains` 报 `NO_DOMAINS`（下游空壳不得假绿）。

符号级寻址：`k3dge where <symbol>`（`file:line`；索引在 `docs/generated/symbol-index.json`，`k3dge index` 重建）。

## 3. 核心概念词表（术语百科）

### 3.1 门禁与契约

| 术语 | 一句话 | 出处 |
| --- | --- | --- |
| **Contract Hash** | 公开接口归一化后的 `sha256`；spec 是锁、代码是源，任何公开接口改动必须 sync 回写 | ADR-0001；`engine/contract.py` |
| **GateReport** | `passed ⇔ violations 为空`；含 `changed_files / modified_domains / violations`，`--json` 带符号级 diff | ADR-0001；`specs/engine §3` |
| **L0 / L1 / L2** | 结构闸 / 契约哈希闸（含符号 diff）/ 行为闸（矩阵↔测试） | ADR-0001 |
| **CONTRACT_DRIFT** | 公开签名哈希失配的违规码 | `specs/engine §4` |
| **TEMPLATE_DRIFT** | 自举仓脚手架字节锁：`engine/pairs.PAIRS` 比对 `templates/assets`，引擎不 import `k3dge.templates` | ADR-0014 |
| **merge-base 基准** | 校验基准 = `merge-base(main, HEAD)`，code 可先落地、spec 分支内收敛 | ADR-0001 |
| **Verification Matrix** | spec §4 的"场景 → 测试文件"表；`align` 跑 Full Matrix | ADR-0001 / ADR-0004 |
| **三件套（版本）** | `pyproject.toml` / `.agent/manifest.json` / `src/k3dge/__init__.py` 版本镜像；不一致 = `VERSION_MISMATCH` | ADR-0013 |

### 3.2 生命周期与审计

| 术语 | 一句话 | 出处 |
| --- | --- | --- |
| **Milestone 状态机** | `DRAFT → ALIGNED → AUDIT_SUGGESTED → AUDITING → SEAL_READY → SEALED`（+`ESCALATED`） | [`overview.md`](overview.md) §6 |
| **`[NEXT]` 提示** | 命令末尾只给合法下一步；优先级 `pending_findings > ratchet_open > seal_ready > audit_suggested`；唯一来源在 `engine/nextstep` + `engine/audit_trigger` | [`overview.md`](overview.md) §7 |
| **审计闭环（封板界限）** | audit + quality 两份 **12 列报告**都到 `待修=0`；未审计调 seal → `audit_needed` | ADR-0017；[`overview.md`](overview.md) §6 |
| **钉语法 markers** | `k3dit:<kind> <ID>[@scope] <一句话≤80字>`；kind ∈ `pending/leftover/disputed/fixnote`；scope ∈ `line/file/repo`；开放=前三态，结项须清零 | [`docs/protocols/peer_contract.md`](../protocols/peer_contract.md) §8；`engine/markers.py` |
| **pending_findings** | `k3dit:pending` 钉计数（check/status 报 `pending=N`，最高优先）；处置以 12 列+tasks 为准，理由写报告不入正文 | AGENTS.md §12；`peer_contract §8` |
| **送检包 Bundle** | gate 类唯一输入形式：`target/ + signatures/ + MANIFEST.json`；身份=`cas://sha256:<git-tree-oid>`，位置=单文件袋；打包器 `engine/bundle.py`，配置 `.agent/bundle.toml` | ADR-0024；`peer_contract §3` |
| **棘轮 Ratchet** | 一工单 = 一快照，单内审↔修可多程；submit/collect 两态；`claim` 即续租；快照推进一律 `git update-ref` CAS | `peer_contract §1.4` |
| **席位 seat** | 审计机构经 seat 连接组件上岗；`sign-report` 署名才算结案 | `peer_contract §1.4` / §2 |
| **doc-audit** | `check` 后、**非阻断**的文档作者合规审计：k3dit 报告 + 建带 Milestone 的 task | ADR-0021 |
| **预筛 Pre-filter** | 人工入口审计的三条件复用（闭环报告 + 基线同 + lens 版本同）；自动入口不预筛 | `peer_contract §7` |

### 3.3 文档体系

| 术语 | 一句话 | 出处 |
| --- | --- | --- |
| **Diátaxis 分类** | `guides`=教程 / `generated`=Reference 机器自动生成 / `architecture`=解释（本文+overview） | [`overview.md`](overview.md) 头部；`docs/generated/README.md` |
| **`docs/<type>` 规约** | 每种类型锁 `README.md` + `AUTHORING.md`；结构硬闸 `docs/<type>/.schema.json`（有才闸，缺则下游安全） | ADR-0018/0019；`engine/doc_catalog.py` |
| **doc catalog** | `list / where / grep`；`grep` 正文只回 `path(:line)`，不回 snippet | ADR-0019；`docs/generated/docs-index.json` |
| **LEFTOVERS.md** | 有意留（活文档常驻表）唯一事实源 | [`overview.md`](overview.md) §8 |
| **Memo** | spark inbox：三种"暂不成事"的念头（模糊/暂不可落地/弱相关）；成熟后晋升 tasks 并移 archive | `docs/guides/user_guide.md`；`docs/memo/README.md` |
| **Incident** | 持续偏离落 `docs/incidents/INC-YYYYMMDD-<TYPE>-<slug>.md`；L2 生成器 `k3dge incident` | ADR-0019 语境；`engine/protocol.write_incident` |
| **guide-stub / align-pass** | `<!-- k3dge:guide-stub -->` 阻断 seal；`<!-- k3dge:align-pass:<id> -->` 是 seal 的 reviews 入场券 | `specs/engine §3` |

### 3.4 MCP 与对外 harness（peer）

| 术语 | 一句话 | 出处 |
| --- | --- | --- |
| **MCP 注入面** | k3dge 以 MCP stdio 把 engine 事实交给 DSH/Codex/Claude Code/OpenCode；外部禁止私有重实现门禁 | ADR-0006；`docs/guides/mcp-bridge.md` |
| **Peer Contract v0.6** | k3dge ↔ 外部 harness 机器契约（信封/工件/钉/棘轮）；**权威源在 GitHub**，本地为工作副本 | `docs/protocols/peer_contract.md` |
| **角色 model** | 只认 `audit / quality / cache`；gate 类（送检包+两态+provenance）vs service 类（同步查询、失败=skip） | `peer_contract §0` |
| **`.mcp.json`** | endpoint（command/args/env/cwd）唯一登记表，不得在 pipeline.toml 重复 | `peer_contract §0`；`mcp-bridge.md` |
| **`.agent/pipeline.toml`** | 流程编排：roles → peers → actions → transports（mcp→cli→manual fallback 链） | `specs/engine §5.1`；`mcp-bridge.md` |
| **降级不可静默** | `WARN[DOWNGRADE] action=… from=… to=… reason=…` 追加 `logs/k3dge.log` | `mcp-bridge.md`；`peer_contract §6` |
| **stub / dummy** | `bind = "dummy"`（`tests/fixtures/dummy_peer.py`）骨架期换实现，k3dge 一行不改 | `peer_contract §5` |
| **K3DGE_SOURCE** | 下游判定核来源政策：本地路径(editable)/`git+https://`(PEP 508)/`pypi`；政策赢过收据，不符 `exit 2` | `docs/guides/downstream.md` |

## 4. 文档地形图

| 类型目录 | 管什么 | 写入规则 | 寻址 |
| --- | --- | --- | --- |
| `docs/architecture/` | 系统叙事与全局不变量（overview）、知识地图（本文） | `AUTHORING.md`；只有 overview/encyclopedia | 直接开 `overview.md` |
| `docs/adr/` | 架构决策记录（append-only，号不复用） | 抄 `_template.md`；修订用 `Amended by` / `Superseded by` | `k3dge doc list --type adr` |
| `docs/specs/<domain>/` | 域契约：边界 + 接口块（`k3dge:interfaces-*`）+ 哈希 + 矩阵 | `k3dge sync` 回写接口与哈希；人写 §1/§3/§4 | `k3dge doc where <ident>` |
| `docs/guides/` | 人读 how-to | 指真实子命令，不发明 CLI | `k3dge doc list --type guides` |
| `docs/generated/` | 机器 Reference（api/domains/symbol-index/docs-index），勿手改 | 生成器回写 | — |
| `docs/tasks/` | 任务 backlog（Status/Priority/Milestone） | `k3dge task create / done` | `k3dge task list --json` |
| `docs/reviews/` | 审计存档（12 列报告）+ LEFTOVERS | 封板写回；append-only | `k3dge doc list --type reviews` |
| `docs/memo/` | 暂不成事的闪念，永不进门禁 | 抄 `_template.md` | `k3dge doc list --type memo` |
| `docs/incidents/` | 持续偏离的 incident 记录 | `k3dge incident` / `write_incident` | `k3dge doc list --type incidents` |
| `docs/branches/` | 红闸分支勘误记录 | 见 `docs/branches/` | — |
| `docs/protocols/` | 审计/质量/复核协议 + Peer Contract | 改动 = 契约变更，需 `k3dge sync` + 下游跟随 | `k3dge doc list --type protocols` |

> 结构门禁（commit）：staged `docs/**` 需该类型 `README.md` + `AUTHORING.md` 齐；`check` 绿后给 `[NEXT] doc_audit`（`k3dge doc-audit` 非阻断，ADR-0021）。

## 5. 决策索引（ADR 全表）

按主题分组（对应 `docs/adr/README.md` 的 Topics，0020 补录于 Agent/harness 组）。**标题为序，深读请 `k3dge doc where <ADR-ID>`。**

### 门禁与基线
| ID | 主题（文件名） | 一句话 |
| --- | --- | --- |
| ADR-0001 | k3dge 架构设计与工程治理基线 | 四域布局 + L0/L1/L2 分层门禁 + 双向绑定 + 符号级 diff 留痕 |
| ADR-0014 | template-drift-in-engine | 自举脚手架字节锁，engine 机检不 import templates |

### 文档体系
| ID | 主题（文件名） | 一句话 |
| --- | --- | --- |
| ADR-0002 | docs-reference-vs-architecture-semantics | spec=契约 / ADR=决策 的语义切分；reference 分层 |
| ADR-0003 | tasks-backlog-merge | tasks 与 backlog 合并为单一日历状态容器 |
| ADR-0018 | doc-readme-anchor-governance | 每种文档类型 README 锚点 + AUTHORING 寻址治理 |
| ADR-0019 | protocol-load-proof-abandoned | 协议加载证明废弃；`PIPELINE_PROTOCOL_NOT_FOUND` 静态守卫 |
| ADR-0023 | low-authority-archive-tier | 低权威归档层（挪走不删） |
| ADR-0024 | audit-evidence-exchange-topology | 送检包拓扑：git-tree oid 身份 + 单文件位置 + 棘轮交换 |

### 生命周期
| ID | 主题（文件名） | 一句话 |
| --- | --- | --- |
| ADR-0004 | milestone-lifecycle-governance | 里程碑生命周期/封板状态机与执行口径 |
| ADR-0008 | unsolicited-doc-triggers | 文档改动触发的非请求式审计触发器 |
| ADR-0021 | doc-audit-post-check-non-blocking | `doc-audit` 在 check 之后、非阻断，建带 Milestone 的 task |
| ADR-0022 | task-maps-to-audit-report | task 映射到审计报告条目 |

### Agent 与 harness
| ID | 主题（文件名） | 一句话 |
| --- | --- | --- |
| ADR-0005 | local-first-and-layer-cuts | 本地优先与层切分（`K3DGE_SOURCE` / editable） |
| ADR-0006 | mcp-foreign-harness-injection | MCP 注入：外部 harness 调 k3dge 事实，禁私有重实现 |
| ADR-0009 | purpose-reduce-agent-failure-modes | 目的：减少 Agent 失败模式（漂移/幻觉/修局部坏整体） |
| ADR-0010 | agent-rules-are-protocol-slices | `.agent/rules/*` 是协议切片（ADR-0010 slice 化），AGENTS.md 为真 |
| ADR-0011 | agent-dir-is-harness-config | `.agent/` 是进程配置，不是可浏览的发现面 |
| ADR-0012 | assertion-evidence-chain | 证据链三环节：产物 + 消费者 + 到达 |
| ADR-0020 | harness-responsibility-split | harness 职责切分（审计/质量/检索各管一块，k3dit/k3lity/k3che） |

### 自举与版本
| ID | 主题（文件名） | 一句话 |
| --- | --- | --- |
| ADR-0007 | self-hosting-bootstrap | 自举：k3dge 用自己的门禁治理自己的开发 |
| ADR-0013 | version-and-changelog | 版本三件套镜像 + CHANGELOG 自动维护 |
| ADR-0015 | downstream-first-domain-and-protocol-pack | 下游至少一域 + 协议打包（init 幂等不覆盖） |
| ADR-0016 | pattern-absorption-protocol | 模式吸收协议（外部 idea 成熟后入主干） |

### 审计报告
| ID | 主题（文件名） | 一句话 |
| --- | --- | --- |
| ADR-0017 | report-schema-v2 | 12 列报告 schema v2（待修/有意留/已修 计数自洽） |

## 6. 常用命令速查

事实源：`k3dge --help`。本仓自举用 `.venv/bin/k3dge`（`pip install -e ".[dev]"` 之后 `k3dge` 即 PATH）。

| 目的 | 命令 |
| --- | --- |
| 环境与状态 | `k3dge status`（域/漂移/pipeline/未完成 tasks/[NEXT] 一行） |
| 门禁 | `k3dge check`（git 触及域）；CI/封板用 `k3dge check --force-full --with-tests` |
| 回写契约 | `k3dge sync`（改公开接口后必跑） |
| 里程碑 | `k3dge milestone audit <id>`（棘轮步进）、`k3dge milestone seal <id>`、`k3dge milestone align` |
| 任务 | `k3dge task list --json` / `k3dge task create` / `k3dge task done` |
| 文档寻址 | `k3dge doc list` / `k3dge doc where <id>` / `k3dge doc grep <word> [--line]` |
| 文档审计 | `k3dge doc-audit`（check 之后、非阻断，ADR-0021） |
| 符号定位 | `k3dge where <symbol>`（file:line）；`k3dge search` / `k3dge index` |
| 审计钉 | `k3dge markers [--json|--check]` |
| 送检与棘轮 | `k3dge audit <submit|status|advance|close>`（审计线：锁线→交件→验→merge→删线） |
| MCP | `k3dge mcp probe [--json]`（诊断，不进 check） |
| 版本 | `k3dge version show` / `k3dge version bump --patch|-m` |
| 提交 | `k3dge commit`（门禁 + attestation 签名）；verify 用 `k3dge verify-attest` |
| 事故 | `k3dge incident`（L2 生成器，从 CI JSON） |
| 脚手架 | `k3dge init`（新仓播种）；`./k3dge-init.sh` |

> 审计相关另有两份协议常备：`docs/protocols/audit_default.md`（5-Pass/8 维）、`docs/protocols/quality_default.md`（k3lity 12 列）、`docs/protocols/verify_default.md`（复核 12 列）。

## 7. 里程碑 → 审计 → 封板速览

```
DRAFT →(milestone align: Full Matrix, 无人问)→ ALIGNED
      →(账齐/C2≥5/体积≥8 量化触发)→ AUDIT_SUGGESTED → 问「要审吗?」N=继续干活
      →(milestone audit)→ AUDITING：audit(k3dit)+quality(k3lity) 各出 12 列
          待修>0 → 问「agent 修?」→ 重审；>3 次未闭环 → ESCALATED 转人工
          两份报告 待修=0 → SEAL_READY → 问「封板?」→(milestone seal)→ SEALED → closure(收摊)
```

要点（判据见 [`overview.md`](overview.md) §6–7 与 `peer_contract`）：
- **审计闭环 = 封板唯一界限**；自动触发只服务「要不要审」，「要不要封」只在闭环后出现一次。
- 交换介质 = 审计线（分支+现场）+ 钉（§3.2/§3.4）；`sign-report` 署名才算结案；`collect` 幂等可重试，`EXPIRED/NOT_FOUND` ⇒ 锁新基线重送。
- `on_seal_enter`（audit+quality 两份必做）与 `on_pre_seal`（各自 verify）配置在 `.agent/pipeline.toml`；两条腿都验完 seal 才放行。
- 外来审计源经 `k3dge milestone audit-submit`（MCP `k3dge_submit_audit_report`，`--kind quality` 同理）落盘即计入闭环。
- 发现用 `k3dit:pending <ID>` 钉在位置（仅指针）；已修删钉，有意留改 `k3dit:leftover`。

## 8. 开放问题与活文档

| 哪类 | 在哪看 | 说明 |
| --- | --- | --- |
| 未完成任务 | `k3dge task list --json`（含 Milestone/Status/Priority） | `[R]` 无里程碑的在 `archive/untagged/` |
| 有意留 | `docs/reviews/LEFTOVERS.md` | 唯一事实源；新审计前必读，不重开已留 ID |
| 审计报告 | `k3dge doc list --type reviews` | `archive/<id>/` 是已封板里程碑 |
| 闪念 | `k3dge doc list --type memo` | 三种暂不成事；永不进门禁 |
| 事故 | `k3dge doc list --type incidents` | 持续偏离记录 |
| 红闸勘误 | `docs/branches/` | `check` 红 ×2 时走：branches → stash |

主 memo 一览（k3dge doc where，按 `docs/memo/`）：

- `2026-08-21-deferred-standards` — 未落地的对标项（6 类标准评估小结）
- `2026-08-25-prompt-as-neural-net` — Prompt as Neural Net，稀疏门控解释框架
- `2026-08-27-h8m2k-a1-harness-hard-isolation` — harness 环境级硬隔离 vs 认知级软隔离
- `2026-09-02-peer-wiring-and-seat-options` — peer 接线与审计席位的选项账（研究用，不作决策）
- `2026-09-05-graph-lens-for-audit-and-qa` — 图论视角的审计/优化应用 + audit/QA 三段拆分（讨论底稿）

已归档：`2026-09-02-plugins-main-absorption-eval`（P1-P3 全账核清，结项记录在 `archive/`，落点以各 peer ADR/tests 为权威）。

## 9. 相关入口速查

- `README.md`（仓根）— 项目门面
- `CHANGELOG.md`（仓根）— Keep a Changelog + SemVer，`k3dge version bump` 自动维护
- `AGENTS.md` — Agent 执行协议：核心不变量 / 文档路由 / 12 触发器 / 证据链（§13）
- [`overview.md`](overview.md) — 系统全貌（唯一叙事判据）
- `docs/guides/` — `client_intro`(甲方) / `user_guide`(用法) / `architecture`(人读导读) / `mcp-bridge`(MCP 剧本) / `downstream`(下游升级) / `changelog`(版本写作)
- `docs/protocols/peer_contract.md` — **权威源在 GitHub `<repo>/docs/protocols/peer_contract.md`**；本地为工作副本
- `docs/reviews/LEFTOVERS.md` — 有意留表