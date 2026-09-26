# Domain Specification: cli

- **Status**: Active
- **Module Path**: `src/k3dge/cli`
- **Contract Hash**: `sha256:4d2b160d3c3566d986a1bdbee3bbcaf4304cc2573fba5e7a800c95268880a8c3`
- **Last Updated**: 2026-09-26

## 1. Domain Boundary & Responsibilities
- **In Scope**:
  - 本仓原生入口：`k3dge check` / `sync` / `milestone` / `version` / `task` / `doc list|where|grep|sync` / `status` / `markers` / `audit` / `search` / `where` / `index` / `commit` / `incident` / `mcp` / `init`（shell、pre-commit、CI）。
  - 对外 harness 注入：`k3dge.cli.mcp` 把同一套 engine 事实以 MCP stdio 交给 DSH / Codex / Claude Code / OpenCode 等，禁止那些工具私有重实现门禁（ADR-0006）。
  - 不负责判定（engine）与透镜审计；`k3dge audit` 是审计线消费侧管理（submit/status/show/advance/materialize/close，ADR-0025 §2.9.2），不是透镜。
  - `check` 支持 `--json` 机器可读输出，以及 `--with-tests`（selective L2）与 `--force-full`（全域 L0/L1）。
  - 协议治理：`docs/protocols/*.md`（`audit_default.md` / `verify_default.md`，审计 + 复审两层）为 `k3dge scaffold` 脚手架模板，由 `.agent/pipeline.toml` 的 manual-step `protocol` 引用配置（`k3dge check` 经 `PIPELINE_PROTOCOL_NOT_FOUND` 校验）；其余类型规则在各 `docs/<type>/AUTHORING.md`（CLI 不再暴露 `protocol` 子命令）；`incident` 子命令生成 L2 事故记录。
  - 从当前目录向上定位 workspace 根（含 `.git` 或 `.agent`）。
  - 将引擎返回的 `GateReport` 渲染为终端输出并映射退出码。
  - MCP 桥接（`k3dge.cli.mcp`）：资源读 spec、工具委托 `evaluate` / `verify_contract` / `sync` / `version` / `task` / `milestone` / `doc list|where|grep`。零漂移，禁止外仓私有重写哈希。
- **Out of Scope**:
  - 一致性判定逻辑（由 `engine` 域负责）。
  - spec 回写（由 `sync` 域负责）。

## 2. Public Interfaces & Type Contracts
<!-- k3dge:interfaces-start -->
```python
from __future__ import annotations
from pathlib import Path
from typing import Optional
from typing import Sequence
from k3dge.engine import gate_facts
from k3dge.engine.evaluator import ConsistencyEngine
from k3dge.engine.models import GateReport
from k3dge.cli.mcp_peers import cmd_mcp_probe
from k3dge.cli.mcp_peers import cmd_mcp_sync
cmd_check(args: argparse.Namespace) -> int
cmd_sync(args: argparse.Namespace) -> int
cmd_extractor(args: argparse.Namespace) -> int
cmd_version(args: argparse.Namespace) -> int
cmd_doc(args: argparse.Namespace) -> int
cmd_task(args: argparse.Namespace) -> int
cmd_init(args: argparse.Namespace) -> int
cmd_mcp(args: argparse.Namespace) -> int
cmd_audit(args: argparse.Namespace) -> int
cmd_markers(args: argparse.Namespace) -> int
cmd_milestone(args: argparse.Namespace) -> int
old_name_warnings(msg: str) -> List[str]
cmd_search(args: argparse.Namespace) -> int
cmd_where(args: argparse.Namespace) -> int
cmd_index(args: argparse.Namespace) -> int
cmd_commit(args: argparse.Namespace) -> int
cmd_commit_attest(args: argparse.Namespace) -> int
cmd_verify_attest(args: argparse.Namespace) -> int
cmd_check_msg(args: argparse.Namespace) -> int
cmd_incident(args: argparse.Namespace) -> int
cmd_status(args: argparse.Namespace) -> int
build_parser() -> argparse.ArgumentParser
main(argv: Optional[Sequence[str]]=None) -> int
from __future__ import annotations
from pathlib import Path
from typing import Optional
from k3dge.engine import contract
from k3dge.engine.align import run_milestone_alignment
from k3dge.engine.milestone_audit import persist_external_audit_report
from k3dge.engine.milestone_audit import run_audit_flow
from k3dge.engine.seal_flow import run_seal_flow
from k3dge.engine.task_index import list_tasks
from k3dge.engine.task_index import scan_milestone_tasks
from k3dge.engine.task_write import create_task
from k3dge.engine.task_write import mark_task_done
from k3dge.engine.evaluator import ConsistencyEngine
from k3dge.engine.manifest import Manifest
from k3dge.engine.models import GateReport
get_manifest_resource() -> str
get_manifest_resource_for(ws: Path) -> str
get_domain_spec_resource(domain: str) -> str
get_domain_spec_resource_for(domain: str, ws: Path) -> str
k3dge_check(workspace_path: Optional[str]=None, with_tests: bool=False, force_full: bool=False) -> str
k3dge_status(workspace_path: Optional[str]=None) -> str
k3dge_verify_domain_contract(domain: str, workspace_path: Optional[str]=None) -> str
k3dge_sync(domains: Optional[list[str]]=None, workspace_path: Optional[str]=None) -> str
k3dge_version(action: str='show', part: str='patch', set_version: Optional[str]=None, message: Optional[str]=None, workspace_path: Optional[str]=None) -> str
k3dge_task_create(title: str, typ: str='fix', slug: Optional[str]=None, milestone_id: Optional[str]=None, priority: str='P2', workspace_path: Optional[str]=None) -> str
k3dge_task_done(path: str, workspace_path: Optional[str]=None) -> str
k3dge_task_list(milestone_id: Optional[str]=None, status: Optional[str]=None, workspace_path: Optional[str]=None) -> str
k3dge_doc_list(typ: Optional[str]=None, ident: Optional[str]=None, q: Optional[str]=None, include_archive: bool=False, workspace_path: Optional[str]=None) -> str
k3dge_doc_where(ident: str, workspace_path: Optional[str]=None) -> str
k3dge_doc_grep(query: str, typ: Optional[str]=None, line: bool=False, include_archive: bool=False, workspace_path: Optional[str]=None) -> str
k3dge_milestone_control(action: str, milestone_id: str, workspace_path: Optional[str]=None) -> str
k3dge_submit_audit_report(milestone_id: str, content: str, workspace_path: Optional[str]=None) -> str
k3dge_5pass_audit_prompt(pass_number: int, target_scope: str, context_snippet: str) -> str
k3dge_adr_index(workspace_path: Optional[str]=None) -> str
from __future__ import annotations
from pathlib import Path
from typing import Optional
from k3dge.engine.mcp_json import probe_peer_mcp
cmd_mcp_sync(workspace: Path) -> int
cmd_mcp_probe(args, workspace: Path) -> int
from __future__ import annotations
from pathlib import Path
from typing import Any
from typing import Dict
from k3dge.engine.evaluator import ConsistencyEngine
from k3dge.engine.manifest import Manifest
from k3dge.engine.manifest import ManifestError
from k3dge.engine.task_index import parse_frontmatter
cache_observability(workspace: Path) -> Optional[Dict[str, Any]]
lifecycle_next(workspace: Path) -> Any
workspace_status(workspace: Path) -> Dict[str, Any]
```
<!-- k3dge:interfaces-end -->

