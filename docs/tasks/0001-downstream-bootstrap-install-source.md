# 记录：下游 bootstrap 的安装源问题

- **Status**: done
- **Priority**: P2
- **Date**: 2026-08-19

## 背景
`k3dge-init.sh` 生成的下游安装命令用 `pip install pre-commit k3dge`，
其中 `k3dge` 依赖 PyPI。在 k3dge 尚未发布到 PyPI 之前，该命令会失败。

## 待决定
- 将安装源改为可配置（如 `pip install -e <path/to/k3dge>` 或本地 wheel），
- 或发布 k3dge 到 PyPI 后该问题自然消失。

## 当前决定
**本地自用**（ADR 0005）：本仓 `k3dge-init` 默认 `pip install -e ".[dev]"`。初始化其他目录时设 `K3DGE_SOURCE` 指向 k3dge 检出。不依赖 PyPI。

## 追加（2026-08-24 8 维审计 S-12）
`scripts/init.sh` 文件头注释写「Defaults to editable install of this repo (.[dev])」，
`else` 分支实际是 `pip install pre-commit k3dge`（PyPI），注释与实现相反。
修复安装源时必须同步改掉该注释（以及 `templates/assets/init.sh`，有 `test_template_sync` 锁）。
PowerShell 轨 `init.ps1` 无这句假注释，但默认同样走 PyPI。
