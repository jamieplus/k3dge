# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Event Log：`.k3dge/events.jsonl` 操作事实日志

- 统一 [NEXT] 通道：stdout + sidecar 双投递
- 提取器生成器：`.agent/extractors.toml` + `k3dge extractor sync`
- 多处理点交付：sidecar 单槽 → 列表 + STATE_OPTIONS priority（[NEXT] 复数处理点）
### Changed
- 归档 Rust memo（ADR-0001 §2.9 已否决重写）；gap-trap proven-red 进审计协议 Pass 4；可检规则配闸进 `AGENTS.md` §12
- 删除 `engine.milestone` 兼容门面；CLI/测试直连叶子模块
- engine 内部不再经 `milestone` 门面 import；闸核禁依赖生命周期；`.mcp.json` 读取归 `engine/mcp_json`
- 清活协议面：去掉 k3lity 点名与 4-peers 枚举，改按 pipeline.toml 角色路由

- engine 解耦：门面不再当总线 + 闸核禁依赖生命周期 + mcp.json 单读取器
- 删除 engine.milestone 兼容门面，调用方直连叶子
- 归档 Rust memo；gap-trap ① 进审计协议、⑤ 进 §12 触发
- 复杂度债续（非 milestone 文件）：CC≥11 函数逐个拆
- P2: 7 处时间戳加时区偏移
- 重构：提取 MCP peer 管理出 cli/main.py
- 流程精简：审计腿模式显式化 + 修 doc-audit 空壳票
- 术语撞名：审计腿 mode "scaffold" → "oneshot"
- 路线残留清理：frontmatter 三头 + doc_catalog 死代码 + parse_doc_schema 去重
- 抽取零依赖 schema 校验层：`scripts/lib/schema_check.py`
- 术语清理：deferred 值级碰撞 + 两处重复常量
- ADR 归档移出封板（seal → sync）+ 删冗余 gates.toml
- 落 ADR：投影三维契约（目标 × 语法 × 范围）
- 判定到动作的结构化派发：gate_id 到 action（替掉散文子串匹配）
- 判定点单源化：prompt 文案源出 STATE_OPTIONS
- 编排骨架收敛·第一刀：闸红文案单源 + 阻断档位统一（Violation 只产 code+事实，文案/severity/options 归声明）
- ADR 编号截断：废物理删除、退役单一面 obsolete/、13 个永久退役号入表、分配=max+1、复用可机检
- ADR-0026 追加：D 线不变量（k3dge 不编排自主↔自主）+ 骨架声明的下游可配边界
- ADR 修正案：doc 规约化策略重划（C1-C5：0022 §2.2 时机/产物、0005 §2.7 同形同路、耐久改闸、先并入后新建配闸）
- ADR 合并退役：reconcile 不覆盖合并路径 + obsolete/ 去向字段无闸（merged-into 无人写无人验）
- 编排骨架收敛·节点表：pipeline.toml [checks.*] 单一声明面 + 五属性 + ctx + 单执行器（下游可配）
### Fixed
- seal/align 任务扫描不含 archive/<M>/：提前归档的 done 里程碑任务致封板被拒（No tasks found）

- closure 收摊模板陈旧：写死「审计双腿闭环」+ 版本记 bump 前值（应与合并审计模块单份报告/终版一致）
- audit job 19d4564724ca: src,docs
- doc-audit: 文档作者合规审计（adr, guides, memo 等 4 处）
- 业务逻辑闸：task 元数据 frontmatter ↔ body 分歧检测
- 补测试：4 个零覆盖/浅覆盖的关键 engine 模块
- 引用便携：k3dge 的 ADR 引用在下游仓指错靶
- doc-audit 改动集只看未提交：先提交即集体失明（并回单一源 diff.get_changed_files）
- pipelines.on_seal_enter/on_pre_seal 无执行者：AGENTS.md §12 声称的 seal hook 机制不存在（接通或废声明，只留一套声明面）
- doc-audit: 文档作者合规审计（adr, architecture, guides 等 11 处）
## [0.1.11] - 2026-09-13

### Fixed
- audit job cc4125a36936: src,docs

- audit job 137ed128e134: src,docs

## [0.1.10] - 2026-09-12

### Changed
- k3dge 侧文档/配置对齐合并审计模块（单份 12 列报告、无独立 quality fallback）

### Added
- G1: 审计模块合并 + 接口冻结（一本账）

- G2: Hall 内核常驻进程（人肉窗先行）
- G3: W1 席目录墙 + 签名钥验签（先 opencode/pi 两宿主）
- G3b: CLI root 白名单能力实测（W1 前置探测）
- G4: 窗版工单 + 工具事实注入 + 复核声明模型
- G5: W2 轮间清场 + W6 看门狗注入
- G6: 割接（seal hook/消费侧/k3lity 归档）
- G7: Hall 测试骨架（W1/W2/W6/账本复算）
- G8: 进程侧观测（统计席位+逃逸率+观测行）
- 修席接受改由快照 diff 推断（禁二值空翻已修）
- 空转熔断机制化（W6 活性墙的最小实现）
### Fixed
- doc-audit: 文档作者合规审计（architecture 等 3 处）

- 核 milestone 棘轮对 collect=open(待修>0) 是否误判 closed
- 审计 scope=src 时模板 pairs 不可同步致 verify TEMPLATE_DRIFT 假红
- 判读席禁止重提已 leftover

## [0.1.9] - 2026-09-05

