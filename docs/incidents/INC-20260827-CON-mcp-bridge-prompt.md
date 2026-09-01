---
id: INC-20260827-CON-mcp-bridge-prompt
type: CON
severity: P3
target_milestone: M6
discovery_date: 2026-08-27
status: closed
root_cause_harness: k3dge
action_task_ref: docs/tasks/2026-08-27-M6-fix-fix_mcp_bridge_deprecated_protocol_pointer.done.md
---

# INCIDENT REPORT: [k8d3e-a78-04] MCP Bridge 残留废弃协议指针

## 1. 现象与证伪证据 (B-T-D Evidence)

- **预期行为**: `docs/guides/mcp-bridge.md:69` `Prompt | k3dge_5pass_audit_prompt` 应 `优先 ../k3dit/docs/guides/protocol.md，否则 docs/protocols/audit_default.md`（与 `mcp.py:362` `../k3dit` 一致，Diátaxis）。
- **现存破损**: `grep -n "k3dit" docs/guides/mcp-bridge.md` → `k3dit/docs/guides/protocol.md` 缺 `../`，与 `src/k3dge/cli/mcp.py:362` `../k3dit/docs/guides/protocol.md` 不一致，`k3dit` harness 未在 `.mcp.json` 时回退路径不精确。
- **复现路径**:
  ```bash
  grep -n "k3dit" docs/guides/mcp-bridge.md
  # => | Prompt | ... | 优先 `k3dit/docs/guides/protocol.md`，不存在时 `docs/protocols/audit_default.md` |
  grep -n "k3dit" src/k3dge/cli/mcp.py
  # => Priority: docs/guides/protocol.md → ../k3dit/... → audit_default.md
  ```

## 2. 根因剖析 (5 Whys)

1. 为什么缺 `../`？ → `mcp-bridge.md:69` 手写 `k3dit/docs/...` 未与 `mcp.py:362` `../k3dit/...` 统一
2. 为什么未拦截？ → `mcp-bridge.md` 非 `PAIRS` 强锁（`downstream.md` 为配对，`mcp-bridge` 为人读），`k3dge check` 不验跨文档 `k3dit` 前缀一致性

## 3. 防退化动作清单

- [x] `docs/guides/mcp-bridge.md:69` → `../k3dit/docs/guides/protocol.md，否则 docs/protocols/audit_default.md`（与 `mcp.py:362` 一致）
- [x] `assets/mcp-bridge.md.template:69` → 同步 `优先 ../k3dit/...，否则 docs/protocols/audit_default.md`
- [x] `grep -r "k3dit/docs/guides" docs --include="*.md"` 全含 `../`
- [x] `src/k3dge/cli/mcp.py:362` 已 `Priority: ../k3dit → audit_default.md`（`docs/guides/protocol.md` 已删）

## 4. 经验灌入

- 外部 Harness 路径统一 `../k3dit`，`grep -r "k3dit/docs/guides" docs` 全含 `../`，`docs/guides/` 人读不含机器 SOP

## 5. 双向回链

- **Audit**: `docs/reviews/archive/untagged/2026-08-27-k8d3e-a78-5pass.md: 04`
- **Branch**: `docs/branches/2026-08-27-k8d3e-a78-repro.md: 04`
- **Task**: `docs/tasks/2026-08-27-M6-fix-fix_mcp_bridge_deprecated_protocol_pointer.done.md`
