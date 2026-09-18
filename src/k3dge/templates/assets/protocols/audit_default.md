# Audit Protocol — Default (5-Pass / 8 维)

> **事实源**：`k3dge` 仅验"报告有无"（`k3dge check`），透镜判断在本文件；`k3dit` 的 `audit-method.md` 优先于本文件。

## 交付

`docs/reviews/YYYY-MM-DD-<scope>.md`，表头 12 列 `ID|日期|严重度|优先级|类型|问题描述|位置|状态|处置|验证|复审|验收`（`状态∈{已修,待修,有意留}`；`复审∈{待复审,通过,驳回}`；`验收` 为 `验收人 YYYY-MM-DD [#reason]`）。

> **位置钉子（写源）**：在每行 `位置` 处钉 v2 钉 `# k3dit:pending <ID> sev=.. prio=.. type=.. <描述>`（文档用 `<!-- ... -->`）。判读四格写源＝钉；账本与 12 列报告＝钉的投影（每轮 harvest 重生成，非手填）；`k3dge check` 扫到并在 `[NEXT]` 报 `pending=N`。生命周期：修席翻 `fixnote`、复核背书翻 `fixed`、有意留翻 `leftover`，**拔钉归 Hall**（peer_contract §8 / ADR-0025 §2.7）。

> **一轮 = 一份报告**：合并审计模块（ADR-0025）出**一份** 12 列报告——文档审计与代码/价值/复核各窗产出后 join 成这一份；`待修=0` 才算"审过一遍"。质量不再是独立 peer/报告（`quality_default.md` 仅存历史指针）。

## 5-Pass 透镜（一次一轮）

**Pass 1 — 健壮性与安全**：边界/空值/正则/子进程超时/事务回滚/注入/密钥 + Vibe `SQL/eval/pickle`
**Pass 2 — 架构与边界**：`DAG` 单向/内聚/分层/违 `ADR` + Vibe 分层割裂
**Pass 3 — 设计与契约**：策略多态/入出参/展示与核心解耦 + Vibe 过度设计
**Pass 4 — 一致性与验证**：状态/缓存/跨平台/时序 + Vibe 幻觉 `API`/`try/pass`，**无测试即缺陷**；**proven-red**（diff 新增测试须在修前码/merge-base 上真红：断言失败才算打中，ImportError/缺符号不算；旧码已绿＝测试没锁住这个洞）。不在 `k3dge check` 里跑。
**Pass 5 — 性能与简洁**：死代码/重复 `IO`/热循环/`N+1` + Vibe 循环内 `IO`

> 8 维叠于对应轮，不另起互斥清单；`k3dge check` 指纹/多轨同构等仍按 `Pass 4` 原条目。

## 前置

`docs/reviews/LEFTOVERS.md` + `docs/architecture/overview.md` §8 先读，不重提已修/有意留。

## Constraints

L2 入场券须逐条确认（agent 进车间前绑定到任务）：

- 交付物写入 `docs/reviews/YYYY-MM-DD-<scope>.md`，表头 12 列 `ID|日期|严重度|优先级|类型|问题描述|位置|状态|处置|验证|复审|验收`
- 5-Pass 透镜逐轮独立执行（健壮安全 / 架构边界 / 设计契约 / 一致验证 / 性能简洁）
- 前置先读 `docs/reviews/LEFTOVERS.md` 与 `docs/architecture/overview.md` §8
- 每行 `状态 ∈ {已修, 待修, 有意留}`；`复审 ∈ {待复审, 通过, 驳回}`；`验收` 为 `验收人 YYYY-MM-DD [#reason]`

## Doc Audit（文档审计，per-type，文档变动时）

> **与 5-Pass 同源**：本节是同一份 k3dit 审计协议的一个 **scope**——代码走 5-Pass，文档走本节。二者由同一 peer（k3dit）执行、同一 12 列报告、同一 `on_pre_seal` verify，不是第五域、不另起 harness（ADR-0005）。`k3dge` 只**指路**（同一个审计 prompt，按 `target_scope` 路由到本节）并**提供事实**（`k3dge_adr_index`），不执行、不判。

**触发**：文档改动时（非里程碑）。**T-01**：`k3dge check` 是静态硬闸、不跑透镜；doc-audit 在 **check 之后**经 `k3dge doc-audit` 触发（非阻断），走同一条 `k3dit.actions.audit` 链、`target_scope` 为文档时套用本节，产 12 列报告 + 建一个带 `Milestone` 的 `doc-audit` task（本轮不改，封板轮也得闭环，ADR-0022）。**只有 ADR 冲突/覆盖这一项留在里程碑审计**（`k3dge_adr_index` 事实 + k3dit 判，ADR-0005），不在每次 commit 的 doc-audit 里做。

**per-type 透镜**：
- **ADR — 集合自洽（冲突 / 覆盖 / 正交）**：两篇 *未 superseded* 的 ADR 不应无声共享 scope / decision-topic（冗余）；**正交性**——Decision 不得复述其它 ADR 的规范正文（复述＝第二源），跨篇事实应以 `见 ADR-XXXX §Y` 指针引用、单一 owner；指针须完整——`Supersedes`/`Related` 不悬空、被取代的 ADR 不再被当现行引用。事实来自 `k3dge_adr_index`（AdrIndex + O(n) 重叠/指针 findings，**非判断**）；冲突/冗余/正交由 k3dit 判。
- **通用 — AUTHORING 规则合规**：改动文档须符合其类型 `AUTHORING.md`（结构已由 `.schema.json` 硬闸；此处审"是否真按软规则写"）。ADR 的 `Note:` 只有一个字段（默认 `-`），多次操作按 ① ② ③ 编号续写、不并列多行；动用例外（就地修订 / 物理删除 / 改名）必须留痕，含授权席位与过闸口径（real lens | manual fallback + 可复跑证据）。**正文不写修订史**（「修正（date）」「原稿 / 旧句 / 现稿」层归 `Note:`；沿革与授权在 Note，正文只留现行决策）。**人读优先**：决策先行；一行一点（行宽 ~100 字）；函数名/路径/步骤序等实现细节下沉 `docs/specs/` 或 task；引用放句末；标题用名词短语、不堆斜杠。

**不审**：文本质量（写得好不好 → k3dit LLM 部分）、思想是否值得（→ 合并审计模块内的价值窗，非独立 peer）。文档审查 ≠ 给思想打分。

**k3dge 提供的事实工具**：`k3dge_adr_index`（ADR 索引 + 重叠/指针 findings JSON，**非判断**；冲突/冗余由 k3dit 判）。

> **k3dit 可达时**：k3dit 应使用含本节的同源协议（其 `audit-method.md` 须含本节，与本文同源）；k3dit 不可达时回退到本仓 `docs/protocols/audit_default.md`（即本节所在文件）。
