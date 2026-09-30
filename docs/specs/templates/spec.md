# Domain Specification: templates

- **Status**: Active
- **Module Path**: `src/k3dge/templates`
- **Contract Hash**: `sha256:aab417420e1cee93a32c7b9aa376d1a109da99cb7fac74f82c8d1aa89539bb44`
- **Last Updated**: 2026-09-30

## 1. Domain Boundary & Responsibilities
- **In Scope**:
  - `k3dge-init.sh` 脚手架：生成 `.agent/` 进程配置（`README.md` 标明非发现面、
    `manifest.json`、`rules/` 完整 00–10 含 `02-simplification.md`、`docs.toml`）、
    `AGENTS.md`、`docs/` 目录树、标准 spec 模板与 `.pre-commit-config.yaml`。
  - 第一条域：目录名（或 `--name`）写入 `domains`、`src/<name>/`、spec、tests；空 domains 的已有 manifest 会被升级。
  - 下游协议包：`docs/guides/mcp-bridge.md`、`docs/guides/downstream.md`、空 reviews 索引与空 `LEFTOVERS.md`、`.gitignore`（不把本仓审计目录拷给下游）。
- **Out of Scope**:
  - 门禁判定（由 `engine` 域负责）。

## 2. Public Interfaces & Type Contracts
<!-- k3dge:interfaces-start -->
```python
ROOT = pathlib.Path(__file__).resolve().parent.parent
args = sys.argv[1:] if len(sys.argv) > 1 else ['check']
venv_k3dge = ROOT / '.venv' / ('Scripts/k3dge.exe' if os.name == 'nt' else 'bin/k3dge')
k3dge = shutil.which('k3dge')
from __future__ import annotations
from importlib import resources
from pathlib import Path
from typing import Optional
from typing import Sequence
AGENTS_TEMPLATE = _asset('agents.md')
SPEC_TEMPLATE = _asset('spec.md.template')
GATE_SH_TEMPLATE = _asset('gate.sh')
GATE_PY_TEMPLATE = _asset('gate.py')
GATE_PS1_TEMPLATE = _asset('gate.ps1')
K3DGE_INIT_SH_TEMPLATE = _asset('init.sh')
K3DGE_INIT_WRAPPER = _asset('k3dge-init-wrapper.sh')
K3DGE_INIT_PS1_WRAPPER = _asset('k3dge-init-wrapper.ps1')
INIT_PS1_TEMPLATE = _asset('init.ps1')
DOCS_TOML_TEMPLATE = _asset('docs.toml.template')
PIPELINE_TOML_TEMPLATE = _asset('pipeline.toml.template')
GENERATE_DOCS_SH_TEMPLATE = _asset('generate-docs.sh')
GENERATE_DOCS_PS1_TEMPLATE = _asset('generate-docs.ps1')
PRE_COMMIT_TEMPLATE = _asset('pre-commit.yaml.template')
PRE_COMMIT_HOOK_TEMPLATE = _asset('pre-commit')
COMMIT_MSG_HOOK_TEMPLATE = _asset('commit-msg')
ARCHITECTURE_TEMPLATE = _asset('architecture.md.template')
REVIEWS_README_TEMPLATE = _asset('reviews-readme.md')
MCP_BRIDGE_TEMPLATE = _asset('mcp-bridge.md.template')
GITIGNORE_TEMPLATE = _asset('gitignore.template')
ADR_README_TEMPLATE = _asset('adr-readme.md.template')
DOWNSTREAM_GUIDE_TEMPLATE = _asset('downstream.md')
PROTOCOL_TEMPLATE = _asset('protocols/audit_default.md')
VERIFY_PROTOCOL_TEMPLATE = _asset('protocols/verify_default.md')
QUALITY_PROTOCOL_TEMPLATE = _asset('protocols/quality_default.md')
TASKS_README_TEMPLATE = _asset('tasks-readme.md')
BRANCHES_README_TEMPLATE = _asset('branches-readme.md')
MEMO_README_TEMPLATE = _asset('memo-readme.md')
RULE_ASSETS = ('00-core-discipline.md', '01-docs-structure.md', '02-simplification.md', '03-self-contained.md', '04-milestone.md', '05-branches.md', '06-memo.md', '07-audit.md', '08-design-discipline.md', '09-absorption.md', '10-structure-over-prose.md', '11-next-sidecar.md', '12-introduction-discipline.md')
ensure_mcp_config(target: Path) -> bool
scaffold(target: Path, name: str | None=None) -> list
main(argv: Optional[Sequence[str]]=None) -> int
```
<!-- k3dge:interfaces-end -->

## 3. State Machine & Invariants
- 脚手架幂等：已存在的文件不被覆盖（除明确安全的模板外）。
- `.agent/rules/*.md` 从 `templates/assets/rules/` 整文件拷出，禁止空标题桩；必须含 Rule 02（ADR-0010）。
- `.agent/README.md` 从 `templates/assets/agent-readme.md` 拷出（ADR-0010：标明本目录是进程配置，不是 Agent 发现面）。

## 4. Verification Matrix
| Scenario ID | Level | Input Condition | Expected Outcome | Test File |
| --- | --- | --- | --- | --- |
| TC-TPL-01 | L0 | 对空目录执行 init | 生成 manifest 与 docs 树 | `tests/unit/templates/test_scaffold.py::test_generates_tree` |
| TC-TPL-02 | L0 | 对空目录执行 init | `.agent/rules/` 含完整 00–10（含 02，非空标题） | `tests/unit/templates/test_template_sync.py::test_all_expected_assets_exist` |
| TC-TPL-03 | L0 | assets/rules 与本仓 `.agent/rules` | 字节级一致 | `tests/unit/templates/test_template_sync.py::test_templates_match_repo_scripts` |
| TC-TPL-04 | L0 | 对空目录执行 init | 写出 `.agent/README.md`（标明进程配置） | `tests/unit/templates/test_scaffold.py::test_generates_tree` |
| TC-TPL-05 | L0 | 对空目录 scaffold | 至少一域 + mcp-bridge + 空 reviews 索引 + gitignore | `tests/unit/templates/test_scaffold.py::test_generates_tree` |
| TC-TPL-06 | L0 | 对空目录 scaffold | `scripts/pre-commit` 与 `scripts/commit-msg` 落地且**可执行**（否则 git 静默跳过 hook） | `tests/unit/templates/test_hooks_reach_downstream.py::test_hook_scripts_are_shipped_and_executable` |
| TC-TPL-07 | L0 | 对空目录 scaffold | `docs/{specs,guides,protocols,architecture,generated}` 各带 README + AUTHORING（否则下游第一次提交被 doc-gate 拦） | `tests/unit/templates/test_hooks_reach_downstream.py::test_governance_files_exist_for_every_docs_type` |
| TC-TPL-08 | L1 | init 仓按 AGENTS.md 激活 `core.hooksPath scripts` 后提交 | hook 真跑三层闸（doc-gate PASS）；缺 AUTHORING 时 commit 被拦 | `tests/unit/templates/test_hooks_reach_downstream.py::test_missing_authoring_blocks_the_commit` |
| TC-TPL-09 | L1 | scaffold 写协议文本（AGENTS.md/.agent/rules/README）进下游仓 | 裸 ADR 引用自限定为 `k3dge ADR-NNNN`（防指错靶）；`where ADR-NNNN` 与本仓 adr/README 示例不限定、幂等不重复限定 | `tests/unit/templates/test_reference_portability.py` |