### Added
- G3 换源：`roles.audit.mode="ratchet"` 幂等步进器（建单/探单/collect/写回重试一体；旧一次性链降为缺省形，quality 腿不变
- 首案真跑闭环（job ae911e744eff）：席 10 findings＝7 fixed＋3 有意留；主干带回 F-1/F-2/F-5/F-6/A-2/A-3/F-3 修复；vanished×角色门互锁与进程提交绕闸两处活体缺陷当场修
- P0 present 推送接线：`audit_flow.push_present`（submit 首程底＋`audit advance` 随程推），pipeline `audit.present`；k3dit 缺口回填见其 gap 单
- ratchet v3 exchange implementation ledger（施工账本体）
- ratchet v3 施工十单封账凭条
- 真跑前置：席位工单棘轮化 + ratchet_open 路由
- 席位工单棘轮化（G1）＋ `[NEXT] ratchet_open` 路由：编排认识在办工单（G2）
- ratchet v3 施工账十单全绿（ADR-0025 落地）：bundle 单文件交换原子＋身份/位置分家（②④）；分支工作现场 ensure/advance CAS/merge_back P1＋seal prune 钩子（③⑤⑦）；k3dit 句柄透传零代码落盘、角色门（fixed 仅审计席）、audit-report 机械渲染＋署名结案两步（①⑧⑨）；`k3dge audit` 四动词与 `bundle create`（⑩）；peer_contract v0.6 与 memo 化石条目（⑥）
- task create duplicate check via cache role

- k3dge 出向 MCP 客户端与 endpoint 唯一事实源
### Fixed
- 首夜案卷互踩事故：collect 落盘命名按 role；案卷防跨类覆盖闸；签署件自机构账本复原（INC-20260904-AUD-01）
- k3dge status 抛 NameError 致 [NEXT] 永不输出

- task list 把 docs/tasks/AUTHORING.md 当幽灵任务
- k3che 检索索引把 docs/*/AUTHORING.md 当语料
- audit job ae911e744eff: src
- audit job 0300799a8a4a: src
- k3dge 自身 MCP server 在 mcp 2.x 下无法启动（resource 严格校验）
- doc-audit: 文档作者合规审计（本轮 docs 改动 26 处）
### Changed
- `k3dge milestone seal` archives this-milestone reviews to `docs/reviews/archive/<id>/` and rewrites leftover hrefs in `docs/reviews/LEFTOVERS.md`.
- Move the intentional-leftovers table from `docs/reviews/README.md` to `docs/reviews/LEFTOVERS.md`.
- Align ADRs 0001–0006 / 0008 / 0010 with current AGENTS, 0018 catalog, and pipeline `[peers]` schema.
- `k3dge check` rejects legacy `pipeline.toml` `[harnesses]` / `[hooks]` keys (`PIPELINE_SCHEMA_INVALID`).
- Move per-type structure gates from README comment blocks to `docs/<type>/.schema.json`.
- Move per-type soft rules from README `## Authoring` to `docs/<type>/AUTHORING.md`.

- ADR-0006 就地修订为入向/出向双向契约 + AUTHORING 例外条款

## [0.1.8] - 2026-08-27

### Fixed
- fix AGENTS route 05 branches misroute

- fix architecture guide dangling overview links
- fix audit rule deprecated protocol path
- fix mcp-bridge deprecated protocol pointer
- fix template sync missing protocols asset

## [0.1.7] - 2026-08-27

### Added
- k3che 接 GateReport 入 BranchThrottler 闭环
- k3lity 为 INC-20260826-REG 补 B-T-D 复现用例

## [0.1.6] - 2026-08-26

### Fixed
- `mcp.json` 损坏/非 dict 时静默覆盖丢 peer（`src/k3dge/templates/scaffold.py:115`）
- `tomllib` py3.10 缺失时 `mcp sync` 假成功（`src/k3dge/cli/main.py:255`）
- `create_task` 未校验 `milestone` 致 `../` 逃逸（`src/k3dge/engine/milestone.py:194`）

### Changed
- `overview` 补 `cli→templates` 边（`docs/architecture/overview.md:38`）
- `pipeline` 的 `k3dit` 降级 `python -m` 改 `k3dit` 控制台脚本

### Security
- 隔离外部 `mcp.json` 损坏覆盖风险

## [0.1.5] - 2026-08-26

### Added
- `k3dge task` 支持 `M1` 编码与 `ls` 快筛（`AGENTS.md:56`）
- `k3dge mcp sync` 幂等合并 `harnesses`（`src/k3dge/cli/main.py:244`）

### Changed
- `HUMAN_CHECKPOINT` 四处双编码收敛为单一事实源（`engine/milestone.py:343`）

### Fixed
- `seal` 的 `CHANGELOG` 双轨漂移（`cli` 列任务清单、`mcp` 仅一句）

## [0.1.4] - 2026-08-26

### Added
- `09-absorption` 规则落地（`docs/adr/0020`）
- `pipeline.toml` 对等 `harnesses` 声明

### Changed
- `AGENTS.md` 微内核 51 行
- `mcp.json` 幂等合并

## [0.1.3] - 2026-08-26

### Added
- `Mastra Observational Memory` 上层 `harness` 落地

### Fixed
- 空 `ignore` 崩闸、`tomllib` 假成功、`NUL` 未拒、`rglob` 符号链接外泄等 7 项 `P1`

## [0.1.2] - 2026-08-25

### Fixed
- `P1-01..08` 空 `ignore`/`UTF-8`/`Windows`/`NUL`/`rglob`/`changelog`/`SemVer` 等 `7` 项 `P1` 修复

## [0.1.1] - 2026-08-24

### Added
- `M0` 19 项：本地安装、契约/`MCP`/封板闸、`.agent` 协议等

## [0.1.0] - 2026-08-23

### Added
- Spec-gate harness 基线：`engine`/`cli`/`sync`/`templates` 四域契约门禁
- `k3dge check` / `sync` / `milestone` 三闸机与 `mcp` 零漂移桥接
