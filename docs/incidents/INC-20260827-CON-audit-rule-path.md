---
id: INC-20260827-CON-audit-rule-path
type: CON
severity: P2
target_milestone: M6
discovery_date: 2026-08-27
status: closed
root_cause_harness: k3dge
action_task_ref: docs/tasks/2026-08-27-M6-fix-fix_audit_rule_deprecated_protocol_path.done.md
---

# INCIDENT REPORT: [k8d3e-a78-02] 审计规则废弃协议路径悬空

## 1. 现象与证伪证据 (B-T-D Evidence)

- **预期行为**: `Rule 07` 透镜不在 `k3dge` 包内，优先 `../k3dit/docs/guides/protocol.md`，否则 `docs/protocols/audit_default.md`（`docs/guides/` 人读，不含机器 SOP，Diátaxis ADR 0002）。
- **现存破损**: `.agent/rules/07-audit.md:3` 写 `优先 docs/guides/protocol.md 或 ../k3dit/...`，`ls docs/guides/protocol.md` → 不存在（已迁 `docs/protocols/audit_default.md`），`grep -r "guides/protocol" .agent/rules` 命中 1 悬空。
- **复现路径**:
  ```bash
  cat .agent/rules/07-audit.md | head -3
  # => 优先 `docs/guides/protocol.md` 或 `../k3dit/docs/guides/protocol.md`，否则 `docs/protocols/audit_default.md`
  ls docs/guides/protocol.md # => No such file
  grep -r "guides/protocol" .agent/rules # => 07-audit.md:3
  ```

## 2. 根因剖析 (5 Whys)

1. 为什么悬空？ → `docs/guides/protocol.md` 已按 Diátaxis 迁 `docs/protocols/audit_default.md`，`07-audit.md` 未跟随
2. 为什么双写也错？ → `assets/rules/07-audit.md:3` 同步含旧路径，`PAIRS` 未拦
3. 为什么未拦截？ → `test_template_sync` 仅验 `PAIRS` 字节一致，不验路径语义

## 3. 防退化动作清单

- [x] ` .agent/rules/07-audit.md:3` → `优先 ../k3dit/docs/guides/protocol.md，否则 docs/protocols/audit_default.md`（`docs/guides/` 人读）
- [x] `assets/rules/07-audit.md:3` 同步（`PAIRS` `rules/07-audit.md`）
- [x] `grep -r "guides/protocol" .agent/rules` → 0
- [x] `docs/memo/archive/2026-08-24-audit-harness-independence.md` 已注 `k3dit` 指针

## 4. 经验灌入

- `docs/guides/` 人读指南，不含机器 SOP，`grep -r "guides/protocol" .agent` 必须 0

## 5. 双向回链

- **Audit**: `docs/reviews/2026-08-27-k8d3e-a78-5pass.md: 02`
- **Branch**: `docs/branches/2026-08-27-k8d3e-a78-repro.md: 02`
- **Task**: `docs/tasks/2026-08-27-M6-fix-fix_audit_rule_deprecated_protocol_path.done.md`
