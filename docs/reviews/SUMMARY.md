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
| P1-06 | `K3DGE_BASE_SHA` 是 argv 不是 shell | [2026-08-25-pass1-robustness-security.md](2026-08-25-pass1-robustness-security.md) |
| P1-09 | `test_command_template`：能改 manifest 已能改命令 | 同上 |
| P2-PUR-04 | `render_readme_layout` 仍被 generate-docs 调用 | [2026-08-25-pass2-architecture-dag.md](2026-08-25-pass2-architecture-dag.md) |
| D-01/02/03/06/10/11 | 两提取器 + 零 TS，不抽 register/ABC | [2026-08-25-pass3-design-abstraction.md](2026-08-25-pass3-design-abstraction.md) |
| D-07/08/12 | MCP 同域适配、本地 stdio、seal 恒 bump | 同上 |
| D-09 | pyproject 双引号形态固定 | 同上 |
| P4-05/08 | architecture 与运行时状态不进 PAIRS | [2026-08-25-pass4-consistency-alignment.md](2026-08-25-pass4-consistency-alignment.md) |
| P4-06 | doc/task 薄路由；audit 见 P2-PUR-06 | 同上 |
| P4-07 | 矩阵 ≠ L2 执行（ADR 0005） | 同上 |
| P5-02..07 | 性能阈值未到 | [2026-08-25-pass5-simplicity-performance.md](2026-08-25-pass5-simplicity-performance.md) |

推翻某行 = 改 overview §5.1 并在本文件注明，不要只在新审计里再开一张单。

## M1 — 08-25 审计落地封板（2026-08-25）

- **报告**：[2026-08-25-M1-align.md](2026-08-25-M1-align.md)
- **范围**：14 条 `Milestone: M1` 任务（P1 边界、D-04 哈希、DAG/`audit` 子命令、spec 矩阵、MCP 双 collect）
- **未进本板**：0001 / 0002 deferred / 无 Milestone 的 template-drift done
- **验收**：Full Matrix PASS；C1/C2 否，跳过重构，准予 `k3dge milestone seal M1`

## M0 — 自举期任务封板（2026-08-24）

- **报告**：[2026-08-24-M0-align.md](2026-08-24-M0-align.md)
- **范围**：19 条 `Status: done` 任务（本地安装、契约/MCP/封板闸、`.agent` 协议、version、脚手架 PAIRS）
- **未进本板**：0002 deferred。脚手架自举跳过后补为 [tasks/2026-08-24-fix-template_drift_self_host_only.done.md](../tasks/2026-08-24-fix-template_drift_self_host_only.done.md)
- **验收**：Full Matrix PASS；C1/C2 否，跳过重构，准予 `k3dge milestone seal M0`

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

## 2026-08-24 — 项目更新后 8 维（version / 双 0016）

- **报告**：[2026-08-24-post-update-8dim.md](2026-08-24-post-update-8dim.md)
- **基线**：61 passed / 1 skipped / `k3dge check --with-tests` PASS
- **范围**：更新后全仓；不重开 §5.1 与已修 A/S 项
- **摘要**：两份 ADR 0016 撞号；`validate_versions` 被 `except pass` 吞掉且缺字段不算漂移；version 零测试；CLI seal bump、MCP 不 bump；bump 非原子；init 路径写死 k3dge；MCP 审计 prompt 仍指向缺失的 k3dit protocol
- **处置（回记）**：U-01..U-07 **已修**（ADR 0017、version 闸/测/MCP seal bump/原子写/`package_root`、prompt 回退）。脚手架门控 G-01..G-04 另见下一节，未关

## 2026-08-24 — 脚手架对齐锁 vs 门控

- **报告**：[2026-08-24-scaffold-gate-lock.md](2026-08-24-scaffold-gate-lock.md)
- **范围**：为「脚手架与本体未对齐而 check 不红」加长 `PAIRS`、删 `docs/log`
- **摘要**：pytest 能锁到的变多了；`k3dge check`（含 pre-commit）仍不比 assets。只改 `AGENTS.md` 不标 templates 域。PAIRS 仍漏 memo/reviews；architecture 模板仍是 k3dge 四域
- **处置（回记）**：G-02/G-03/G-04 已修。G-01 本仓已进 check，下游跳过见 [tasks/2026-08-24-fix-template_drift_self_host_only.done.md](../tasks/2026-08-24-fix-template_drift_self_host_only.done.md)

