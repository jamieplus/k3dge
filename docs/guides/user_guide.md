# User Guide

> 基础版本由 `./scripts/generate-docs.sh` 按 `.agent/docs.toml` 生成，`AGENTS.md:33` 为执行依据。

## 概述

本项目使用 `k3dge` harness 约束 AI 协作，`docs/guides/` 为人写导读，`docs/reference/` 机器生成。

## Memo 显式用法（灵光闪念）

与 `docs/tasks/`（有方案的容器，Status/Priority 区分成熟度与排序）互补，`docs/memo/` 收三类**暂不成事**的念头：模糊概念（无方案）、暂无法落地、弱相关闪念。触发即落盘 `docs/memo/YYYY-MM-DD-<slug>.md`：

* **你显式说**：`memo一下` / `灵感记一下` / `这个不排期先存着` → Agent 当轮必写
* **Agent 发现无法成方案或域外溢出** → 主动问"先 memo？"，你确认后写
* **成熟后晋升**进 tasks 并赋 Priority，原 memo 移入 `docs/memo/archive/`（不再被扫描）

单条形态见 `docs/memo/README.md`，永不进门禁，不排期，仅备查。

