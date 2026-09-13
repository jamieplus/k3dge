---
status: done
milestone: M9
priority: P3
date: 2026-09-13
---

# 分发：零依赖单件 zipapp（供下游/无 venv 宿主）

- **Status**: done
- **Milestone**: M9
- **Priority**: P3
- **可检索摘要**: 自举阶段不作 PyPI 发布；加一个 **stdlib `zipapp` 单件** `dist/k3dge.pyz`（~1.2MB、零第三方），解决"`k3dge not found`"，供下游仓/无 venv 宿主使用。来源：`rust-k3dge-fit` §5 分发建议（#3）。
- **Date**: 2026-09-13

## Intent
让 k3dge **真能被用**：一个文件，`python dist/k3dge.pyz …` 即用，无需 pip/venv/网络。

## 落点/实现
- `scripts/build-pyz.sh`：`python -m zipapp src -m "k3dge.cli.main:main" -p "/usr/bin/env python3"` → `dist/k3dge.pyz`（`dist/` 已 gitignore）。
- README 增「分发（单件，零依赖）」节；并注明 `[project.scripts] k3dge` 已存（`pipx`/`uv tool install .` 可用）。
- 冒烟测试 `tests/unit/cli/test_pyz.py`：构建 + 从临时目录跑 `--help`。
- 实测：单件 `init <dir>` 端到端成功（zip 内 `assets` 经 `importlib.resources` 可读）；`check` 仅因目标非 git 仓而拒（预期）。

## 边界与拆分
- **零新增依赖/工具链**（zipapp 是 stdlib）；PEP 517 源码安装路径已具备。
- **自举仓专属**的 `TEMPLATE_DRIFT` 依赖磁盘 `templates/assets`（`Path(__file__)`），不在单件保护面——下游/非自举跳过，**预期**。
