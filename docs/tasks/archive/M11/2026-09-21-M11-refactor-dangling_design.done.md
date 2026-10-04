---
status: done
milestone: M11
priority: P3
date: 2026-09-21
---

# 悬空设计盘点：删 3 个零调用 API + `facts_of` 接入生产自检

- **可检索摘要**: 按"声明面 vs 事实"同一判据对**设计层**横展：真悬空 3 处（`seal.auto_satisfied_ids` 兼容别名、`seal.auto_pending_seal_gates`、`scaffold._ensure_mcp_config` Deprecated alias，生产零调用）；一处"只为测试而活"的 API（`gate_facts.facts_of`）接线成生产自检。另证明若干面是干净的（见下），并把 3 条"看起来像死代码、其实有意留"的登记入账。

## 证据（可复跑）

```
扫法：AST 取模块级 def/class → 计数"同文件（除 def 行）/ 跨模块 / 测试 / 文档与配置面"四处的引用
真悬空（生产 0 调用）：
  seal.auto_pending_seal_gates   ← 清单 ⚙️ 语义已由 seal_checklist 的 auto 字段承担
  seal.auto_satisfied_ids        ← 自称"兼容别名 → nodes.satisfied_ids"，仅 docstring 提及
  templates/scaffold._ensure_mcp_config ← 自称 "Deprecated alias"，公共 ensure_mcp_config 才有人用
只为测试而活：
  gate_facts.facts_of            ← 声明里的占位键；测试喂自造 facts 自证，生产侧没人核对
干净（防重开）：
  违规码：gate_facts 54 + 五份 .schema.json 的 codes 全部有产出点
  配置旋钮：gates.DEFAULTS 每个键都被读过
  编排声明：[checks.*] 的 action/precondition id 全部有实现（未知 id 直接拒）
  peer action：pipeline.toml 的 submit/collect/present/status 全有调用方（角色名 + f-string 形式）
  CLI：20 子命令唯一"文档面几乎不提"的 commit-attest，到达面是 hook（scripts/commit-msg）
```

## 方案

1. 删：`seal.auto_pending_seal_gates` / `seal.auto_satisfied_ids` / `scaffold._ensure_mcp_config`（`rules/02`：零调用；兼容别名无调用＝无兼容价值）。
2. 接线：`facts_of` 有生产消费者——`doc_gate.missing_declared_facts()` 在渲染每个码前核对"声明要的占位键是否都给了"，闸尾统一 `[k3dge facts] WARN`（**不阻断**：那是工具自检，不是仓内偏差）。
3. 登记：`FACTS-01`（`fix_kind` 只服务交叉核对守卫，别删）、`EVENT-01`（`read_events` 对外面仓内零读者）、`AUDIT-01`（oneshot 路径配置相关当前不可达）。

## 边界与拆分

- 事实归属：闸的声明面归 `gate_facts`；自检归 `doc_gate`（渲染点）；清理归各归属模块。
- 不动的：`fix_kind`（守卫支撑）、`read_events`（对外面）、oneshot 路径（配置面合法取值）。
- 更正记录：盘点第一遍把 `fix_kind` 说成"连测试都不用"是错的（tests 5 处）——保留并在 LEFTOVERS 登记。

## 结案

- 落地：`engine/seal.py`（删 2 个 API + prose 改指 `nodes.satisfied_ids`）、`templates/scaffold.py`（删 Deprecated alias）、`engine/doc_gate.py`（`missing_declared_facts()` + `_MISSING_FACTS` 累积 + 闸尾 WARN）。
- 测试：`tests/unit/scripts/test_precommit.py` 加 `TestDeclaredFactsSelfCheck`（3 例：缺事实/给全/未声明码）；`test_milestone.py` 的对齐断言改走 `nodes.satisfied_ids`。
- 实测：真跑 hook（stage 一处 docs 改动）→ doc-gate/schema PASS 且**未出现** `[k3dge facts] WARN` ⇒ 当前声明面与产出点一致（接线是为防未来漂移）。
- 验证：`k3dge check --with-tests` 绿（四域）；`pytest -q` 全绿。
