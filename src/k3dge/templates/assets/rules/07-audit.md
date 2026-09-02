# Rule 07 — Audit (审计结果归档)

* 透镜不在 `k3dge` 包内，优先 `../k3dit/docs/guides/protocol.md`；复审层见 `docs/protocols/verify_default.md`，审计层见 `docs/protocols/audit_default.md`（`docs/guides/` 为人读指南，不含机器 SOP，见 ADR-0002 Diátaxis）。
* 产出 `docs/reviews/YYYY-MM-DD-<scope>.md`（12 列：`ID|日期|严重度|优先级|类型|问题描述|位置|状态|处置|验证|复审|验收`）。未修未否决**留在报告行本身**（配 `位置` 的 `k3dit:pending` 标记），一份报告对应**一个** `report:` 指针的 report-task（1 report = 1 task）；**不再逐条建 task**。特别大的单条才在 `处置` 写 `转 sub-task <id>` 例外拆出（ADR-0022）。
* 新审计前先读 `docs/reviews/LEFTOVERS.md`，不重报已修/有意留。
* 角色流（两层 protocol 对应两步）：**审计角色**出报告（`待修`，走 `peers.k3dit.actions.audit`：`mcp(k3dit_run_audit) → manual(audit_default.md)`）→ **修改者角色**改码并 `k3dge task done` **自动回填**报告表 `状态→已修`+`## 回填`（`_auto_backfill_reviews`）→ **审计角色**验收（走 `peers.k3dit.actions.verify`：`mcp(k3dit_check_report) → cli(k3dit check-report) → manual(verify_default.md)`）后流程结束（`seal`）。
* 回填为修改者职责，验收为审计者职责，不可同一角色自审自填后直接 `seal`。
* 每个待修缺陷必在 `docs/incidents/INC-YYYYMMDD-<TYPE>-<slug>.md` 留 B-T-D 复现（`Baseline`/`Treatment`/`Design`，见 `docs/incidents/README.md` 命名 `INC-YYYYMMDD-<TYPE>-<slug>.md` 与 Frontmatter 模板），含可重跑命令与 `stderr` 片段，否则视为未闭环（`docs/branches/` 仅为 `check` 红后试错分支，`docs/incident/` 单数已废弃）。
* 外部 peers（`k3dit/k3che/k3lity` via `pipeline.toml` 的 `[peers]` + `[pipelines]`）调用失败走 `default` 时必须高亮 `WARN[HARNESS FALLBACK]` 到 `stderr` 并在报告 `审计人/验收人` + `透镜来源` 注明 `manual` vs `k3dit`（含 `reason`）；审计/复审两级 protocol 各有独立 manual 兜底，降级链见 `pipeline.toml`。
