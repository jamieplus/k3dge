# Rule 04 — Milestone Lifecycle

* **Milestone cursor**：`.agent/milestone` 纯文本 `M0`→`M1`…，`scaffold` 默认写 `M0`，`seal` 成功后原子 `bump`。
* **任务编码**：`docs/tasks/YYYY-MM-DD-<type>-<slug>.md`（`type` ∈ {audit, feat, fix, docs, chore, refactor}，`slug` 内 `_`），`Status: done` 时后缀 `.done.md`；有 `Milestone: M1` 时文件名中加入 `M1`。
* **触发**：`Milestone` 下全部 `done` → `k3dge milestone align`（Full Matrix）；`align` 成功后 `HUMAN_CHECKPOINT`，分支 `A(y)` 调 `k3dit triage <review>` 创审计任务/`B(N/60s)` 去 `stub` 后 `seal`。
* **钩子链**：`align` 成功后读 `.agent/pipeline.toml` 的 `pipelines.on_align_success` 按序调 `peers`，各 action 的 `transports` 链 `mcp→cli→manual`/`skip` 三级降级；`skip` 亦 `logs/k3dge.log` 记 `HARNESS_SKIP`；复审在 `pipelines.on_pre_seal` 调 `k3dit.actions.verify`。
* **门禁**：`seal` 闸机是 `align-pass`、无 `align-stub`、无 `guide-stub`、正文列出该里程碑全部任务，缺一即 `SEAL REJECTED`。不读 `SUMMARY.md`（ADR-0018）。
* **归档**：`seal` 将 tasks 移入 `docs/tasks/archive/<id>/`；将本里程碑 reviews（文件名含该 id，或正文含 align-pass 标记；他里程碑文件名不动）移入 `docs/reviews/archive/<id>/`，并改写 `docs/reviews/LEFTOVERS.md` 相对链接。失败回滚移动并还原 LEFTOVERS.md。
