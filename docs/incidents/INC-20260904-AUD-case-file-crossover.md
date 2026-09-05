# INCIDENT REPORT: [M7] 双腿首夜案卷互踩（quality 签署件覆盖审计签署件）

## 1. 现象与证伪证据 (B-T-D Evidence)

- **ID**: INC-20260904-AUD-01 | **Date**: 2026-09-04（首案当夜） | **Type**: AUD（案卷完整性） | **严重度**: 高
- 判定当时仍正确（两报告 `待修=0` 各为真），但案卷内容错位——seal 只数计数的话永远不会发现。

## 2. 根因剖析 (5 Whys)

ratchet 双腿并行后，同一里程碑先后有 audit 与 quality 两份签署报告；`collect_audit` 落盘命名硬编码 `-audit.md`，不随工单 role 走。

## 3. 防退化动作清单

- 触发：quality 工单 collect 把签署件写进 `2026-09-04-M7-audit.md` 覆盖审计签署件；席按工单跑 `k3lity quality-report --workspace <consumer>` 把 94 条机器草稿直写案卷区 `…-quality.md`——一覆一占。
- 损害：审计签署件盘上缺失；若只看计数闸，错位不可见。

## 4. 经验灌入

- 防退化（同夜全部落地）：① 命名按 role（`-audit.md`/`-quality.md`）；② 案卷防互踩闸：目标已存在且 kind 不符 ⇒ FORMAT 拒落、原件不动（跨单覆盖仍合法=重提交设计）；③ 两份签署件自机构账本（权威源）逐字节复原，state 指针纠正；④ k3lity `quality-report --out`，席工单改令草稿落 /tmp。
- 回归：`test_collect_role_naming_and_kind_guard`（254 绿）。
- 教训：数据最小化让**机构账本成为唯一权威副本**，恰在被踩夜证明价值——git＋两家账本三路可恢复；闸门排序（验壳→类守卫→落盘）保持。

## 5. 双向回链

- 报告：`docs/reviews/2026-09-04-M7-audit.md`、`docs/reviews/2026-09-04-M7-quality.md`（复原后的两份签署件）
- 工单：k3dit `ae911e744eff`、k3lity `0300799a8a4a`；测试：`test_collect_role_naming_and_kind_guard`
