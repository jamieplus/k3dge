# bump_version 三件套非原子写，kill 半漂移

- **Status**: done
- **Milestone**: M3
- **Priority**: P1
- **Date**: 2026-08-26

## 已确认意图
bump_version 三件套非原子写，kill 半漂移

## 可检索摘要
bump_version 三件套非原子写，kill 半漂移 位于 src/k3dge/engine/version.py:192，需修复后经 k3dge check --with-tests 与 k3dit 5-Pass 审计验证，确保自包含且可回溯。

## 上下文/切入点
触发于 k3dit 审计，切入点 src/k3dge/engine/version.py:192，关联 2026-08-26-M3-audit-P1_01_bump_version.done.md