## 2026-08-25 — Pass 1 健壮性与安全（边界/类型/正则/子进程/事务/注入）

- **报告**：[2026-08-25-pass1-robustness-security.md](2026-08-25-pass1-robustness-security.md)
- **基线**：`70 passed / 1 skipped / 44 subtests / k3dge check --with-tests PASS / 4 域契约已同步`
- **范围**：Pass 1 单透镜：边界/空值、正则 ReDoS、子进程超时、事务回滚、污点/注入、密钥硬编码、Vibe 特检
- **摘要**：9 项。P1-01 `ignore=[""]` 崩闸（不是空列表）；P1-02 部分 `read_text` 未捕 `UnicodeDecodeError`（契约路径已包）；P1-03 POSIX 上 Windows 盘符绕过；P1-04 NUL；P1-05 `rglob` 跟符号链接；P1-07 changelog 非原子写；P1-08 `int()` 接受负版本。P1-06 不是 shell 注入。
- **处置**：7 转 M1 tasks（P1-01/02/03/04/05/07/08）/ 2 有意留（P1-06、P1-09）

## 2026-08-25 — Pass 2 架构与拓扑（依赖 DAG / ADR / 域纯度 / 文档边界）

- **报告**：[2026-08-25-pass2-architecture-dag.md](2026-08-25-pass2-architecture-dag.md)
- **基线**：`70 passed / 1 skipped / 44 subtests / k3dge check --with-tests PASS / 4 域契约已同步`
- **范围**：Pass 2 单透镜：依赖 DAG 单向、`ADR` 一致性、域职责纯度、`reference` 投影边界
- **摘要**：10 项。`engine → templates.pairs` 与 overview 孤岛冲突（设计债，不是崩闸）；`k3dge audit triage` 违 ADR 0005。
- **处置**：2 独立 M1 tasks（DAG-01 并入 DAG-02/PUR-01/02/ADR-01/D-05/META-01；PUR-06 并入 PUR-05）/ PUR-03 并入 P4-03 / 1 有意留（PUR-04）。P2-DAG-01 为 P1 不是 P0。

## 2026-08-25 — Pass 3 设计与抽象（OCP/装饰器/展示与哈希/抽象质量）

- **报告**：[2026-08-25-pass3-design-abstraction.md](2026-08-25-pass3-design-abstraction.md)
- **基线**：`61 passed / 1 skipped` 延续 08-24 post-update；四域契约已同步；单透镜仅审 `contract.py/evaluator.py/version.py/mcp.py`（+ `_ts.py/manifest.py/generator.py` 交叉）
- **范围**：Pass 3 单透镜，不重开 F-07/F-08 主路径与 §5.1 有意留，仅开其残余设计债
- **摘要**：12 项。真正要修的是 D-04：哈希含文件名，重命名误漂。D-05 是 DAG-01 同一条。其余为两提取器/零 TS/MCP 同域适配下的抽象债。
- **处置**：1 转 tasks（D-04，P4-04 并入）/ 1 并入 DAG-01（D-05）/ 10 有意留（D-01/02/03/06/07/08/09/10/11/12）

## 2026-08-25 — Pass 4 一致性与对齐（契约哈希/多轨同构/矩阵/脚手架镜像）

- **报告**：[2026-08-25-pass4-consistency-alignment.md](2026-08-25-pass4-consistency-alignment.md)
- **基线**：`70 passed / 1 skipped / 44 subtests` + `k3dge check` (selective 3 域) / `--force-full` (4 域) / `--force-full --with-tests` 均 PASS；`k3dge sync` 幂等；4 域 hash 已同步（cli 3f89e… / engine 5c0b13… / sync 819887… / templates b05302…）
- **范围**：Pass 4 单透镜：`k3dge check`/`sync`、`manifest`/`specs`/`templates/assets`↔`scripts`/`AGENTS.md`/`.agent/*` 多轨同构、Verification Matrix 17 引用、scaffold 镜像。复用 `contract.collect_domain_interface` + `TEMPLATE_DRIFT` 自举判定 + `evaluator._check_domain` 存在性校验
- **摘要**：9 项。P4-01 sync 矩阵缺 `Level`；P4-02 `VERSION_MISSING` 无生产方；P4-03 `TC-SYNC-02` 仍把 README 算在 sync。P4-04 即 D-04。P4-09 通过。
- **处置**：3 转 tasks（P4-01/02/03）/ 1 并入 D-04（P4-04，P0 降 P1）/ 4 有意留（P4-05/06/07/08；P4-05/08 注释已写入 `pairs.py`）/ 1 通过（P4-09）

