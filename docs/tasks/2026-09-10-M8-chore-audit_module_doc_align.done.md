---
status: done
milestone: M8
priority: P2
date: 2026-09-10
---

# k3dge 侧文档/配置对齐合并审计模块（单份 12 列报告、无独立 quality fallback）

- **Status**: done
- **Milestone**: M8
- **Priority**: P2
- **可检索摘要**: ADR 已于 2026-09-10 对齐 ADR-0025 合并审计模块（0004/0006/0018/0020/0022），但 `AGENTS.md`、`.agent/pipeline.toml`、`docs/protocols/quality_default.md` 仍写 audit+quality 两份 12 列报告与独立 quality peer/fallback，需同批改齐
- **Date**: 2026-09-10

## Intent

把 k3dge 侧（消费侧）仍在描述「两 harness / 两份报告」的活文件对齐 ADR 新口径：一轮 = 一份 12 列报告（合并审计模块各判读窗产出后 join），quality 是模块内窗口、无独立 peer 与独立 fallback；封板资格由 `audit_trigger.audit_closed` 判。与 M8 G1（审计模块合并）配套，避免文档与运行面长期两套说法。

## Notes

- `AGENTS.md` §12：Milestone all `done` 行「audit(k3dit)+quality(k3lity) **各出一份 12 列报告**」与「两份都 待修=0」；`seal` hook 行 `on_seal_enter`/`on_pre_seal` 的 k3lity stage、`--kind quality` 措辞。
- `.agent/pipeline.toml`：`[peers.k3lity]` 整块与 `[roles.quality]`、`pipelines.on_seal_enter` / `on_pre_seal` 的 `k3lity.*` stage、注释「k3lity (quality) produces a SECOND 12-col report」。
- `docs/protocols/quality_default.md`：整份为独立 quality peer 的 manual 兜底（「各出一份 12 列报告」「审计报告（k3dit）+ 质量报告（k3lity）」）；按 ADR-0018 §2.8 应随合并退役，质量窗兜底并入 audit/verify 协议或标注 legacy。
- `docs/protocols/audit_default.md:9,11`：「**标记只是指针**：理由/改法/验收只写本表」与「**一轮 = 两份报告**：质量层（k3lity）另出 `...-quality.md`」——与 ADR-0025 §2.7（钉=写源、报告=投影）和单报告模型冲突，按新口径改写或指向 `peer_contract §8`。
- 待核实现面（改了文档就得同批或紧后确认）：`engine/audit_trigger.audit_closed` 是否仍要求两 kind 齐、`engine/pipeline_runner.py` 的 stage 解析、`milestone audit-submit --kind quality` 的落盘路径、`engine/nextstep` 的 `[NEXT]` 文案。
- 时序：G1 合并落地前，运行面仍是两 peer；本 task 与 G1 同批改或在其后立即改，别让 `AGENTS.md` 单方面先变。
- `AGENTS.md:43` 与 `src/k3dge/engine/nextstep.py:35` 仍写「标记只是指针…理由/改法写报告不入正文」；`docs/architecture/encyclopedia.md:214` 写「钉在位置（仅指针）」——与 ADR-0025 §2.7（钉=写源、报告=投影）冲突，按新口径改写。
- 依据：`docs/adr/0004-milestone-lifecycle-governance.md` §2.1.3/§2.1.6、`0006` §2.2/§2.3.5、`0018` §2.8、`0020`（Amended-by ADR-0025）、`0022`、`0025` §2.2/§2.7。

## 边界与拆分

- 事实归属：报告口径/窗口划分属 ADR-0025 审计模块；k3dge 侧只改「怎么调用与展示」（AGENTS.md/pipeline.toml/协议兜底文本），不改 peer 内部。
- 边界检查：k3dge 不因文档对齐去读 peer 内部状态；`check` 仍静态（T-01）。
- 桩子先行：可先用 dummy peer 验证单 stage 流程，再切真 peer。

## Related

- `docs/tasks/2026-09-06-M8-feat-hall_G1_merge.md`（peer 侧合并，本 task 是其 k3dge 侧文档/配置配套）
- `docs/tasks/2026-09-06-M8-feat-hall_G6_cutover.md`（k3lity 归档）
- k3dit 侧现役透镜镜像已按 ADR 新标准同步（正交性 + 单 Note 编号）：k3dit `docs/tasks/2026-09-10-M8-chore-align_adr_note_and_orthogonality_lens.done.md`；同节「`位置` 钉子」的指针语言仍待 G1 批统一。
