# Authoring

Copy `_template.md`. Soft rules (k3dit may judge text quality; k3dge does not):

- Context: constraints only — no chat log, no timeline, no "the user said".
- Decision: invariants and explicit non-goals.
- Consequences: upside, downside, reopen criterion.
- Wrong: "Twenty minutes later we decided…" / "the agent found…". Right: name the constraint and the choice.

Do not judge whether the decision is a *good* idea (k3lity, soft). k3dit may flag two Accepted Decision sections that directly negate each other.

## 人读优先 (readability)

软规则，k3dit 文审按此判（结构另有 `.schema.json` 硬闸）：

- **决策先行**：每节/子节第一句写规则本身；理由、边界、实现随后。
- **一行一点**：一条 bullet 只讲一件事，过长拆子项；行宽目标 ≤ ~100 字，长机制拆编号步骤。
- **细节下沉**：函数名 / 文件路径 / 命令序列 / 内部状态机 → `docs/specs/` 或 task；ADR 只留不变量、契约与权衡（复述实现＝第二源）。
- **引用放句末**：`见 ADR-XXXX §Y` 收在句尾，不打断主句；同段不重复引同一处。
- **少叠括号**：括号不嵌套；加粗只标规则关键词，不标整句。
- **标题用名词短语**：不堆斜杠（「人工入口 / Checklist / loop」拆节或取中心词）。
- **语言**：中文为主；代码标识符用行内 `code`，不把英文术语串当句法。

## 术语（canonical terms）

同一概念只用一个词；改词不改义，语义变更走 ADR。

| 概念 | 用 | 不用 |
| --- | --- | --- |
| 账本（ledger） | 账本 | 台账 |
| 消费仓（被审仓） | 消费仓 | 市民、被审仓 |
| 判读窗（群）/ 判读席 | 判读窗、判读席 | 判断窗、判断席 |
| 钉（pin） | 钉；动作＝收钉，产物＝收成 | 标记、指针（pin 义） |
| Hall（大厅） | Hall；首现注"大厅" | 大厅（除场地比喻句） |
| 闭环 | 闭环（`audit_closed`） | 收口（名词义） |
| 落盘 | 落盘 | 落位 |
| 降级 / 兜底 | 降级＝传输链事件；兜底＝manual 档位 | 混用；fallback 只留代码/工具名 |
| 人 | 人（维护者） | 裸"人" |

例外：stub 类标记仍叫"标记"（`guide-stub` / `align-stub`）；task→报告的 `report:` 指针仍叫"指针"。

## Record lifecycle (from `README.md`; enforce where a machine can)

**没有任何 ADR 操作是无条件的。** 下表每行的"例外"列一旦动用，都必须由**人类在本轮显式授权**，并把痕迹写进该 ADR 的 `Note:` 字段——agent 不得自行选用例外路径，历史授权也不构成常备许可（`ADR-0011` / `ADR-0012`）。

| 操作 | 默认路径（无条件可用） | 需显式人工授权的例外 | 机验码 |
| --- | --- | --- | --- |
| 新建 | copy `_template.md`，`Status: Proposed` → 由人/k3dit 判 `Accepted` | — | `ADR_SECTIONS_MISSING`, `ADR_NUMBER_COLLISION`, `ADR_FRONTMATTER_MISSING` |
| 改正文（已 `Accepted`） | 新开一条：`Supersedes: ADR-NNNN` + 旧文 `Status: Superseded by ADR-NNNN`；非冲突增补用 `Amended by ADR-NNNN` | **就地修订（in-place revision）**：流程尚未跑通时其 `Accepted` 本就是过早的，允许直接替换决策正文，免得一次性 supersession 把 ADR 集撑成废料堆 | 同上 + `ADR_SECTION_ORDER` |
| 删除 / 改名 / 复用编号 | 一律不允许；**Numbers are never reused** | **物理删除**（含改名腾号） | `ADR_FILENAME_MISMATCH` |

`Note:` 字段（默认 `-`）只装"这条记录本身是怎么来的"，不装决策正文；`Deciders:` 只记席位。**只有一个 `Note:` 字段**：每次操作的陈述段用 ①②③ 编号续写，不并列多行 `Note:`。痕迹格式：

```
Note: ① <操作：就地修订 / 物理删除授权> YYYY-MM-DD，经 <授权席位> 本轮显式授权，依 `docs/adr/AUTHORING.md`；过闸口径 = real lens | manual fallback（<可复跑证据，如 `[PEER-MANUAL] … no live lens`>）。
      ② <下一次操作> YYYY-MM-DD，经 <授权席位> 本轮显式授权，依 `docs/adr/AUTHORING.md`；过闸口径同上。
```

**授权落地 = `Note:` 必须填**：凡动用"例外"列（就地修订 / 物理删除 / 改名），该文件 `Note:` 不得停留在 `-`。缺痕＝按静默重写处理（`ADR-0012`），无论口头说过几次"我授权"。历史授权不续期：换一次操作就在同一 `Note:` 内追加编号段（① ② ③ …），旧段保留，别擦。
  填法照抄上面那个格式块，末尾必带**可复跑证据**（例：`实测 [PEER-MANUAL] action 'k3dit.actions.audit' has no live lens`），只写"已授权"不算过。
  本条目前**只有人读约束、无机验**（`check` 不看 `Note:` 内容）；机验候选登记在 `docs/tasks/2026-09-02-M7-feat-check_gate_by_doc_status.md`。

就地修订另加两条：③ 被作废的旧句、授权与过闸痕迹写进 `Note:`（正文只留现行决策，不写「修正（date）/原稿/现稿」层）；既有 `ADR-NNNN §x` 指针靠**章节号不重排**仍可解析；④ 不为它扩 `Status` 枚举（`.schema.json` ⇒ `ADR_FRONTMATTER_MISSING`）。流程真跑通后回到 append-only，决策仍成立就用自己的 ADR 正式收编。

- **Section numbers must ascend** in document order (`## 1` → `## 2` → `### 2.1` → `### 2.1.1` …). This one is machine-gated: `k3dge check` fails it with `ADR_SECTION_ORDER`, because appending a decision out of order (or reusing a number) is exactly how the prose gets silently rewritten.
- A durable design change = its own ADR, judged by k3dit/human — the same seat must not both write and ratify (ADR-0006). An agent editing an ADR without a human/k3dit pass is **not** a decision record yet.
- **本文件是这些特权的唯一投递点**：`README.md` 只写默认路径与指针，不复述例外；两者冲突以本文件为准——特权越少被复述，越不容易被顺手用。

Structure gate is `.schema.json` (`k3dge check`).
