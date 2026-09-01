# Domain Specification: templates

- **Status**: Active
- **Module Path**: `src/k3dge/templates`
- **Contract Hash**: `sha256:a4ab9ea5a48acd5349a3344361560fd60cd1001f4020489108fd737b895a0b3a`
- **Last Updated**: 2026-08-27

## 1. Domain Boundary & Responsibilities
- **In Scope**:
  - `k3dge-init.sh` 脚手架：生成 `.agent/` 进程配置（`README.md` 标明非发现面、
    `manifest.json`、`rules/` 完整 00–03 含 `02-simplification.md`、`docs.toml`）、
    `AGENTS.md`、`docs/` 目录树、标准 spec 模板与 `.pre-commit-config.yaml`。
  - 第一条域：目录名（或 `--name`）写入 `domains`、`src/<name>/`、spec、tests；空 domains 的已有 manifest 会被升级。
  - 下游协议包：`docs/guides/mcp-bridge.md`、`docs/guides/downstream.md`、空 reviews 索引与空 `LEFTOVERS.md`、`.gitignore`（不把本仓审计目录拷给下游）。
- **Out of Scope**:
  - 门禁判定（由 `engine` 域负责）。

## 2. Public Interfaces & Type Contracts
<!-- k3dge:interfaces-start -->
```python
ensure_mcp_config(target: Path) -> bool
scaffold(target: Path, name: str | None=None) -> None
main(argv: Optional[Sequence[str]]=None) -> int
```
<!-- k3dge:interfaces-end -->

## 3. State Machine & Invariants
- 脚手架幂等：已存在的文件不被覆盖（除明确安全的模板外）。
- `.agent/rules/*.md` 从 `templates/assets/rules/` 整文件拷出，禁止空标题桩；必须含 Rule 02（ADR-0010）。
- `.agent/README.md` 从 `templates/assets/agent-readme.md` 拷出（ADR-0011：标明本目录是进程配置，不是 Agent 发现面）。

## 4. Verification Matrix
| Scenario ID | Level | Input Condition | Expected Outcome | Test File |
| --- | --- | --- | --- | --- |
| TC-TPL-01 | L0 | 对空目录执行 init | 生成 manifest 与 docs 树 | `tests/unit/templates/test_scaffold.py::test_generates_tree` |
| TC-TPL-02 | L0 | 对空目录执行 init | `.agent/rules/` 含完整 00–03（含 02，非空标题） | `tests/unit/templates/test_template_sync.py::test_all_expected_assets_exist` |
| TC-TPL-03 | L0 | assets/rules 与本仓 `.agent/rules` | 字节级一致 | `tests/unit/templates/test_template_sync.py::test_templates_match_repo_scripts` |
| TC-TPL-04 | L0 | 对空目录执行 init | 写出 `.agent/README.md`（标明进程配置） | `tests/unit/templates/test_scaffold.py::test_generates_tree` |
| TC-TPL-05 | L0 | 对空目录 scaffold | 至少一域 + mcp-bridge + 空 reviews 索引 + gitignore | `tests/unit/templates/test_scaffold.py::test_generates_tree` |
