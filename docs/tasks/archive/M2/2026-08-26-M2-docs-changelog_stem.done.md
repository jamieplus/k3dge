# 变更日志仅透 file stem 未读人话摘要

- **Status**: done
- **Milestone**: M2
- **Priority**: P1
- **Date**: 2026-08-26

## 已确认意图
seal 的 changelog 仅透 archive 文件 stem，未读任务内可检索摘要的人话，致 0.1.3/0.1.4 如任务列表

## 可检索摘要
cli/main.py:313 的 seal 按 archive/M2/*.md 的 stem 拼 task_list，未读 tasks 内 可检索摘要 的人话，致 CHANGELOG.md 0.1.3/0.1.4 为文件名列表而非人话变更；M1 的 0.1.2 人话为对照

## 上下文/切入点
触发于 M2 seal 时的 changelog 生成，切入点 src/k3dge/cli/main.py 的 seal 与 src/k3dge/engine/version.py 的 append_changelog
