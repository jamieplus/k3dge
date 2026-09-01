# Memo: 人读文档自省体治理 — 审计先行、收敛后升闸

- **类型**：暂无法落地（方向明确但需 3 轮 audit 观察收敛，且属 `harnesses/audit` 范畴，非 `src/k3dge` 门禁）
- **念头**：` .agent/README.md` 等人读文档出现 AI 自省体（"读到这里是因为已知路径，不是因为被逛到""主流 harness 不扫这里"）不应在 `gate` 硬拦。`gate` 只拦可正则判定的硬事实（`VERSION_MISMATCH`/`guide-stub`），自省体这类"是否像人话"的软风格应先在 `harnesses/audit` 的 `Pass 3/4` 以 9 列审计抓取（`有意留: 推导已收至 ADR` / `已修: 改为是什么/怎么用`），待累积 3 轮同类且收敛为 2-3 条硬正则后，再晋升为 `DOC_STYLE` 门禁。期间 `.agent/README.md` 保持 `scaffold` 生成件（`assets/agent-readme.md` 锁）以控增量污染，存量自省句暂不追改
- **触发场景**：在 `GitHub` 推 ` .grok` 误追踪后，讨论"AI 自省式写作如何规范"时提出；用户追问"有明确边界吗？做成 gate 还是 audit 发现"，确认边界后判定不立即可门禁、且部分属并列 `audit` harness
- **关联度**：弱相关 — `k3dge` 本仓仅提供 `test_template_sync` 锁与 `guide-stub` 硬拦，风格审计属 `harnesses/audit` 职责（`ADR-0006` 并列 harness 分工）
- **Date**: 2026-08-24
- **处置**：仅 memo 存档，不建 `tasks`；当 `harnesses/audit` 累积 3 轮同类自省体且模式收敛时，由该 harness 的 `tasks` 晋升（`Status: idea`，附硬正则草案），原 memo 移入 `archive/`
