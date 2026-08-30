# Pass 4 一致性与对齐审计 — 契约哈希 / 多轨脚本同构 / 校验矩阵 / 测试存在性 / 脚手架镜像

- **Date**: 2026-08-25
- **Auditor**: Muse Spark (Pass 4 lens only)
- **Scope**: `k3dge check` / `k3dge sync` / `.agent/manifest.json` / `docs/specs/*/spec.md` / `src/k3dge/templates/assets/*` ↔ 仓内成对物 / `scripts/*` 双轨 / Verification Matrix / `tests/unit/**/*`
- **Baseline**:
  - `.venv/bin/k3dge check` → `[GATE SUCCESS] Validated domains: cli, engine, templates` (selective, git 触及域)
  - `.venv/bin/k3dge check --force-full` → `[GATE SUCCESS] Validated domains: cli, engine, sync, templates`
  - `.venv/bin/k3dge check --force-full --with-tests` → `PASS` (4 域全量 L0/L1 + 镜像漂移闸)
  - `.venv/bin/k3dge sync` → `[SYNC] Contracts already up to date.`
  - `pytest -q` → `70 passed, 1 skipped, 44 subtests passed`
  - 4 域 Contract Hash 均已同步（见下「证据链-契约」）
- **Not in scope**: Pass 1/2/3/5（健壮性/拓扑/设计/性能）—— 不重开 §5.1 有意留 A-11/S-13/F-14/F-15/R3-1/R3-4 及 08-24/08-25 已修项；仅在 Pass 4 残余一致性处开单

## 证据链总表（产物 → 消费者 → 到达方式）

