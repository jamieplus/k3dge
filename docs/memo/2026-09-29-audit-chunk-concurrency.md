# Memo: 判读腿分片串行 ⇒ 整仓一轮撞墙钟——并发/收窄选项账

- **类型**: 暂无法落地（要动 k3dit 物化/相位循环，属独立批次；先记选项与硬约束，避免下次重走）
- **念头**: 审计判读腿（doc/code/value）每窗把整仓切 ~59 片、逐片**串行**（~2.5 min/片），整仓一轮 > 2h；记下「怎么才能不这么慢」的选项与结构性约束。
- **触发场景**: 2026-09-29 M11 封板二跑，`k3dit audit` 整仓（`scope=.`），doc 窗 59 片 ≈ 2h 即到 k3ge 侧 7200s 墙钟被掐 ⇒ `hall export` 抢救出 `incomplete` 包、封板被拒。
- **Date**: 2026-09-29

## 事实（可复跑）

- **每窗对整棵树切片**：`hall/<window>/facts/chunk_digest.md` 头为 `… window=code chunk=27/59 … 跟踪总数=584`；doc 窗同样 `…/59`。即三窗各自把整仓（584）审一遍。
- **串行**：`hall/seats/seat-<win>-<job>.log` 严格一片接一片（一条 `{"ok":…}` 收尾后才起下一片 `turn 1`）；同一时刻只有一对 `seatwrap`+`seat_http`；hall 事件 `spawn→collect→merge` 逐片推进。
- **三条硬约束**：
  1. 同窗只有一个站址——`hall_wall.materialize` 每片 `_clear_contents` 重写该目录；
  2. 钉**就地**写进窗树（`pins = "inplace"`）⇒ 并行片会互相踩写同一棵树；
  3. `scope="."` 未按窗切——`hall_wall.window_scope` 对 `"."`/空 返回整树（`_WINDOW_TREE` 的 `src`/`docs` 交集落空），所以 doc/code/value **各审一遍整仓**（3×）。

## 选项（按性价比）

1. **修 scope（~3×，且不算并发）**：让 `window_scope` 先把 `.`/空 归一为"整树"，再按 `_WINDOW_TREE` 切（doc→`docs`、code/value→`src`）。纯逻辑一处、不动并发模型 ⇒ 片数与总量同时降，立竿见影。
2. **跨窗并行 doc‖code‖value（~3×）**：站址独立（`hall/doc`、`hall/code`、`hall/value`）、findings 独立、互不写同一棵树 ⇒ 架构可行；要改 Hall 相位循环（现为跑完一窗再下一窗）。中等改动。
3. **窗内并行（真并发）**：**当前形状不可**（约束 ①②）。要 per-chunk 站址 + 钉的独立归并/去重，等于重做判读腿的物化与收成。大改 + ADR。
4. **旁路手工分片**（多 worktree 跑互斥 scope 的独立审计再合并）：k3dit 无**合并 findings** 能力，等于绕过封板链，不建议。
5. **减片不并发**：`K3DIT_WINDOW_LIMIT` 调大（每片份数多）⇒ 片数少但单片更慢、更易撞预算/超时，收益有限。

## 关联（指针）

- 墙钟 ≠ 探针：`docs/reviews/LEFTOVERS.md`（M11 2026-09-29 条）、`src/k3dge/engine/audit_bundle.py:94-117`（`_run` 平铺超时 `killpg`）、`src/k3dge/engine/milestone_audit.py:434-445`（`k3dit_timeout`）。
- 物化/窗切：k3dit `hall_wall.window_scope` / `materialize`；分片大小 `WINDOW_TARGET_LIMIT`（`hall_wall.py`）。
- 拓扑/入口：ADR-0025（hall 拓扑）、ADR-0008（路径入口）。

## 下一步

- 先做 1（k3dit 一处逻辑 + 回归）；2 立 ADR 另做；**不要动 3**。
- 本账只为"下次别再重走"留存判据；转 tasks 由后续排期决定。
