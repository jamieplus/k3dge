# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- doc-audit: 文档作者合规审计（architecture 等 3 处）

## [0.1.9] - 2026-09-05

### Added
- G3 换源：`roles.audit.mode="ratchet"` 幂等步进器（建单/探单/collect/写回重试一体；旧一次性链降为缺省形，quality 腿不变
- 首案真跑闭环（job ae911e744eff）：席 10 findings＝7 fixed＋3 有意留；主干带回 F-1/F-2/F-5/F-6/A-2/A-3/F-3 修复；vanished×角色门互锁与进程提交绕闸两处活体缺陷当场修
- P0 present 推送接线：`audit_flow.push_present`（submit 首程底＋`audit advance` 随程推），pipeline `audit.present`；k3dit 缺口回填见其 gap 单
- ratchet v3 exchange implementation ledger（施工账本体）
- ratchet v3 施工十单封账凭条
- 真跑前置：席位工单棘轮化 + ratchet_open 路由
- 席位工单棘轮化（G1）＋ `[NEXT] ratchet_open` 路由：编排认识在办工单（G2）
- ratchet v3 施工账十单全绿（ADR-0024 落地）：bundle 单文件交换原子＋身份/位置分家（②④）；分支工作现场 ensure/advance CAS/merge_back P1＋seal prune 钩子（③⑤⑦）；k3dit 句柄透传零代码落盘、角色门（fixed 仅审计席）、audit-report 机械渲染＋署名结案两步（①⑧⑨）；`k3dge audit` 四动词与 `bundle create`（⑩）；peer_contract v0.6 与 memo 化石条目（⑥）
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
