# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-08-23

### Added
- Spec-gate harness 基线：`engine`/`cli`/`sync`/`templates` 四域契约门禁
- `k3dge check` / `sync` / `milestone`（`status|align|seal` 三闸机）与 `mcp` 零漂移桥接
- 自动版本：`pyproject.toml` 单源，镜像至 `.agent/manifest.json` 与 `src/k3dge/__init__.py`，`VERSION_MISMATCH` 门禁
- `k3dge version show|bump`（`--major|--minor|--patch|--set`，`-m` 变更说明）与 `milestone seal` 自动 `patch`  bump
