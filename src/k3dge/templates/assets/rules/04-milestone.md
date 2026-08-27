# Rule 04 — Milestone Lifecycle

* **Milestone cursor**：`.agent/milestone` 纯文本 `M0`→`M1`…，`scaffold` 默认写 `M0`，`seal` 成功后原子 `bump`。
* **任务编码**：`docs/tasks/YYYY-MM-DD-<type>-<slug>.md`（`type` ∈ {audit, feat, fix, docs, chore, refactor}，`slug` 内 `_`），`Status: done` 时后缀 `.done.md`；有 `Milestone: M1` 时文件名中加入 `M1`。
* **触发**：`Milestone` 下全部 `done` → `k3dge milestone align`（Full Matrix）；`align` 成功后 `HUMAN_CHECKPOINT`，分支 `A(y)` 调 `k3dit triage <review>` 创审计任务/`B(N/60s)` 去 `stub` 后 `seal`。
* **钩子链**：`align` 成功后读 `.agent/pipeline.toml` 的 `hooks.on_align_success` 按序调 `harnesses`，`mcp→cli→manual` 三级降级，`skip` 亦 `logs/k3dge.log` 记 `HARNESS_SKIP`。
* **门禁**：`seal` 三闸机（`align-pass`/`SUMMARY`/`guide-stub`）+ 正文列出全部任务，缺一即 `SEAL REJECTED`。
