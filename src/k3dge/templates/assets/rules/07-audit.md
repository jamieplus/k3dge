# Rule 07 — Audit (审计结果归档)

* 透镜不在 `k3dge` 包内，优先 `../k3dit/docs/guides/protocol.md`，否则 `docs/protocols/audit_default.md`（`docs/guides/` 为人读指南，不含机器 SOP，见 ADR 0002 Diátaxis）。
* 产出 `docs/reviews/YYYY-MM-DD-<scope>.md`（9 列），未修未否决必转 `tasks`。
* 新审计前先读 `SUMMARY.md`，不重报已修/有意留。
* 修复后必回填：同一报告追加 `## 回填` 小节（原表不改）更新 `状态`→`已修/有意留`，并同步 `SUMMARY.md` 回填行；`k3dge sync` 后 `k3dge check` 全绿方可 `seal`。
* 每个待修缺陷必在 `docs/incidents/INC-YYYYMMDD-<TYPE>-<slug>.md` 留 B-T-D 复现（`Baseline`/`Treatment`/`Design`，见 `docs/incidents/README.md` 命名 `INC-YYYYMMDD-<TYPE>-<slug>.md` 与 Frontmatter 模板），含可重跑命令与 `stderr` 片段，否则视为未闭环（`docs/branches/` 仅为 `check` 红后试错分支，`docs/incident/` 单数已废弃）。
* 外部 harness（`k3dit/k3che/k3lity` via `pipeline.toml`）调用失败走 `default` 时必须高亮 `WARN[HARNESS FALLBACK]` 到 `stderr` 并在报告 `审计人/透镜来源` 注明 `manual` vs `k3dit`（含 `reason`）。
