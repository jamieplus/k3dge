---
id: INC-20260827-AST-template-sync-protocols
type: AST
severity: P2
target_milestone: M6
discovery_date: 2026-08-27
status: closed
root_cause_harness: k3dge
action_task_ref: docs/tasks/2026-08-27-M6-fix-fix_template_sync_missing_protocols_asset.done.md
---

# INCIDENT REPORT: [k8d3e-a78-05] 模板同步缺 protocols 资产

## 1. 现象与证伪证据 (B-T-D Evidence)

- **预期行为**: `docs/protocols/audit_default.md` 新增时，`assets/protocols/audit_default.md`、`PAIRS`、`scaffold`、`expected` 四件套应同步，否则下游 `k3dge-init.sh` 漏释放 `docs/protocols/audit_default.md`，`TEMPLATE_DRIFT` 未拦。
- **现存破损**: `grep -n "protocols" src/k3dge/engine/pairs.py` → 0；`ls src/k3dge/templates/assets/protocols/` → `No such file`；`grep -n "protocols" tests/unit/templates/test_template_sync.py` → 0（`expected` 22 项）；`pytest test_template_sync -q` 22 项。
- **复现路径**:
  ```bash
  grep -n "protocols" src/k3dge/engine/pairs.py # => 0
  ls src/k3dge/templates/assets/protocols/ # => No such file
  grep -n "audit_default" tests/unit/templates/test_template_sync.py # => 0
  pytest tests/unit/templates/test_template_sync.py -v # => 22 expected
  ```

## 2. 根因剖析 (5 Whys)

1. 为什么 `PAIRS` 缺？ → `docs/protocols/audit_default.md` 按 Diátaxis 新增于 `M6`，`engine/pairs.py` 未追
2. 为什么 `assets` 缺？ → `src/k3dge/templates/assets/protocols/` 未 `mkdir && cp`
3. 为什么 `scaffold` 缺？ → `scaffold.py:60` 无 `PROTOCOL_TEMPLATE`，`scaffold:225` 未 `mkdir protocols`
4. 为什么 `expected` 缺？ → `test_template_sync.py:21` 22 项未含 `protocols/audit_default.md`

## 3. 防退化动作清单

- [x] `mkdir -p assets/protocols && cp docs/protocols/audit_default.md assets/protocols/audit_default.md`（`diff -r` ok）
- [x] `pairs.py:47` + `("protocols/audit_default.md","docs/protocols/audit_default.md")`（`TEMPLATE_DRIFT`）
- [x] `scaffold.py:60` `PROTOCOL_TEMPLATE = _asset("protocols/audit_default.md")` + `scaffold:225` `mkdir protocols && _write_if_missing audit_default.md`
- [x] `test_template_sync.py:46` + `protocols/audit_default.md` → `expected` 23 项，`pytest` 65 subtests `PASS`

## 4. 经验灌入

- 新增机器 SOP 必四件套：`assets` + `PAIRS` + `scaffold` + `expected`，否则 `TEMPLATE_DRIFT`/`test_template_sync` 红，`grep -r "protocols" src/k3dge/engine/pairs.py` 必 1

## 5. 双向回链

- **Audit**: `docs/reviews/archive/untagged/2026-08-27-k8d3e-a78-5pass.md: 05`
- **Branch**: `docs/branches/2026-08-27-k8d3e-a78-repro.md: 05`
- **Task**: `docs/tasks/2026-08-27-M6-fix-fix_template_sync_missing_protocols_asset.done.md`
- **Review 回填**: `docs/reviews/archive/untagged/2026-08-27-k8d3e-a78-5pass.md: 回填 05 已修`
- **PAIRS**: `src/k3dge/engine/pairs.py:47`
