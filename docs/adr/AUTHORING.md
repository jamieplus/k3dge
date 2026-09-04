# Authoring

Copy `_template.md`. Soft rules (k3dit may judge text quality; k3dge does not):

- Context: constraints only — no chat log, no timeline, no "the user said".
- Decision: invariants and explicit non-goals.
- Consequences: upside, downside, reopen criterion.
- Wrong: "Twenty minutes later we decided…" / "the agent found…". Right: name the constraint and the choice.

Do not judge whether the decision is a *good* idea (k3lity, soft). k3dit may flag two Accepted Decision sections that directly negate each other.

## Record lifecycle (from `README.md`; enforce where a machine can)

**没有任何 ADR 操作是无条件的。** 下表每行的"例外"列一旦动用，都必须由**人类在本轮显式授权**，并把痕迹写进该 ADR 的 `Note:` 字段——agent 不得自行选用例外路径，历史授权也不构成常备许可（`ADR-0011` / `ADR-0012`）。

| 操作 | 默认路径（无条件可用） | 需显式人工授权的例外 | 机验码 |
| --- | --- | --- | --- |
| 新建 | copy `_template.md`，`Status: Proposed` → 由人/k3dit 判 `Accepted` | — | `ADR_SECTIONS_MISSING`, `ADR_NUMBER_COLLISION`, `ADR_FRONTMATTER_MISSING` |
| 改正文（已 `Accepted`） | 新开一条：`Supersedes: ADR-NNNN` + 旧文 `Status: Superseded by ADR-NNNN`；非冲突增补用 `Amended by ADR-NNNN` | **就地修订（in-place revision）**：流程尚未跑通时其 `Accepted` 本就是过早的，允许直接替换决策正文，免得一次性 supersession 把 ADR 集撑成废料堆 | 同上 + `ADR_SECTION_ORDER` |
| 删除 / 改名 / 复用编号 | 一律不允许；**Numbers are never reused** | **物理删除**（含改名腾号） | `ADR_FILENAME_MISMATCH` |

`Note:` 字段（默认 `-`）只装"这条记录本身是怎么来的"，不装决策正文；`Deciders:` 只记席位。痕迹格式：

```
Note: <操作：就地修订 / 物理删除授权> YYYY-MM-DD，经 <授权席位> 本轮显式授权，依 `docs/adr/AUTHORING.md`；
      本轮过闸口径 = real lens | manual fallback（<可复跑证据，如 `[PEER-MANUAL] … no live lens`>）
```

**授权落地 = `Note:` 必须填**：凡动用"例外"列（就地修订 / 物理删除 / 改名），该文件 `Note:` 不得停留在 `-`。缺痕＝按静默重写处理（`ADR-0012`），无论口头说过几次"我授权"。历史授权不续期：换一次操作就重写一次 `Note:`，旧痕若仍相关就并列保留，别擦。
  填法照抄上面那个格式块，末尾必带**可复跑证据**（例：`实测 [PEER-MANUAL] action 'k3dit.actions.audit' has no live lens`），只写"已授权"不算过。
  本条目前**只有人读约束、无机验**（`check` 不看 `Note:` 内容）；机验候选登记在 `docs/tasks/2026-09-02-M7-feat-check_gate_by_doc_status.md`。

就地修订另加两条：③ 正文必须点名被作废的旧句，使既有 `ADR-NNNN` 指针读不到两层皮；④ 不为它扩 `Status` 枚举（`.schema.json` ⇒ `ADR_FRONTMATTER_MISSING`）。流程真跑通后回到 append-only，决策仍成立就用自己的 ADR 正式收编。

- **Section numbers must ascend** in document order (`## 1` → `## 2` → `### 2.1` → `### 2.1.1` …). This one is machine-gated: `k3dge check` fails it with `ADR_SECTION_ORDER`, because appending a decision out of order (or reusing a number) is exactly how the prose gets silently rewritten.
- A durable design change = its own ADR, judged by k3dit/human — the same seat must not both write and ratify (ADR-0006). An agent editing an ADR without a human/k3dit pass is **not** a decision record yet.
- **本文件是这些特权的唯一投递点**：`README.md` 只写默认路径与指针，不复述例外；两者冲突以本文件为准——特权越少被复述，越不容易被顺手用。

Structure gate is `.schema.json` (`k3dge check`).
