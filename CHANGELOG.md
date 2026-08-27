# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
