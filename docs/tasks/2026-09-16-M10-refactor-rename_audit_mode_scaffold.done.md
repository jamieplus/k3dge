---
status: done
milestone: M10
priority: P1
date: 2026-09-16
---

# 术语撞名：审计腿 mode "scaffold" → "oneshot"

- **可检索摘要**: `scaffold` 一词在 k3dge 内有两个不相干含义——(A) `templates/scaffold.py::scaffold()` 是 `k3dge init` 的脚手架生成工具；(B) `[roles.audit] mode` 的缺省值指审计腿的旧一次性形状。违反 `docs/adr/AUTHORING.md:36`「同一概念只用一个词」。把 (B) 改名为 `oneshot`（沿用 pipeline.toml 原注释「旧一次性形」）。

## 意图

消除一词两义。本会话已实际发生误读：讨论审计腿时反复说「scaffold 死路径」，字面可读成「脚手架生成工具是死路径」，用户据此提问才暴露撞名。

## 证据链

### E11a — 撞名两侧（产物）

```
含义 A（脚手架工具）
  src/k3dge/templates/scaffold.py:255   def scaffold(target: Path, name: str | None = None) -> None
  src/k3dge/cli/main.py:494             scaffold(target, name=args.name)     ← k3dge init 调用

含义 B（审计腿形状）
  src/k3dge/engine/milestone_audit.py:101  缺省 scaffold（旧形）
  src/k3dge/engine/milestone_audit.py:109  .get("mode", "scaffold")
  src/k3dge/engine/milestone_audit.py:111  return "scaffold"
```

### E11b — 违规判据（消费者）

`docs/adr/AUTHORING.md:36`：「同一概念只用一个词；改词不改义，语义变更走 ADR。」
撞名是其逆向违规（一词两义），且已造成实际误读。

### E11c — 向后兼容性证明

`_audit_mode()` 生产侧唯一消费点：
```
src/k3dge/engine/milestone_audit.py:185   ratchet = _audit_mode(workspace) == "ratchet"
```
只与 `"ratchet"` 比较 ⇒ 非 ratchet 的任何取值走同一路径。
`pipeline_schema.py` 无 `mode` 取值校验（grep 无命中）。

**结论**：下游仓已写 `mode = "scaffold"` 的配置，改名后行为一字不变（仍为「非 ratchet」）。

## 改动

| 位置 | 改动 |
|---|---|
| `engine/milestone_audit.py` | 缺省值 `"scaffold"` → `"oneshot"`（2 处）+ docstring |
| `.agent/pipeline.toml:23` | 注释「缺省 "scaffold"」→「缺省 "oneshot"」 |
| `templates/assets/pipeline.toml.template:23` | 同上（PAIRS 配对，须同步） |
| `tests/test_seal_flow.py` | `_SCAFFOLD`→`_ONESHOT`、`_ws_scaffold()`→`_ws_oneshot()`、2 处断言、测试名 |

不改：`templates/scaffold.py`（含义 A，名字正确）、历史 task/review 文档（当时记录属实）。

## 边界与拆分（feat 类必填；规则 08）

- 事实归属：审计腿形状归 `milestone_audit._audit_mode`；脚手架生成归 `templates/scaffold.py`
- 边界检查：改名不得改行为——`== "ratchet"` 判据不动，故非 ratchet 分支行为恒等
- 桩子先行：改缺省值 → 跑 test_seal_flow（含新加的 `test_default_mode_is_*` 守卫）→ 同步模板 → 跑 template_sync

## Notes

- 改动量：~10 处字面量替换，零行为变化
- 选 `oneshot` 而非 `legacy`：命名行为（一次性跑完并在 loop 内等待）而非命名状态，与 pipeline.toml 原注释「旧一次性形」一致