| 断言 | 产物（已打开/已执行） | 消费者 | 到达方式 |
| --- | --- | --- | --- |
| 4 域哈希与代码一致 | `docs/specs/{engine,cli,sync,templates}/spec.md: **Contract Hash**` + `src/k3dge/engine/contract.py:231-283` + `bash .venv/bin/python -c collect_domain_interface+compute_hash`（4 域均 `match: True`） | `k3dge.engine.evaluator.ConsistencyEngine.evaluate` → `contract.verify_contract` / `k3dge check` / `k3dge sync` | 硬编码路径 `docs/specs/<domain>/spec.md` + `Manifest.spec_path` + `contract.INTERFACE_START/END` |
| `k3dge sync` 幂等、无漂移 | `src/k3dge/sync/generator.py:67-197` + 执行 ` .venv/bin/k3dge sync` → `already up to date` + 临时改 `src/k3dge/cli/main.py` 加 `dummy_public_api` 后 `sync_all` 正确重算并回写 `dummy_public_api` 到 spec | `cli.main.cmd_sync` → `sync.generator.sync_all` | 硬编码 `sync_domain` / `MANIFEST` 加载 |
| 多轨脚本同构（assets ↔ 仓） | `src/k3dge/templates/assets/{gate.sh,gate.py,gate.ps1,init.sh,init.ps1,generate-docs.sh,generate-docs.ps1,k3dge-init-wrapper.sh,...}` vs `scripts/*` / `k3dge-init.*` / `AGENTS.md` / `.agent/*` / `.pre-commit-config.yaml` 逐对 `diff -u` 均 `OK`（21 对 Same） + `src/k3dge/templates/pairs.py:6-29` + `src/k3dge/templates/scaffold.py:19-127` | `k3dge.engine.evaluator` 内 `TEMPLATE_DRIFT` 段 (`evaluator.py:218-265`) / `tests/unit/templates/test_template_sync.py:13-18` (21 subtests `tests/unit/templates/test_template_sync.py:13`) | `pairs.PAIRS` 单一注册表 + `Path(__file__).resolve().parents[1]/templates/assets` vs `workspace_root` 自举判定 |
| Verification Matrix 文件存在 | `docs/specs/{engine,cli,sync,templates}/spec.md` 第 4 节 `Verification Matrix` 行 + `tests/unit/{engine,cli,sync,templates}/*` 逐项 `Path.exists()` 校验（4 域 17 引用全部 `True`） + `src/k3dge/engine/evaluator.py:299-320` `_TEST_REF_RE` + `_VERIFICATION_MATRIX_RE` | `ConsistencyEngine._check_domain` → `MISSING_TEST_FILE` / `k3dge check --force-full` | 硬编码正则 `` `(tests/[^\\s`]+)` `` 扫描 spec 正文 |
| 脚手架镜像完整性 | `src/k3dge/templates/scaffold.py:80-127` 写出路径清单 + `src/k3dge/templates/assets/spec.md.template` vs `docs/specs/_template/spec.md` `diff OK` + `pytest tests/unit/templates/test_scaffold.py:18-66` | `k3dge.templates.scaffold.scaffold` / `k3dge-init.sh` (`scripts/init.sh:52`) | 硬编码 `_asset()` / `RULE_ASSETS` / `_write_if_missing` |
| 版本三件套一致 | `pyproject.toml:7 version = "0.1.1"` + `.agent/manifest.json:4 version 0.1.1` + `src/k3dge/__init__.py:3 __version__ = "0.1.1"` + `src/k3dge/engine/version.py:93-126 validate_versions` + `.venv/bin/k3dge check` 无 `VERSION_MISMATCH` | `ConsistencyEngine.evaluate` 末段 `validate_versions` | 硬编码三路径 `_pyproject_path` / `_manifest_path` / `_init_path` |

## 契约哈希同步实测（`collect_domain_interface` → `compute_hash` → `spec_schema.extract_contract_hash`）

```
cli       sha256:3f89e5e7f60e889d8b78b0dee11a68474df58df14bb85efe174f8001b4542353  spec match True
engine    sha256:5c0b13ae0cef0d9205da1626a48b3e8750479cb2a58278945c1d22cb4f3d9337  spec match True
sync      sha256:819887211d2dcf80500f558db552b03fbc043c0dc5243fb3571363ba72bbdd8e spec match True
templates sha256:b0530264b6f37c3e98c2e6cf4d1a5a4a4bc98e15484d7ce3430862495125e261 spec match True
```

- `include_doc=False` 时 docstring 变更不触哈希（`contract.py:82-96 _doc_first_line` 仅在 `include_doc=True` 追加 `# doc:`），`include_doc=True` 仅供 `docs/reference/api.md` 展示（`generator.py:179-185 doc_cache`），哈希与展示已解耦（F-08 已修，`k3dge sync` 中 `iface_cache` vs `doc_cache`）。
- `k3dge sync` 调 `contract.collect_domain_interface(src_dir, manifest, workspace, include_doc=False)`，`Last Updated` 仅在 `current_hash != new_hash` 时重写（`generator.py:90-91` 防抖），故 `engine 2026-08-24 / sync 2026-08-23` 日期滞后于今日属预期，非漂移。

## 发现（9 列）

| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P4-01 | 中 | P1 | 缺陷 | sync 域 Verification Matrix 表头缺 `Level` 列，与模板及 engine/cli/templates 三域不一致。模板 `docs/specs/_template/spec.md:21` 为 `\| Scenario ID \| Level \| Input Condition \| Expected Outcome \| Test File \|`，sync 为 `\| Scenario ID \| Input Condition \| Expected Outcome \| Test File \|`。属脚手架镜像对齐遗漏，门禁 `validate_structure` 仅验三节标题存在而不验列头，易导致后续 Agent 误按无 Level 格式追加新用例 | `docs/specs/sync/spec.md:35` vs `docs/specs/_template/spec.md:21`, `docs/specs/engine/spec.md:123`, `docs/specs/cli/spec.md:49`, `docs/specs/templates/spec.md:31` | 待修 | [tasks/2026-08-25-M1-audit-P4_01_sync_Level.md](../tasks/2026-08-25-M1-audit-P4_01_sync_Level.md) | `grep -n "Scenario ID" docs/specs/*/spec.md` 已复现不一致；`src/k3dge/engine/spec_schema.py:8-12` 不拦列头故现不报红 |
| P4-02 | 中 | P1 | 缺陷 | engine 域 `TC-ENG-06` 期望 `VERSION_MISMATCH`/`VERSION_MISSING`，但代码仅产 `VERSION_MISMATCH` 且缺失版本时大多不阻断。`version.py:93-126 validate_versions` 在 `canonical is None`（`pyproject.toml` 与 `manifest` 均缺）时直接 `return []`；`pyproject missing + manifest present` 时仅比 `manifest vs __init__.py`，不报“缺失”。规约名 `VERSION_MISSING` 在仓内无生产方（`grep -rn VERSION_MISSING` 仅命中 spec），与实现不一致；审计曾以 `VERSION_MISMATCH` 为唯一闸（ADR 0017） | `docs/specs/engine/spec.md:130` vs `src/k3dge/engine/version.py:93-126` / `src/k3dge/engine/evaluator.py:205-216` | 待修 | [tasks/2026-08-25-M1-audit-P4_02_TC_ENG_06_VERSION_MISSING.md](../tasks/2026-08-25-M1-audit-P4_02_TC_ENG_06_VERSION_MISSING.md) | `grep -rn VERSION_MISSING` 仅 spec 命中；`python -c validate_versions(missing)` 返回 `[]` 已复现；`tests/unit/engine/test_version.py:58,66` 仅断言 `VERSION_MISMATCH` |
| P4-03 | 中 | P1 | 缺陷 | sync 域 `TC-SYNC-02` “README 含布局 marker 且幂等” 描述已过期。`generator.py:174-197 sync_all` 注释 “README 由收尾脚本（docs 生成）经 agent 更新，不再由 sync 触碰” 且不再调用 `render_readme_layout`；布局刷新现由 `scripts/generate-docs.sh:57-59` 直接调 `render_readme_layout`。矩阵仍把该能力归于 `sync`，与实现职责漂移 | `docs/specs/sync/spec.md:35-36` vs `src/k3dge/sync/generator.py:110-120,174-196` vs `scripts/generate-docs.sh:57-59` | 待修 | [tasks/2026-08-25-M1-audit-P4_03_TC_SYNC_02_generate_docs.md](../tasks/2026-08-25-M1-audit-P4_03_TC_SYNC_02_generate_docs.md)（P2-PUR-03 并入） | `grep -n render_readme_layout src/k3dge/sync/generator.py` 仅 `render_readme_layout` 定义与 `scripts/generate-docs.sh` 调用处命中，`sync_all` 已无调用 |
| P4-04 | 中 | P1 | 缺陷 | Contract hash 锚定文件名：`contract.py:260 collect_domain_interface` 以 `f"# {file_path.name}\n{iface}"` 拼装，多文件域中重命名文件（签名不变）即改哈希，违背 `docs/architecture/overview.md:69` “仅覆盖公开签名/函数体不改哈希”及 ADR 0001 契约范围。已在 Pass 3 D-04 以高优开单，本轮在一致性透镜复现 | `src/k3dge/engine/contract.py:242-266` （`collect_domain_interface` / `chunks.append(f"# {file_path.name}\n{iface}")`） vs `docs/specs/engine/spec.md:117` L1 范围 | 待修 | 并入 [D-04](../tasks/2026-08-25-M1-audit-D_04.md)，不另开单。优先级随 D-04 为 P1，不是崩闸 | `python -c` 临时仓 `mod.py → renamed.py` 已复现 `compute_hash` 变更（见审计过程执行输出） |
| P4-05 | 低 | P2 | 规范 | `architecture.md.template` 未纳入 `PAIRS`，脚手架仍写入 `docs/architecture/overview.md` 但门控 `TEMPLATE_DRIFT` 永不校验其漂移。`pairs.py:6-29` 覆盖 22 对资产，后 `diff` 统计 `assets not in PAIRS: {'architecture.md.template'}`。G-04 已将模板改为泛化占位（`_示例_ | src/<domain>`）并刻意不进 PAIRS，但 `pairs.py` 无豁免注释，新 Agent 易误“补全 PAIRS”把本仓特化 `overview.md` 当模板回写 | `src/k3dge/templates/pairs.py:6-29` vs `src/k3dge/templates/assets/architecture.md.template:21-34` vs `docs/architecture/overview.md:27-44` / `src/k3dge/templates/scaffold.py:45,124` | 有意留 | 有意留：维持不进 PAIRS（G-04）。豁免已写进 `pairs.py` 模块注释。何时重开：决定把 architecture 模板与本仓 overview 字节锁死 | `diff assets vs PAIRS` 已复现单漏项；`docs/reviews/2026-08-24-scaffold-gate-lock.md:G-04` 已记录“不进 PAIRS”结论 |
| P4-06 | 低 | P2 | 规范 | CLI 8 个公开命令 `cmd_check/sync/version/doc/audit/task/milestone + build_parser/main` 仅 5 个 TC 覆盖（`TC-CLI-01`/`02`/`03`/`04`/`05`），`cmd_doc` / `cmd_audit` / `cmd_task` 无矩阵行。`cli/spec.md:22-41` 接口块含 9 行签名，`TC-CLI-05` 已覆盖 `version/seal` 联动但 doc/audit/task 三分支仅在 `src/k3dge/cli/main.py:127-314` 存在，无对应 `L1` 用例 | `docs/specs/cli/spec.md:21-41,48-54` vs `src/k3dge/cli/main.py:127-314` | 有意留 | 有意留：doc/task 是薄路由；`audit` 去留由 [P2-PUR-06](../tasks/2026-08-25-M1-audit-P2_PUR_06_k3dge_audit_triage_cli_ADR.md) 决定，不另开矩阵债单。何时重开：三命令不再是薄路由 | `grep -n "def cmd_" src/k3dge/cli/main.py` 8 函数 vs `grep TC-CLI docs/specs/cli/spec.md` 5 行已复现缺口 |
| P4-07 | 低 | P3 | 规范 | `manifest.tests` vs `Verification Matrix` 执行语义分叉：`evaluator.py:192-199` `run_tests` 批量执行直接取 `manifest.domains[domain].tests` 目录，矩阵 ` `(tests/…)` `` 仅做 `MISSING_TEST_FILE` 存在性校验（`_check_domain:304-320`）。CLI 矩阵 3 行跨域引用 `tests/unit/engine/test_milestone.py` 等在 `tests_root=tests/unit/cli` 下被标 `foreign`，文件存在但 `selective L2`（`k3dge check --with-tests`）不执行，矩阵“覆盖”错觉 | `docs/specs/cli/spec.md:50-54` (3 行 engine 测试) vs `src/k3dge/engine/evaluator.py:192-199,304-315` vs `docs/specs/engine/spec.md:118-119` | 有意留 | 有意留：维持 ADR 0005 “L2=`manifest.tests`，矩阵只验存在”。何时重开：推翻 ADR 0005 的 L2 范围 | 临时仓复现：cli 域 `tests/unit/engine/test_fail` 即使 `assert False` 也不在 `evaluate(run_tests=True)` 违规中 |
| P4-08 | 低 | P3 | 规范 | `TEMPLATE_DRIFT` 自举判定依赖双重回退（`evaluator.py:226-236` `is_relative_to` + workspace `src/k3dge/templates/assets` 存在性），注释已说明“仅自举仓比对、k3dit 等下游跳过”（`tasks/2026-08-24-fix-template_drift_self_host_only.done.md`）。但 `scaffold.py:97` 写入的运行时状态文件 `.agent/milestone`（M0）及 `logs/` 空目录不在 `PAIRS`，符合预期却无显式“状态 vs 模板”分类注释，新人易误把 `milestone` 当模板补进 `PAIRS` | `src/k3dge/engine/evaluator.py:218-257` vs `src/k3dge/templates/scaffold.py:97,111-122` | 有意留 | 有意留：运行时状态不进 PAIRS。分类已写进 `pairs.py` 模块注释。何时重开：有人把 `.agent/milestone` 当模板补进锁 | `scaffold.py` 与 `PAIRS` 对比已复现 `.agent/milestone` 非对 |
| P4-09 | 信息 | — | 通过 | 全量通过项（作基线，非缺陷）：① 4 域 `CONTRACT_DRIFT`/`SPEC_MISSING_SECTION`/`CONTRACT_HASH_MISSING` 链路闭环，`--force-full` 与 selective 差分（`diff.get_changed_files: git status --porcelain` + `merge-base...HEAD`）行为与 `engine/spec.md:116` 一致；② `PAIRS` 21 对（除架构模板豁免）`diff -u` 字节一致、`test_template_sync:21 subtests` 全 Same；③ 矩阵 17 引用文件均存在、`_check_domain` 对 `missing` 报 `MISSING_TEST_FILE` 对 `foreign` 加缀；④ 脚手架对空目录 `scaffold(target)` 生成 `.agent/rules 00-03` 含 `02-simplification.md` 非空且 `>80` 字符、`AGENTS.md`/`pre-commit.yaml`/`_template/spec.md` 镜像一致 | `docs/specs/{engine,cli,sync,templates}/spec.md` + `src/k3dge/engine/{contract,evaluator,spec_schema}.py` + `src/k3dge/templates/{pairs,scaffold}.py` | 已验证 | 无需转 tasks；回归锚：`k3dge check --force-full --with-tests PASS` / `k3dge sync 幂等` / `pytest 70 passed` | 见本报告顶部 Baseline 及审计过程 `diff`/`pytest` 输出 |

## 多轨脚本同构明细（`src/k3dge/templates/assets` → 仓内）

| 资产 | 仓内路径 | 比对 | 说明 |
| --- | --- | --- | --- |
| `gate.sh` | `scripts/gate.sh` | `diff OK` | bash 轨：`[ -x .venv/bin/k3dge ]` 优先 + `command -v k3dge` 回退，缺省 `check` |
| `gate.py` | `scripts/gate.py` | `diff OK` | python 轨：同语义，`Scripts/k3dge.exe` 分支适配 Windows |
| `gate.ps1` | `scripts/gate.ps1` | `diff OK` | pwsh 轨：`$Root = Split-Path` / `Test-Path .venv/Scripts/k3dge.exe` |
| `init.sh` | `scripts/init.sh` | `diff OK` | `K3DGE_SOURCE` 解析 + `python3 -m venv` + `pip install -e .[dev]` vs 下游 |
| `init.ps1` | `scripts/init.ps1` | `diff OK` | pwsh 等价分支（`$Py`/`$VenvPy` 双路径） |
| `generate-docs.sh` | `scripts/generate-docs.sh` | `diff OK` | `grep -Eq "^\s*readme\s*=\s*true"` + `render_readme_layout` 回调 |
| `generate-docs.ps1` | `scripts/generate-docs.ps1` | `diff OK` | `Select-String -Pattern "^\s*$key\s*=\s*true"` 等价 |
| `k3dge-init-wrapper.sh` | `k3dge-init.sh` | `diff OK` | `exec "$(dirname $0)/scripts/init.sh"` |
| `k3dge-init-wrapper.ps1` | `k3dge-init.ps1` | `diff OK` | `& "$PSScriptRoot/scripts/init.ps1" @args` |
| `agents.md` | `AGENTS.md` | `diff OK` | Agent 唯一发现面 |
| `agent-readme.md` | `.agent/README.md` | `diff OK` | 进程配置声明面（ADR 0014） |
| `rules/00-03` | `.agent/rules/00-03` | `diff OK` (4) | 含 `02-simplification.md` >80 字符 + ADR 0012 |
| `docs.toml.template` | `.agent/docs.toml` | `diff OK` | 人读文档生成开关 |
| `spec.md.template` | `docs/specs/_template/spec.md` | `diff OK` | 含 `Level` 列头，4 节完整 |
| `tasks-readme.md` | `docs/tasks/README.md` | `diff OK` | — |
| `branches-readme.md` | `docs/branches/README.md` | `diff OK` | G-03 补 |
| `memo-readme.md` | `docs/memo/README.md` | `diff OK` | G-03 补 |
| `reviews-readme.md` | `docs/reviews/README.md` | `diff OK` | G-03 补 |
| `pre-commit.yaml.template` | `.pre-commit-config.yaml` | `diff OK` | `language: python entry: scripts/gate.py always_run: true` 无 `additional_dependencies: ["."]` |
| `architecture.md.template` | — (豁免) | 不比 | 下游泛化占位 ` _示例_ | src/<domain>` ，不与本仓四域特化 `overview.md` 比对（G-04） |

`scaffold` 可执行位与仓内一致：`gate.sh/gate.py/init.sh/generate-docs.sh/k3dge-init.sh` 为 `755`，`*.ps1` 与包装器 `ps1` 为 `644`（`scaffold.py:103-127 executable=True` 仅对 sh/py 轨）。

## Verification Matrix — 文件存在性全量

- `engine:6` → `tests/unit/engine/test_evaluator.py` ✓ / `test_schema.py` ✓ / `test_contract.py`×2 ✓ / `test_milestone.py` ✓ / `test_version.py` ✓
- `cli:5` → `tests/unit/cli/test_main.py` ✓ / `tests/unit/engine/test_milestone.py` (foreign) ✓ / `tests/unit/engine/test_evaluator.py` (foreign) ✓ / `tests/unit/cli/test_mcp.py` ✓ / `tests/unit/engine/test_version.py` (foreign) ✓
- `sync:2` → `tests/unit/sync/test_generator.py`×2 ✓
- `templates:4` → `tests/unit/templates/test_scaffold.py`×3 ✓ / `test_template_sync.py` ✓
- `manifest.tests` 目录 4 项均存在且与 `PAIRS` 解耦（`tests/unit/contracts/test_manifest_sync.py:25-31` 另有全量 `spec dir`/`src`/`tests` 存在性闸）

`evaluator._check_domain` 对 `tests/unit/cli/test_main.py` 等真实 `MISSING_TEST_FILE` 报域内违规，对 `tests/unit/engine/*` 在 `cli` 矩阵中追加 ` (cross-domain reference)` 且不纳入 `_run_batch_tests` 的执行集（`evaluator.py:194-198 batch_refs` 直接取 `manifest.tests`），故 “矩阵覆盖” ≠ “执行覆盖”，已在 `engine/spec.md:118` 声明。

## 不重开（本轮已核对仍有意留）

A-11 / S-13 / F-14/F-15 / R3-1 / R3-4 及 08-25 Pass 3 除 D-04/D-05 外的有意留（D-01/D-02/D-03/D-06/D-07/D-08/D-09/D-10/D-11/D-12）均不在 Pass 4 透镜内重开（见 `docs/architecture/overview.md` §5.1 与 `docs/reviews/SUMMARY.md`）。

## 处置汇总

- **转 tasks**：P4-01 / P4-02 / P4-03（3 项，各有独立 M1 文件）
- **并入**：P4-04 → D-04（同一哈希锚，不另开单；P0 降为 P1）
- **有意留**：P4-05 / P4-06 / P4-07 / P4-08（4 项；P4-05/P4-08 豁免已写入 `pairs.py` 注释）
- **已验证通过**：P4-09（1 项，作回归基线）

> P4-01..P4-03 只改 spec 矩阵/表头，哈希不变。D-04（含 P4-04）若定案去文件名头须 `k3dge sync` 重算四域 hash。
