# Changelog — 版本与变更说明

> 人读指南：本文件讲**如何记版本**；机器事实在根目录 `CHANGELOG.md`（Keep a Changelog + SemVer，自动更新）。

## 版本单源与自动更新

* **单源**：`pyproject.toml` 的 `project.version` 为唯一事实源（下游脚手架无 `pyproject.toml` 时回退至 `.agent/manifest.json`），`k3dge version bump` 自动镜像至 `.agent/manifest.json` 与 `src/k3dge/__init__.py`（存在时），三者不一致时门禁 `VERSION_MISMATCH` 阻断
<!-- k3dit:pending doc-7 sev=低 prio=P3 type=规范 行首加粗定界符 `** bump…**` 中开 `**` 后紧跟空格不成对，CommonMark 不渲染为粗体而显示字面星号；应为 `**bump 入口…**` -->
* ** bump 入口（本仓与下游通用）**：
  ```bash
  k3dge version show                          # 查看当前版本（有 pyproject 读它，无则读 manifest）
  k3dge version bump --patch -m "fix: xxx"   # 0.1.0 → 0.1.1（默认，改 manifest/CHANGELOG，pyproject 存在时同改）
  k3dge version bump --minor -m "feat: xxx"  # 0.1.0 → 0.2.0
  k3dge version bump --major -m "BREAKING"   # 0.1.0 → 1.0.0
  k3dge version bump --set 1.2.3 -m "release 1.2.3"
  ```
  每次 `bump` 自动在 `CHANGELOG.md` 追加 `## [X.Y.Z] - YYYY-MM-DD` 条目；下游无 `pyproject.toml` 时仅改 `manifest` + `CHANGELOG`
* **里程碑联动**：`k3dge milestone seal <id>` 成功后自动 `patch` bump 并写入 `CHANGELOG.md`（`Seal milestone <id>.`），`--no-version-bump` 可跳过

## 变更历史（摘要）

* **Unreleased**：`[dev]` 含 mcp；下游 init 装 `[mcp]`；CI 为 `--force-full --with-tests`；无 Milestone 的 done 在 `archive/untagged/`
* **0.1.0**（2026-08-23）：基线四域门禁 + `mcp` 桥接 + `5-Pass` 15 项审计全绿
* 详细按 `CHANGELOG.md` 与 `k3dge doc list --type adr` / `--type reviews`
* 活文档搬走/删除须同轮接上扫描入口：ADR-0018

## 概述

需要「发生了什么」时：先读 `CHANGELOG.md` 版本条目，再读 `ADR` 与 `reviews` 摘要。
