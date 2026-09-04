---
status: done
milestone: M7
priority: P2
date: 2026-09-04
---

# ratchet v3 施工十单封账凭条

- **Status**: done
- **Milestone**: M7
- **Priority**: P2
- **可检索摘要**: ratchet v3 施工账（①②③④⑤⑥⑦⑧⑨⑩）全绿——bundle 单文件交换原子、分支写回（merge_back P1）、角色门/署名结案（k3dit 侧 ①⑧⑨）、seal 清理钩子、audit 四动词 CLI、契约 v0.6 与 memo 化石条目
- **Date**: 2026-09-04

## 已确认意图

- 交换与写回全部走 ADR-0026 定稿形状：身份（`cas://` tree oid）与位置（file|url）分家；bundle 即宇宙；工作现场 = `k3dit/<job>` 分支 + worktree；closure merge 回主干。
- 主权表落码：k3dit 只存句柄字符串与判断物，`rounds.py` 零 `open()`（grep 为证）；判与物分离到席位（P3 机器化：`fixed` 仅审计席可签）。
- 结案两步化：清零 ⇒ `pending_report` ⇒ 审计席**署名**报告才 `done`；collect 未署名只回 `PENDING`。

## 边界与拆分

- 不在本账：远程 transport、k3che CAS、`context/` 契约召回（§3"待接"行保留原样）。
- 拆层照旧：store/worktree/bundle = 机械件；audit_flow = 编排；cli = 薄出口；判断全在席位与 k3dit 账本。

## 验收

- `logs/ratchet_demo.py` 活体整圈：submit→claim 句柄→落标 advance→审计签账→修→`fixed`→`audit-report`→`sign-report`→collect（`merge: ff`，主干带回修复 True）→prune（bundles 剩 0、store 保留）。
- k3dge 241 / k3dit 46 / k3che 40 测试绿；两仓 `check` ✅；冲突/脏树/自愈三回归测。
