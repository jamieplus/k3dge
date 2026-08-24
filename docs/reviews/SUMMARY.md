# Reviews Summary — 审计摘要索引

> Agent 先读此文件定相关性，再按需读单篇 `docs/reviews/*.md`。新增报告时在此追加一节。

## 现行有意留（勿重开）

否决理由与失效条件以 [`docs/architecture/overview.md`](../architecture/overview.md) **§5.1** 为准。下表只做 ID 索引：

| ID | 一句话 | 报告 |
| --- | --- | --- |
| A-11 | git 无 timeout：本地立刻返回；加 timeout 会把门禁变成假失败 | [2026-08-24-5pass-audit.md](2026-08-24-5pass-audit.md) |
| S-13 | MCP 任意 `workspace_path`：本地 stdio = OS 用户；改网络 MCP 必须重开 | [2026-08-24-8dim-vibe-audit.md](2026-08-24-8dim-vibe-audit.md) |
| F-14 / LR-5 | `_replace_between_all` O(N²)：spec ≪ 100KB，可读性优先 | [2026-08-23-5pass-audit.md](2026-08-23-5pass-audit.md) |
| F-15 / LR-6 | milestone 重复读盘：活跃任务少，OS 缓存够 | 同上 |
| R3-1 | 三处域表行：4 域 + ADR 0002 判据/投影不可合并 | [2026-08-21-line-by-line.md](2026-08-21-line-by-line.md) |
| R3-4 | 函数内 import subprocess：L2 冷路径 | 同上 |

推翻某行 = 改 overview §5.1 并在本文件注明，不要只在新审计里再开一张单。

## 2026-08-21 — 全仓逐行三轮

- **报告**：[2026-08-21-line-by-line.md](2026-08-21-line-by-line.md)
- **基线**：20 tests / gate PASS / 4 域契约已同步
- **范围**：`src/k3dge/engine` `contract/diff/manifest` `src/k3dge/sync` `templates` `scripts/*` 全量
- **摘要**：L1 签名提取缺 `*args/kwonly/defaults/基类`、TS 0.21+ API 不兼容、引号路径/重命名解析、manifest 通配跨目录、非 git 目录崩栈等 15 项已修；3 项冗余（域表行构建三处重复等）判"有意留"
- **处置**：15 已修 / 3 有意留（过度优化，记录在案防重提）

## 2026-08-23 — 一致性 + 逻辑冗余（第二轮）

- **报告**：[2026-08-23-consistency-logic.md](2026-08-23-consistency-logic.md)
- **基线**：30 tests / 26 subtests / gate --with-tests PASS / 4 域契约已同步
- **范围**：全量一致性 5 维 + 逻辑冗余 6 项（`engine`/`cli`/`sync`/`templates`/`scripts`/`docs`）
- **摘要**：`gate` 双轨透传、`tasks` 状态枚举、`architecture` 箭头、`spec` 矩阵 TC、模板漂移 5 项已修；`evaluator` 死代码、`manifest` 临时对象、`sync` 双重 AST 3 项已修；2 项（`_replace_between_all` O(N²)等）判有意留
- **处置**：8 已修 / 2 有意留

## 2026-08-23 — 5-Pass 专项深度审计（合并版）

- **报告**：[2026-08-23-5pass-audit.md](2026-08-23-5pass-audit.md)（合并 `#7q3d9-a19` 14 项 + `#8d4m2-a1` 15 项，去重后超集）
- **基线**：33 tests / 26 subtests / gate --with-tests PASS / 4 域契约已同步（含 `cli/mcp.py` 零漂移桥接已重算，零漂移）
- **范围**：5-Pass 全量（健壮性与安全 / 架构与拓扑 / 软件设计 / 契约一致性 / 简洁性与性能），`src/k3dge/**` + `scripts/*` + `docs/**` + `tests/**` 全量
- **摘要**：15 项全闭环（F-01 `gate` 透传、F-07 装饰器感知、F-08 展示与哈希解耦、F-09 6 用例、F-12 死代码、F-13 双缓存等 13 已修；F-14 O(N²) 与 F-15 读盘 2 项有意留），零新增阻断，生产就绪
- **处置**：13 已修 / 2 有意留 / 0 转 tasks（`#7q3d9-a19` + `#8d4m2-a1` 合并绿灯，原 `5pass-isolation.md` 已归并）

## 2026-08-24 — 5-Pass 全量复核

- **报告**：[2026-08-24-5pass-audit.md](2026-08-24-5pass-audit.md)
- **基线**：36 tests / 26 subtests / gate --with-tests PASS / 4 域契约已同步
- **范围**：5-Pass 全量复扫（正确性 / 架构 / 设计 / 契约 / 简洁），不重提 F-14/F-15/R3-1/R3-4
- **摘要**：A-01 封板 `M1⊂M10` 子串误放行、A-05 损坏 manifest 崩栈已修；MCP `force_full` 名不副实、align 复制 L2、TC 过称、TS 整段入哈希、抽取吞 SyntaxError、DAG/ADR 措辞 8 项转 tasks；git timeout 与既有有意留不重开
- **处置**：2 已修 / 8 转 tasks / 2 有意留

## 2026-08-24 — 8 维 + Vibe 特检（相对 08-24 透镜增量）

- **报告**：[2026-08-24-8dim-vibe-audit.md](2026-08-24-8dim-vibe-audit.md)
- **基线**：36 tests / 26 subtests / gate --with-tests PASS / 4 域契约已同步
- **范围**：用户给出的 8 维 + Vibe 五轮（安全污点/回滚/状态机绕过/无测试即缺陷等）；不重提 A-01..A-12
- **摘要**：有新发现。S-02 `--with-tests` 缺 spec 时 TypeError 崩栈；S-03/S-04 路径逃逸；S-01 假回滚；S-05 封板验收可绕过；S-07/S-11 测试与配置缺口。无 eval/密钥/SQL。S-13 本地 MCP 任意 workspace 有意留；S-12 并入 tasks/0001
- **处置**：0 已修 / 10 转 tasks / 1 并入 0001 / 1 有意留
