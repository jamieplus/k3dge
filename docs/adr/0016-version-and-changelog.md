# ADR 0016: 自动版本与变更日志

- **Status**: Accepted
- **Date**: 2026-08-24
- **Deciders**: Core Maintainer

## 1. 上下文 (Context)
自举阶段以 `docs/adr/` 与 `docs/reviews/` 为记事，不维护独立版本号（`docs/guides/changelog.md` 原文）。用户提出需要**自动更新的版本号**与**更新说明文档**，且 `milestone seal` 已具备物理封板语义，天然适合触发版本递增。

## 2. 决策 (Decision)

1. **单源**：`pyproject.toml` 的 `project.version` 为唯一事实源，`k3dge version bump` 自动镜像至 `.agent/manifest.json` 与 `src/k3dge/__init__.py`。三者不一致时门禁 `VERSION_MISMATCH` 阻断（`engine/evaluator.py` 内 `validate_versions`）。
2. **Bump 入口**：
   - `k3dge version show` — 查看当前版本
   - `k3dge version bump [--major|--minor|--patch|--set X.Y.Z] [-m "msg"]` — 语义化递增并追加 `CHANGELOG.md`
   - `k3dge milestone seal <id>` 成功后自动 `patch` bump + `CHANGELOG.md` 条目（`Seal milestone <id>.`），`--no-version-bump` 可跳过
3. **变更日志**：根目录 `CHANGELOG.md`（Keep a Changelog + SemVer），`docs/guides/changelog.md` 为人读指南（如何 bump、何时 bump）。`engine/version.py` 负责解析/递增/写回与 `append_changelog`。
4. **不引入 hatch-vcs / setuptools_scm**：自举需改完立刻用同一份代码，`pip install -e` 已满足；`git describe` 派生版本等发行后再议。

## 3. 后果 (Consequences)
- **正**：`seal` 即发版，`CHANGELOG.md` 自动沉淀，无需人肉改三处版本号
- **负**：`seal` 默认 bump 可能与"只想归档不发版"冲突，需显式 `--no-version-bump`
- **何时重开**：需 `git tag` 驱动或 PyPI 发布时，引入 `hatch-vcs` 动态版本
