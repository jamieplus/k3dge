# Memo: `sync` 的 `docs_updated` 标志不含索引写盘 —— 打印/MCP 说"无改动"，同一快照其实改了文件

- **类型**: 模糊概念（一处"报告面 ≠ 事实"的对不齐；已可复跑，未观察到实际危害）
- **念头**: `k3dge sync` 在"只重生 `docs/generated/docs-index.json`"这一种情形下会打印 `Contracts already up to date.`，MCP 同源地把 `up_to_date` 报成 `true`——但那一轮确实写了盘。
- **触发场景**: 2026-09-21 往 `docs/memo/` 加了一份文档，`k3dge check` 报 `DOC_INDEX_STALE`，`k3dge sync` 说"already up to date"，随后 `git diff --stat` 显示 `docs/generated/docs-index.json` 已变。
- **Date**: 2026-09-21

## 事实（可复跑）

```
$ git diff --stat docs/generated/docs-index.json   # sync 之前：git 层面干净（但内容已 stale，check 刚报过 DOC_INDEX_STALE）
$ k3dge sync
[SYNC] Contracts already up to date.               # ← 说"无改动"
$ git diff --stat docs/generated/docs-index.json
 docs/generated/docs-index.json | 8 ++++++++        # ← 实际写了盘（新增 memo 的卡片）

# 同一会话内复现第二次（再加一份 memo 后）：同样打印 already up to date，索引再 +8 行 → 16
```

机制（两条标志、三种写盘）：

| 位置 | 行为 |
| --- | --- |
| `sync/generator.py:235` | `sync_manual_docs`：`ctx["docs_updated"] = bool(render_manual_docs(...))` —— 只反映 `api.md`/`domains.md` |
| `sync/generator.py:238-240` | `sync_docs_index`：`write_docs_index(...)`，**不置任何标志** |
| `cli/main.py:253-255` | `cmd_sync`：`if not changed and not docs_updated: print("Contracts already up to date.")` |
| `cli/mcp.py:203,210-211` | MCP `k3dge_sync`：`"docs_updated": bool(docs_updated)`、`"up_to_date": not changed and not docs_updated` |
| `cli/main.py:444-445` | `k3dge doc sync` 同源：`changed={changed} docs_updated={docs_updated}` |

⇒ `docs_updated` 的语义是"**manual docs 是否重生**"，而两个消费者的措辞（"already up to date" / `up_to_date`）表达的是"**这轮有没有写盘**"。`sync_docs_index` 落在这两个语义之间。

## 危害评估（为什么记下来而不是立刻修）

- **消费面**：`up_to_date` 是给 agent 的机械判定（MCP JSON），不是纯装饰——consumer 若据此认为"sync 无事发生、无需提交"，`docs-index.json` 的改动会留在工作区未提交（下次 `check` 才由 `DOC_INDEX_STALE` 追回）。
- **未观察到实例**：目前只有“打印与实际不符”这一条事实；没有“因此漏提交 / 误判”的可复跑实例 ⇒ 按 `.agent/rules/12 §2` 不构成开工理由。
- **消费者排查（2026-09-21）**：`grep -rn "up_to_date" AGENTS.md docs .agent src/k3dge/templates` ⇒ 只有 `docs/specs/cli/spec.md:78`（签名）、`docs/guides/mcp-bridge.md:88` 与模板同款（“回写 spec 接口块与哈希”）。**没有任何地方教人用 `up_to_date` 做决定** ⇒ 到达环不存在，维持有意留（等实例）。
- **反面**：纯打印面（CLI 文案）误报的代价确实低；MCP 字段的代价低但非零。

## 修法选项（择一，勿混）

1. **标志改名（最小改动）**：`docs_updated` → 语义化（如 `manual_docs_updated`），MCP 的 `up_to_date` 改为"本轮是否有任何写盘"（新增 `wrote` 字段，保留旧字段不动 = §2.7「加字段可以」）。
2. **统一"写盘"计数**：`sync_all` 的返回值扩为"写盘集合"（域 + manual + index），两个消费者共用；缺点是把"投影类写盘"也报出来，噪音变大。
3. **只修文案**：`cmd_sync` 打印改为陈述事实（"spec 契约无变化；派生件已重生"）。不动 MCP 字段。缺点：MCP 那份对不齐仍在。

**已应用（2026-09-21，取选项 3）**：CLI 无变化分支改为 `[SYNC] No spec contract changes (derived docs/index are rewritten only when stale).`，日志同改；MCP `up_to_date`/`docs_updated` 字段未动（按下方 reopen 条件等实例）。落地票：`docs/tasks/2026-09-21-M11-fix-memo_review_landing.done.md`。

## 关联（指针）

- 判据：`ADR-0026` §2.2（投影语法：纯打印面出**陈述式事实**，不夸大成"无变化"）、§2.7（字段语义变更 ⇒ 走 ADR；加字段可以）。
- 现状机制：`src/k3dge/sync/generator.py:225-262`、`src/k3dge/cli/main.py:253-265,444-445`、`src/k3dge/cli/mcp.py:196-215`。
- 相邻（同一轮讨论产出的另一份）：`docs/memo/2026-09-21-hookization-surface-inventory.md`。

## 下一步

- Reopen 条件：出现「consumer 据 MCP `up_to_date=true` 判定无改动」的实例，或该字段被写进 agent 协议话术 ⇒ 按选项 1 修（增字段，不改既有字段语义）。
- 在此之前：`docs/reviews/LEFTOVERS.md` 的 `SYNC-01` 行即结论。
