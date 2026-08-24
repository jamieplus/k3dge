# Domain Specification: templates

- **Status**: Active
- **Module Path**: `src/k3dge/templates`
- **Contract Hash**: `sha256:b0530264b6f37c3e98c2e6cf4d1a5a4a4bc98e15484d7ce3430862495125e261`
- **Last Updated**: 2026-08-24

## 1. Domain Boundary & Responsibilities
- **In Scope**:
  - `k3dge-init.sh` 脚手架：生成 `.agent/` 进程配置（`README.md` 标明非发现面、
    `manifest.json`、`rules/` 完整 00–03 含 `02-simplification.md`、`docs.toml`）、
    `AGENTS.md`、`docs/` 目录树、标准 spec 模板与 `.pre-commit-config.yaml`。
- **Out of Scope**:
  - 门禁判定（由 `engine` 域负责）。

## 2. Public Interfaces & Type Contracts
<!-- k3dge:interfaces-start -->
```python
# scaffold.py
scaffold(target: Path) -> None
main(argv: Optional[Sequence[str]]=None) -> int
```
<!-- k3dge:interfaces-end -->

## 3. State Machine & Invariants
- 脚手架幂等：已存在的文件不被覆盖（除明确安全的模板外）。
- `.agent/rules/*.md` 从 `templates/assets/rules/` 整文件拷出，禁止空标题桩；必须含 Rule 02（ADR 0012）。
- `.agent/README.md` 从 `templates/assets/agent-readme.md` 拷出（ADR 0014：标明本目录是进程配置，不是 Agent 发现面）。

## 4. Verification Matrix
| Scenario ID | Level | Input Condition | Expected Outcome | Test File |
| --- | --- | --- | --- | --- |
| TC-TPL-01 | L0 | 对空目录执行 init | 生成 manifest 与 docs 树 | `tests/unit/templates/test_scaffold.py` |
| TC-TPL-02 | L0 | 对空目录执行 init | `.agent/rules/` 含完整 00–03（含 02，非空标题） | `tests/unit/templates/test_scaffold.py` |
| TC-TPL-03 | L0 | assets/rules 与本仓 `.agent/rules` | 字节级一致 | `tests/unit/templates/test_template_sync.py` |
| TC-TPL-04 | L0 | 对空目录执行 init | 写出 `.agent/README.md`（标明进程配置） | `tests/unit/templates/test_scaffold.py` |
