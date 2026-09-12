# Intentional leftovers

Do not reopen IDs in this table. Overturning a leftover = edit this file, not a shadow list.

Denial reason and reopen condition live here only.

| ID | 一句话 | 报告 |
| --- | --- | --- |
| A-11 | git 无 timeout：本地立刻返回；加 timeout 会把门禁变成假失败 | [2026-08-24-5pass-audit.md](archive/untagged/2026-08-24-5pass-audit.md) |
| S-13 | MCP 任意 `workspace_path`：本地 stdio = OS 用户；改网络 MCP 必须重开 | [2026-08-24-8dim-vibe-audit.md](archive/untagged/2026-08-24-8dim-vibe-audit.md) |
| F-14 / LR-5 | `_replace_between_all` O(N²)：spec ≪ 100KB，可读性优先 | [2026-08-23-5pass-audit.md](archive/untagged/2026-08-23-5pass-audit.md) |
| F-15 / LR-6 | milestone 重复读盘：活跃任务少，OS 缓存够 | 同上 |
| R3-1 | 三处域表行：4 域 + ADR-0002 判据/投影不可合并 | [2026-08-21-line-by-line.md](archive/untagged/2026-08-21-line-by-line.md) |
| R3-4 | 函数内 import subprocess：L2 冷路径 | 同上 |
| P1-06 | `K3DGE_BASE_SHA` 是 argv 不是 shell | [2026-08-25-pass1-robustness-security.md](archive/untagged/2026-08-25-pass1-robustness-security.md) |
| P1-09 | `test_command_template`：能改 manifest 已能改命令 | 同上 |
| P2-PUR-04 | `render_readme_layout` 仍被 generate-docs 调用 | [2026-08-25-pass2-architecture-dag.md](archive/untagged/2026-08-25-pass2-architecture-dag.md) |
| D-01/02/03/06/10/11 | 两提取器 + 零 TS，不抽 register/ABC | [2026-08-25-pass3-design-abstraction.md](archive/untagged/2026-08-25-pass3-design-abstraction.md) |
| D-07/08/12 | MCP 同域适配、本地 stdio、seal 恒 bump | 同上 |
| D-09 | pyproject 双引号形态固定 | 同上 |
| P4-05/08 | architecture 与运行时状态不进 PAIRS | [2026-08-25-pass4-consistency-alignment.md](archive/untagged/2026-08-25-pass4-consistency-alignment.md) |
| P4-06 | doc/task 薄路由；audit 见 P2-PUR-06 | 同上 |
| P4-07 | 矩阵 ≠ L2 执行（ADR-0005） | 同上 |
| P5-02..07 | 性能阈值未到 | [2026-08-25-pass5-simplicity-performance.md](archive/untagged/2026-08-25-pass5-simplicity-performance.md) |
| BV-01 | `bump_version` 跨三文件非原子：单文件 `tmp+replace` 原子，`kill -9` 半漂移由 `VERSION_MISMATCH` 暴露，已加内存回滚；引入跨文件原子需 `write-ahead log` 复杂度不值 | [2026-08-27-5pass-full.md](archive/untagged/2026-08-27-5pass-full.md) |
| T-01 | Meta-Gate vs Orchestrator：`k3dge` 仅元门禁，`pipeline.toml` `on_align_success` 单向 `skip/fallback_to_cli` 调度 `k3che/k3lity/k3dit`，外部挂死不阻断 `GateReport` | [2026-08-27-5pass-full.md](archive/untagged/2026-08-27-5pass-full.md) |
| T-02 | Pure Evaluator vs Mutator：判定与 milestone/version 副作用同域，阈值未到不拆 `lifecycle` | 同上 |
| T-03 | Self-Hosting 嗅探：`Manifest self_hosting` 显式化待规模化再 ADR | 同上 |
| SEAL-01 | `seal` 验 align-pass + 无 stub；报告格式由 `k3dit check-report` 在 `on_pre_seal` 卡 | 同上 |
| AGENTS-SP-01 | `AGENTS.md` 稀疏寻址无已读断言：以 Gate 红灯逼回读 | 同上 |
| M8-code-2 | MCP `workspace_path` 直通 `_find_workspace` 不收敛：本地 stdio=OS 用户；锁 CWD 属编排，改需 ADR（ADR-0006 S-13） | [2026-09-11-M8-audit.md](2026-09-11-M8-audit.md) |
| M8-value-1 | `evaluate` CC61/283 行 god-method：重构无窗内测试保行为，交独立 refactor task（M7-Q3 同域已接受技术债） | 同上 |
| M8-value-2 | 12 列报告解析 ≥5 套口径：全并属 refactor；code-13 已消 `_count_status` 与 `_parse_audit_stats` 分歧 | 同上 |
