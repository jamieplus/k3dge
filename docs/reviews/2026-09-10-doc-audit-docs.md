# 审计：文档审计（ADR-0024/0025 + AGENTS/rules/pipeline/protocols/tasks + k3dit spec）

- **Date**: 2026-09-10
- **基线**: 工作树 2026-09-10（`k3dge check` 绿；`k3dge_adr_index`＝`analyze_adr_coverage` 可达）
- **审计人**: k3dit Doc Audit lens（独立 doc-audit 执行者）
- **范围**: ADR 集合自洽（冲突/覆盖/正交）＋ AUTHORING 软合规

## 发现

| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D-1 | 2026-09-10 | 中 | P1 | 冲突 | §2.7 已定「任何席不删钉、复核翻 `fixnote→fixed`、Hall 机械拔 `fixed`」，但同篇 §2.2 仍写「`fixed` 由复核删 `fixnote` 产生」，§2.3 仍写「翻 `fixed` 后由复核窗逐条验收」（先后颠倒），同 ADR 内直接相抵。 | docs/adr/0025-hall-harness-topology.md:66,97 | 已修 | 已修（§2.2/§2.3 旧句抹平，统一为复核正向翻 fixnote→fixed、Hall 机械拔）。 | ADR-0025 §2.2:67、§2.3:98 与 §2.7:172,188 口径一致；正文无「复核删 fixnote」残留。 | 通过 | verifier 2026-09-10 |
| D-2 | 2026-09-10 | 低 | P3 | 规范 | Note 段用裸旧号记录改名/平移（ADR-0026、ADR-0027、ADR-0028 均已不存在），`analyze_adr_coverage` 报 `pointer_dangling`；ADR-0023 §2.4 要求历史以「事件」而非裸号描述。 | docs/adr/0024-audit-evidence-exchange-topology.md:13；docs/adr/0025-hall-harness-topology.md:14,17 | 已修 | 已修（Note 旧号改事件表述，裸 ADR 号已清）。 | `analyze_adr_coverage` 非 scope_overlap findings=`[]`，无 `pointer_dangling`。 | 通过 | verifier 2026-09-10 |
| D-3 | 2026-09-10 | 低 | P3 | 规范 | 新增就地修订 Note 的「过闸口径 = manual fallback」只写授权理由（会话授权、agent 代改字），未带 AUTHORING 要求的可复跑证据（如 `[PEER-MANUAL] … no live lens`）；同仓旧段（0006/0018/0020/0023）均带实测证据。 | docs/adr/0024-audit-evidence-exchange-topology.md:16；docs/adr/0025-hall-harness-topology.md:23 | 已修 | 已修（追加独立文审段，带报告路径与 real lens 过闸口径）。 | ADR-0024:17、ADR-0025:24 含报告 `docs/reviews/2026-09-10-doc-audit-docs.md` 与 `real lens`；对齐 AUTHORING:55 模板。 | 通过 | verifier 2026-09-10 |
| D-4 | 2026-09-10 | 中 | P2 | 冲突 | 三处仍把 `k3dit:pending` 定义为「只读指针、理由/改法/验收只写报告、不入正文」；ADR-0025 §2.7 与 peer_contract §8「写源纪律」已定钉（树上）＝写源、账本/12 列＝投影、修席 note＝改法，直接相抵。 | docs/protocols/audit_default.md:9；AGENTS.md:43；.agent/rules/04-milestone.md:15 | 已修 | 已修（三处及模板镜像统一改「钉＝写源」口径）。 | `audit_default.md:9`、`AGENTS.md:43`、`.agent/rules/04-milestone.md:15` 及 `src/k3dge/templates/assets/...` 三镜像均为写源/投影口径。 | 通过 | verifier 2026-09-10 |
| D-5 | 2026-09-10 | 低 | P3 | 冗余 | 同一 trigger「In-flight ratchet job (`[NEXT] ratchet_open`)」在触发表内重复两行（中文详版＋英文简版），一行一点的表格出现同键两写。 | AGENTS.md:39,45 | 已修 | 已修（删除重复的英文简版行）。 | `AGENTS.md` 中 `ratchet_open` 仅 1 处（:39），无重复 trigger 行。 | 通过 | verifier 2026-09-10 |
| D-6 | 2026-09-10 | 中 | P2 | 冲突 | k3dit spec 仍写判断窗「allow edit 以便写本窗 artifact.json」；ADR-0025 §2.7 已定判读席只写树上钉、不产 `artifact.json` items，Hall 以私有 `done_path` 心跳收成、`_apply_live` 忽略席产 JSON。 | k3dit/docs/specs/k3dit/spec.md:19 | 已修 | 已修（artifact.json 句改「落/翻钉」，契约哈希已 sync）。 | `k3dit/docs/specs/k3dit/spec.md:19` 现为「allow edit 以便在窗 src 落/翻钉」，无 artifact.json；心跳由 `done_path`（:70）承载。 | 通过 | verifier 2026-09-10 |
| D-7 | 2026-09-10 | 中 | P2 | 覆盖 | 合并口径未覆盖契约：`.agent/pipeline.toml` 已删 `[roles.quality]` 并声明「质量不在角色表」，但 peer_contract §0 仍列三角色 `audit/quality/cache`、§4 工件表 `findings` 产出方仍＝`quality`。 | docs/protocols/peer_contract.md:8,11,85 | 已修 | 已修（角色改两角色，findings 产出方改指判读窗）。 | `peer_contract.md:8` 两角色 audit/cache、`:11` gate 类（audit）、`:85` findings 产出方＝audit 模块内判读窗。 | 通过 | verifier 2026-09-10 |

## 回填

- 2026-09-10 修后复审（独立 agent 复核同一报告，未由修者自证）：**待修 0 / 有意留 0 / 已修 7**。
- 关键证据：`analyze_adr_coverage` 非 `scope_overlap` findings 归零；`ratchet_open` 单行；钉写源纪律三处 + 模板镜像对齐；`peer_contract` 角色收敛 `audit/cache`；k3dit spec 去 `artifact.json`；ADR-0025 §2.2/§2.3 抹平到 §2.7；Note 补独立文审证据。
- 过程证据：`docs/incidents/INC-20260910-CON-audit-merge-doc-drift.md`（B-T-D + 5 Whys + 防退化）。
