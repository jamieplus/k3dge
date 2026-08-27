---
id: INC-20260827-CON-M6-5pass-full
type: CON
severity: P2
target_milestone: M6
discovery_date: 2026-08-27
status: closed
root_cause_harness: k3dge
action_task_ref: docs/tasks/2026-08-27-M6-fix-fix_template_sync_missing_protocols_asset.done.md
---

# INCIDENT REPORT: [M6] 5-Pass 全量 9 缺陷（M3 回归 4 项）B-T-D 复现

## 1. 现象与证伪证据 (B-T-D Evidence)

- **预期行为 (Baseline)**: `M6` 的 `5-Pass` 审计 9 项待修（`P1-01..P4-01` + `P4-02` 候选）应在 `k3dge-audit` 快照 `0.1.7/M6` 全绿前被 ` WARN` 可观测或 `P2/P3` 建Task；`k3dge check --force-full` 仅验 `CONTRACT_DRIFT`，`CHANGELOG` 静默、`mcp sync` 假失败、`mcp.json` 损坏静默、`cli→templates` 私有导入、`overview §5.1` 悬空、`seal` 双轨、`ManifestError` 穿透、`矩阵缺口`、`跨文件原子` 应被拦截或回退为 `有意留`。
- **现存破损 (Treatment 前)**: `P1-01` `_append_to_unreleased` `except:pass` 静默（`chmod a-w` 后 `mark_task_done` 仍 `ok`）；`P1-02` `new_text` 三重覆盖死代码；`P1-03` `py3.10` 无 `tomli` 时 `mcp sync` `return 1` 假失败；`P1-04` 损坏 `.mcp.json` 静默 `return`；`P2-01` `cli→templates` 私有 `._ensure_mcp_config`；`P2-02` `overview`/`SUMMARY` 互指 `§5.1`；`P3-01` `cli` 用 `Unreleased` 正文、`mcp` 用 `archive` 列表双轨；`P3-02` `ManifestError` 抛栈；`P4-01` `TC-ENG-08/09/10` 缺口；`P4-02` 跨文件 `kill -9` 半漂移。
- **复现路径**:
  ```bash
  # P1-01
  python -c "from pathlib import Path; from k3dge.engine.milestone import _append_to_unreleased; ..."
  # => r=None, o='' (静默) → 修复后 r=False, o='[WARN]...'
  # P1-03
  grep -r tomli pyproject.toml # => 0
  python -c "import tomli" # => ModuleNotFoundError → 修复前 mcp sync return 1
  # P1-04
  echo '[' > .mcp.json; python -c "from k3dge.templates.scaffold import _ensure_mcp_config; print(_ensure_mcp_config(Path('.')))" # => None
  # P2-01
  grep -rn "_ensure_mcp_config" src/k3dge/cli # => 1
  # P4-01
  grep -rn "guide-stub|Unreleased|pipeline" docs/specs # => 0
  ```

## 2. 根因剖析 (5 Whys)

1. 为什么 `P1-01` 静默？ → `milestone.py:82` `except:pass` 双重静默，未 `WARN` 或 `bool`
2. 为什么 `P1-03` 假失败？ → `pyproject.toml:19` `mcp` extra 无 `tomli>=2; python<3.11`，`cli/main.py:253` 未分层 `None` 跳过
3. 为什么 `P1-04` 静默？ → `scaffold.py:111` 损坏 `return` 无 `WARN`，`cli/main.py:245` 私有导入且 `mcp sync` 仍 `0`
4. 为什么 `P2-02` 悬空？ → `overview §5.1` 已迁 `SUMMARY.md`，`overview.md:118`/`SUMMARY.md:5` 未同步
5. 为什么 `P3-01` 双轨？ → `cli/main.py:340` 与 `mcp.py:318` 分头算 `notes`，未抽 `consume_unreleased`

## 3. 防退化动作清单

- [x] **物理测试加固**: `milestone.py:82` `->bool` + `WARN`，`341` 转告；`scaffold.py:111` `->bool` + `WARN`；`cli/main.py:245` 公有 `ensure_mcp_config`
- [x] **契约补强**: `engine/spec.md:136` + `TC-ENG-08/09/10`，`cli/spec.md:56` + `TC-CLI-08`，`pairs.py:47` + `protocols/audit_default.md`
- [x] **规则透镜升级**: `.agent/rules/07-audit.md:7` 已指 `docs/incidents/INC-...`，`AGENTS.md:46` / `branches/README.md:5` 同步，`incident/README.md` 正交分工
- [x] **关联修复 Tasks**: `2026-08-27-M6-fix-*.done.md` 5 项（`M6`）+ `M6-5pass` 9 项 `done`，`align M6 PASS`，`Gate SUCCESS`，`pytest 87 passed / 65 subtests`
- [x] **外部 Harness 高亮**: `cli/main.py:247` `_harness_fallback_warn` + `mcp.py:358` `_audit_protocol_with_fallback` 高亮 `WARN[HARNESS FALLBACK]`，`k3dge mcp sync` 已 `auto-added peer k3dit/k3che/k3lity`

## 4. 经验灌入

- `except:pass` 在 `CHANGELOG`/`mcp.json` 侧必 `WARN` 或 `bool`，`rg "except.*: pass"` 0 容忍
- `optional-dependencies` 必覆 `3.10`，`tomli` 缺失不假失败
- 跨域私有即 drift，`_private` 不进 `spec`，晋升需 `k3dge sync`
- `overview §8` 仅索引，`SUMMARY.md` 单一事实源，不再 `§5`
- 双轨 `seal` 必抽 `consume_unreleased`，`rg consume_unreleased` 双命中

## 5. 双向回链

- **Audit**: `docs/reviews/2026-08-27-5pass-full.md: P1-01..P4-02`
- **Branch**: `docs/branches/2026-08-27-M6-5pass-repro.md:1`（镜像，`incidents` 为主）
- **Tasks**: `docs/tasks/2026-08-27-M6-fix-*.done.md` 9 项（`M6`）
- **Review 回填**: `docs/reviews/2026-08-27-5pass-full.md: 回填` 已 `已修/有意留`
- **Harness**: `k3che` `BranchThrottler` / `k3lity` `B-T-D` / `k3dit` `5-Pass`