## 3. State Machine & Invariants
- `check` 退出码：`0` 当且仅当 `GateReport.passed` 为真。
- `--json` 输出结构稳定，便于 CI 与 Agent 机器消费。

## 4. Verification Matrix
| Scenario ID | Level | Input Condition | Expected Outcome | Test File |
| --- | --- | --- | --- | --- |
| TC-CLI-01 | L1 | 门禁失败运行 `check` | 退出码非零 | `tests/unit/cli/test_main.py::test_check_exit_nonzero_on_drift` |
| TC-CLI-02 | L1 | `milestone status/align/seal` 路由 | 正确解析并分发至 `milestone` 引擎 | `tests/unit/engine/test_milestone.py::test_scan_filters_milestone` |
| TC-CLI-03 | L1 | `check --force-full` / MCP `force_full` | 校验全部 `manifest.domains`，不限于 git 触及域 | `tests/unit/engine/test_evaluator.py::test_force_full_checks_untouched_domain` |
| TC-CLI-04 | L1 | MCP 资源缺失 / 非法 action / `manifest` 损坏 | 统一 `{"ok": false, "error": ...}` JSON（`ManifestInvalid`） | `tests/unit/engine/test_pipeline_schema.py::test_mcp_missing_tool` |
| TC-CLI-05 | L1 | `version show|bump` 与 `seal` 自动 patch（含 `consume_unreleased`） | 版本三件套镜像 + `CHANGELOG.md` 按 `Unreleased` 正文双轨一致、原子回滚 | `tests/unit/engine/test_version.py::test_bump_patch_updates_all` |
| TC-CLI-06 | L1 | `task list --json` / MCP `k3dge_task_list` | 顶层 tasks 索引，不含正文、不含 archive | `tests/unit/cli/test_mcp.py::test_task_list_json` |
| TC-CLI-07 | L1 | MCP `k3dge_sync` / `k3dge_task_create` / `k3dge_task_done` | 与 CLI 同一套 engine/sync，done 优先精确 path | `tests/unit/cli/test_mcp.py::test_verify_collects_once` |
| TC-CLI-08 | L1 | `mcp sync` 遇损坏 `.mcp.json`（非 dict/JSON 错误）或 `pipeline.toml` 损坏/缺解析器 | 损坏 `WARN` 不覆盖且 `0` 放行；`pipeline.toml` 解析失败 `1`；缺 `tomli` 跳过不假失败 | `tests/unit/cli/test_main.py::test_init_creates_harness` |
| TC-CLI-09 | L1 | 提交信息里裸写 `k3ge`（正确名 k3dge；无此仓） | 只提示不阻断（advisory）；反引号跨度＝引用该错写时不提示 | `tests/unit/cli/test_old_name_warning.py` |
