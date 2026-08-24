# Domain Specification: cli

- **Status**: Active
- **Module Path**: `src/k3dge/cli`
- **Contract Hash**: `sha256:af3a444335eee8d175e79ce605f910d23a23ecea2a9da619ad3d7bf2d7d5b172`
- **Last Updated**: 2026-08-24

## 1. Domain Boundary & Responsibilities
- **In Scope**:
  - 本仓原生入口：`k3dge check` / `sync` / `milestone`（shell、pre-commit、CI）。
  - 对外 harness 注入：`k3dge.cli.mcp` 把同一套 engine 事实以 MCP stdio 交给 DSH / Codex / Claude Code / OpenCode 等，禁止那些工具私有重实现门禁（ADR 0006）。
  - 不负责判定（engine）与透镜审计（`harnesses/audit`）。
  - `check` 支持 `--json` 机器可读输出，以及 `--with-tests`（selective L2）与 `--force-full`（全域 L0/L1）。
  - 从当前目录向上定位 workspace 根（含 `.git` 或 `.agent`）。
  - 将引擎返回的 `GateReport` 渲染为终端输出并映射退出码。
  - MCP 桥接（`k3dge.cli.mcp`）：资源读 spec、工具委托 `evaluate` / `verify_contract` / `milestone`。
- **Out of Scope**:
  - 一致性判定逻辑（由 `engine` 域负责）。
  - spec 回写（由 `sync` 域负责）。

## 2. Public Interfaces & Type Contracts
<!-- k3dge:interfaces-start -->
```python
# main.py
cmd_check(args: argparse.Namespace) -> int
cmd_sync(args: argparse.Namespace) -> int
cmd_version(args: argparse.Namespace) -> int
cmd_milestone(args: argparse.Namespace) -> int
build_parser() -> argparse.ArgumentParser
main(argv: Optional[Sequence[str]]=None) -> int
# mcp.py
get_manifest_resource(workspace_path: Optional[str]=None) -> str
get_domain_spec_resource(domain: str, workspace_path: Optional[str]=None) -> str
k3dge_check(workspace_path: Optional[str]=None, with_tests: bool=False, force_full: bool=False) -> str
k3dge_verify_domain_contract(domain: str, workspace_path: Optional[str]=None) -> str
k3dge_milestone_control(action: str, milestone_id: str, workspace_path: Optional[str]=None) -> str
k3dge_5pass_audit_prompt(pass_number: int, target_scope: str, context_snippet: str) -> str
```
<!-- k3dge:interfaces-end -->

## 3. State Machine & Invariants
- `check` 退出码：`0` 当且仅当 `GateReport.passed` 为真。
- `--json` 输出结构稳定，便于 CI 与 Agent 机器消费。

## 4. Verification Matrix
| Scenario ID | Level | Input Condition | Expected Outcome | Test File |
| --- | --- | --- | --- | --- |
| TC-CLI-01 | L1 | 门禁失败运行 `check` | 退出码非零 | `tests/unit/cli/test_main.py` |
| TC-CLI-02 | L1 | `milestone status/align/seal` 路由 | 正确解析并分发至 `milestone` 引擎 | `tests/unit/engine/test_milestone.py` |
| TC-CLI-03 | L1 | `check --force-full` / MCP `force_full` | 校验全部 `manifest.domains`，不限于 git 触及域 | `tests/unit/engine/test_evaluator.py` |
| TC-CLI-04 | L1 | MCP 资源缺失 / 非法 action | 统一 `{"ok": false, "error": ...}` JSON | `tests/unit/cli/test_mcp.py` |