## 2026-08-25 — Pass 5 简洁性与性能（死代码 / 重复 AST / 临时对象 / 复杂度 / IO）

- **报告**：[2026-08-25-pass5-simplicity-performance.md](2026-08-25-pass5-simplicity-performance.md)
- **基线**：`70 passed / 1 skipped / 44 subtests` + `k3dge check --force-full` PASS / `k3dge sync` 幂等；4 域 hash 已同步；单透镜仅审 `src/k3dge/**` + `scripts/*`
- **范围**：Pass 5 单透镜：死代码/重复计算与 IO/热循环分配/N+1/复杂度权衡；不重提 §5.1 有意留 `F-14/F-15/R3-1/R3-4` 与 Pass 3/4 已转 tasks
- **摘要**：8 项。可修的是 P5-01 MCP 一域双收集。其余为规模阈值未到的微冗余。P5-08 无死代码。
- **处置**：1 转 tasks（P5-01）/ 6 有意留（P5-02..07，阈值见 §5.1）/ 1 通过（P5-08）

## 2026-08-25 — 五轮处置对齐后的 M1 工作项

落地 14 条 `docs/tasks/2026-08-25-M1-audit-*.md`（均为 `Status: idea`，`Milestone: M1`）。报告写「转 tasks」的每一行都有对应文件或并入说明；其余改为有意留并进入 overview §5.1。未实施代码。

## 2026-08-25 — k8d3e-a4 穿透式审查与 P1 修复

- **报告**：[2026-08-25-k8d3e-a4-fix.md](2026-08-25-k8d3e-a4-fix.md)
- **基线**：`85 passed / 1 skipped / 47 subtests / k3dge check PASS / 4 域契约已同步`（`k3dge sync` 后 `engine` 哈希重算）
- **范围**：`#k8d3e-a4` 5 轮 8 项（R1 健壮/R2 架构/R3 设计/R4 一致性/R5 简洁），`diff/generator/version/milestone/scaffold` 全量
- **摘要**：5 项 P1 立即修复已合入（SEC-01 `diff` 仅 `R/C` 拆 `->`、SEC-02 `generator` `find` 防崩、`DSN-01` 跳过 `Unreleased`、CON-01 `archive` 阻断、CON-02 变量遮蔽），`R2` 无缺陷
- **处置**：5 已修 / 3 有意留候选（SEC-03/PRF-01/PRF-02）

## 2026-08-26 — k3dit 5-Pass 穿透（pipeline/HUMAN_CHECKPOINT/mcp sync 增量）

- **报告**：[2026-08-26-k3dit-5pass-pipeline.md](2026-08-26-k3dit-5pass-pipeline.md)
- **基线**：`86 passed / 1 skipped / 49 subtests / k3dge check --force-full PASS`
- **范围**：`e0de18d..f987092`（pipeline.toml + HUMAN_CHECKPOINT + mcp sync + changelog 清单），经 `k3dit_run_audit` MCP 取透镜逐轮执行，报告经 `k3dit check_report` 校验通过
- **摘要**：14 项待修（P1 四项：N1-01 `.mcp.json` 损坏覆盖、N1-02 tomllib py3.10 假成功、N1-03 非 dict TypeError、P4-01 seal changelog 双轨漂移；P2 七项：路径逃逸/DAG 缺边/降级断链/零测试/checkpoint 双编码等）+ 1 有意留（P2-03 pipeline 字节锁追赶成本）
- **处置**：13 转 M2 tasks（`2026-08-26-M2-audit-*.md`）/ 1 有意留
