---
status: done
milestone: M11
priority: P2
date: 2026-09-21
---

# 架构文档 seal 覆盖（overview + encyclopedia）+ 域表对账闸 `ARCH_TABLE_DRIFT`

- **可检索摘要**: 上一条只把 `docs/architecture/overview.md` 纳入 seal 的**事实行**——`encyclopedia.md` 完全没进面；且两份文档的域表与 manifest 之间**没有任何闸**，而 `overview.md` 头部自称"人写常驻 + `k3dge sync` 聚合校验"——那道校验此前并不存在（`grep architecture evaluator|pure_refs` 零命中）。

## 证据

```
grep -rn "architecture" src/k3dge/engine/{evaluator,pure_refs,doc_catalog}.py
  ⇒ 只有一句注释（pure_refs:352），无任何一致性判据
docs/architecture/overview.md 头部：> 人写常驻 + `k3dge sync` 聚合校验。   ← 声称有、实际无（ADR-0012 证据链缺"到达"环）
两条域表：overview §1（Domain/Source/Spec/Description）、encyclopedia §2（+ 测试/depends_on）；manifest 改域/路径可静默漂移
```

## 方案

1. 新码 **`ARCH_TABLE_DRIFT`**（`evaluator._check_architecture_tables`）：抽两张域表（表头含 `Domain` 且含事实列即认），比 `域集` 与 `src`/`spec`（overview）、`tests`/`depends_on`（encyclopedia）；**不比 description/一句话**（散文）；缺文件、非域表格式不报（归文档评审）。`depends_on` 逗号列表顺序不敏感。
2. seal 的事实行扩成**逐件报**：`overview.md` / `encyclopedia.md` 各自"区间内动过/未动"；两件都没动时明说"都没动"。
3. 把 `overview.md` 头部那句自称改成事实（对账闸在 `k3dge check`，不是 sync）。
4. `AGENTS.md` §12 口径扩到两件文件并写明域表另有闸（模板资产镜像）。

## 边界与拆分

- **不把解释文档变成生成物**：Diátaxis 里 `architecture`＝解释（人写），`generated`＝Reference；只把表里的**事实列**纳入机检，散文仍归人/k3dit。
- 事实归属：表行对账＝manifest 的投影 ⇒ 判据在 `evaluator`；reconcile/生成不动（不新造 `overview` 的 markers 块）。
- 不阻断的部分：设计文档**新鲜度**仍只出事实（seal 输出 + 收摊清单）；域表**事实列**不一致才红（`ARCH_TABLE_DRIFT`）。

## 结案

- 落地：`engine/evaluator.py`（`_check_architecture_tables` + `_domain_table_rows` / `_norm_cell`）、`engine/gate_facts.py`（`ARCH_TABLE_DRIFT`，fix=judgment：文档过时 vs manifest 才是源）、`engine/seal_flow.py`（事实行逐件报两件设计文档）、`docs/architecture/overview.md`（头部自称改事实）、`AGENTS.md` + 资产镜像、引擎 spec TC-ENG-25。
- 测试：`tests/unit/engine/test_architecture_tables.py`（7 例：匹配过、缺域行、src 错、depends_on 顺序不敏感、depends_on 缺项、缺文件不报、非域表忽略）；`test_architecture_freshness.py` 随文案更新（仍 5 例）。
- 实测：本仓两张表当前与 manifest 一致 ⇒ 闸绿（无存量漂移）；负向由单测覆盖（改一个 `src` 单元即红）。
- 验证：`k3dge check --with-tests` 绿（cli/engine/sync/templates）；`pytest -q` 707 passed, 2 skipped。
- 有意留：`overview.md`/`encyclopedia.md` 的**散文**不设闸（归人/k3dit）；表结构若大改，闸安静跳过（不误报）。
