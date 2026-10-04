---
status: done
milestone: M11
priority: P2
date: 2026-09-21
---

# seal 相位 3 自动刷纯投影 + `k3dge where` 索引自愈

- **可检索摘要**: 上游只给 `docs/generated/*` 加了**闸**（陈旧就红、去跑 `k3dge sync`/`k3dge index`）——闸管"发现"，不管"及时"。派生件是确定性的，应当在**对的时机自动刷新**：封版那一刻（相位 3）刷一次纯投影；`k3dge where` 读到陈旧索引时自愈，别拿旧索引给出错的 `file:line`。

## 证据

```
seal 相位 3 原有行为：只 write_docs_index（docs-index 一件）；api.md/domains.md/符号索引/README 自动块不在其中
k3dge where 原行为：索引**缺失**才重建（search._load_index）⇒ 代码写完后没跑 k3dge index 就静默返回过期位置
```

## 方案

1. `seal_flow._refresh_projections(workspace)`：相位 3 在 `closure_note` 之前刷 `docs/generated/{api,domains}.md`、`docs-index.json`、`symbol-index.json`、README 自动块；返回**实际变化**的路径（落进随后的封版提交）。
2. **不跑整条 `sync`**：spec 接口块/契约哈希与 ADR reconcile 是**事实源写**，审计后动它们＝改审计看过的内容（ADR-0004 §2.1.9「审哪版封哪版」）。
3. 纯渲染归 engine：`render_readme_layout` + `_layout_block` + `_replace_between_all` + LAYOUT 常量迁入 `engine/generated_docs.py`（engine ↛ sync，`seal_flow` 依赖它）；`sync.generator` 反向 import。
4. `search._is_stale_cheaply`：`k3dge where` 遇「任一域 src 文件比索引新」即重建（廉价 mtime 启发式；权威判据仍是 `check` 的 `SYMBOL_INDEX_STALE`）。

## 边界与拆分

- 事实归属：纯渲染/刷新 = engine（manifest 派生物）；写盘时机 = seal 相位 3（投影）与 sync（含事实源写）；陈旧判定 = evaluator。
- 不动的：spec/ADR（事实源）、审计基线 B 的内容。
- 失败语义：刷新任一件失败 ⇒ 跳过该件（投影坏不拦收尾），但清单与输出会体现实际变化列表。

## 结案

- 落地：`engine/seal_flow.py`（`_refresh_projections` + `_closure_note` 先刷再写清单，输出 `派生件: …`）、`engine/generated_docs.py`（+`render_readme_layout`/`_layout_block`/`_replace_between_all`/LAYOUT 常量）、`sync/generator.py`（改从 engine 取、去自身副本）、`engine/search.py`（`_is_stale_cheaply` + `_load_index` 自愈）。
- 测试：`tests/unit/engine/test_projection_refresh.py`（6 例：陈旧 api.md 被刷回并上报、幂等、README 自动块、索引落盘、where 自愈、缺失即建）；`os.utime` 拨旧索引 mtime 防 CI 秒级粒度 flake。
- 实测：`_refresh_projections` 在本仓返回 `['docs/generated/symbol-index.json']`（本票改动引入新公共符号）；造陈旧 api.md 后调用即刷回；`k3dge where ConsistencyEngine` 在索引被删条目 + src 触新后仍解析成功。
- 验证：`k3dge check --with-tests` 绿（cli/engine/sync/templates）；`pytest -q` 714 passed, 2 skipped；引擎 spec 加 TC-ENG-26/27；`AGENTS.md` §12 口径补"相位 3 先刷纯投影"（资产镜像）。
- 判据链：闸（`SYMBOL_INDEX_STALE`/`DOCS_GENERATED_STALE`/`DOC_INDEX_STALE`）管**发现**，seal 相位 3 与 `k3dge where` 管**及时**；两者互补，不互相替代。
