# User Guide

> 基础版本由 `./scripts/generate-docs.sh` 按 `.agent/docs.toml` 生成，`AGENTS.md:33` 为执行依据。

## 概述

本项目使用 `k3dge` harness 约束 AI 协作，`docs/guides/` 为人写导读，`docs/generated/` 机器生成（Diátaxis Reference）。

## Memo 显式用法（灵光闪念）

与 `docs/tasks/`（有方案的容器，Status/Priority 区分成熟度与排序）互补，`docs/memo/` 收三类**暂不成事**的念头：模糊概念（无方案）、暂无法落地、弱相关闪念。触发即落盘 `docs/memo/YYYY-MM-DD-<slug>.md`：

* **你显式说**：`memo一下` / `灵感记一下` / `这个不排期先存着` → Agent 当轮必写
* **Agent 发现无法成方案或域外溢出** → 主动问"先 memo？"，你确认后写
* **成熟后晋升**进 tasks 并赋 Priority，原 memo 移入 `docs/memo/archive/`（不再被扫描）

单条形态见 `docs/memo/README.md`，永不进门禁，不排期，仅备查。

## 本仓门禁与 CI

- 本地默认：`k3dge check`（git 触及域）。提交钩子同样是这条。
- CI 与封板对齐：`k3dge check --force-full --with-tests`（见 `.github/workflows/ci.yml`），再 `pytest -q`。
- 自举安装 `pip install -e ".[dev]"` 已含 MCP。配 MCP 剧本见 [`mcp-bridge.md`](mcp-bridge.md)。

## 下游仓升级

别的工程用 `K3DGE_SOURCE` 挂本 harness 时（三种合法源：本地路径＝editable、`git+https://…`＝非 editable 直引、保留词 `pypi`＝包索引）：闸和 `k3dge task list` 等工具在 `.venv` 的 k3dge 包里；`AGENTS.md` / `scripts/gate.*` 是 init 当时拷进去的。源更新后怎么升、再跑 init 会不会覆盖，见 [`downstream.md`](downstream.md)。

