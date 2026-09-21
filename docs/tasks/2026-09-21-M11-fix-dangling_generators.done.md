---
status: done
milestone: M11
priority: P2
date: 2026-09-21
---

# 悬空生成路径归位：生成物新鲜度闸 + README layout 并入 sync + 删 changelog 死簇 + 架构 seal 收口

- **可检索摘要**: 2026-09-21 盘点"自动更新/生成文档"时发现 5 条路径**生成器在、却没有切入时间点也没有闸**：`docs/generated/symbol-index.json`、`.mcp.json`、`docs/generated/{api,domains}.md`、`README.md` 的 layout 块（唯一调用方是 `generate-docs.sh`）、`changelog._append_to_unreleased`（零生产调用方）。另有架构文档只在收摊清单里挂一句 advisory，跨里程碑静默漂移。

## 证据（盘点，均可复跑）

```
grep -n "symbol-index\|symbol_index\|mcp.json\|k3dge:layout\|overview.md\|encyclopedia\|uncovered" \
     src/k3dge/engine/{evaluator,pure_refs,gate_facts,pairs}.py scripts/pre-commit
  ⇒ 只 DOC_INDEX_STALE / TEMPLATE_DRIFT / VERSION_MISMATCH / CONTRACT_* 有闸；上列五件零命中

render_readme_layout 的调用方：scripts/generate-docs.sh:59（+ templates 资产镜像）——`k3dge sync` 有意不碰 README
_append_to_unreleased 的调用方：仅 tests/unit/engine/test_changelog_deep.py（生产零调用）
seal closure §3 原文：`- [ ] docs/architecture/overview.md 对齐到已封板的现实`（无事实、无区间，跳过无痕）
```

## 方案（各归其位，不新造机制）

1. `SYMBOL_INDEX_STALE`：`evaluator` 重建符号索引与盘上比（缺文件不报，同 `DOC_INDEX_STALE` 口径）；修法 `k3dge index`。
2. `DOCS_GENERATED_STALE`：新增 `engine/generated_docs.render_manual_docs_content`（**纯渲染**，一处构造）；sync 写盘、evaluator 比对（engine ↛ sync，故渲染住 engine）。
3. `MCP_JSON_PEER_MISSING`：`.mcp.json` 的 `mcpServers` 必须含 `k3dge` 自身 + 声明 `enabled` 且**探得到 sibling** 的 peer；探针 `engine/mcp_json.probe_peer_mcp`（从 `cli/mcp_peers` 迁入，写侧与闸共用一份，避免第二判据）。
4. README layout 归 `k3dge sync`（`sync_manual_docs` 顺带刷自动块）；`generate-docs.sh` 与模板资产同步去掉该调用（PAIRS 字节锁）。
5. 删 `changelog._append_to_unreleased` 一族 + 其专属测试（`rules/02`：零消费者；双写来源）。
6. 架构文档：seal 相位 3 算出事实（最近边界 tag..HEAD 内 `src/`/`docs/specs/` 变过而 `overview.md` 未动）写进收摊清单与 seal 输出（**advisory，不阻断**）；`AGENTS.md` §12 补口径 + 模板资产镜像。

## 边界与拆分

- 事实归属：投影内容渲染归 `engine`（manifest/接口派生物）；写盘归 `sync`；比对闸归 `evaluator`；`.mcp.json` 探测归 `engine/mcp_json`（读口原有归属）。
- 不阻断人写的散文：架构新鲜度只出**事实**，写得好坏归人/k3dit（`AGENTS.md` §12 既有口径）。
- 不动：`docs-index.json`（已有闸）、审计线/封版的 `--no-verify`（机械件，PRE-01 已记）。

## 结案

- 落地：`engine/generated_docs.py`（新）、`engine/mcp_json.py`（+`probe_peer_mcp`）、`engine/evaluator.py`（+`_check_generated_projections` / `_check_mcp_json`）、`engine/gate_facts.py`（三个码：`SYMBOL_INDEX_STALE` / `DOCS_GENERATED_STALE` / `MCP_JSON_PEER_MISSING`）、`engine/seal_flow.py`（`_boundary_tag_before` / `_architecture_staleness` + 收摊清单与 seal 输出）、`sync/generator.py`（README layout 并入 `sync_manual_docs`；渲染函数迁出）、`cli/mcp_peers.py`（去重复探针）、`engine/changelog.py`（删死簇）。
- 新测试：`tests/unit/engine/test_generated_projections.py`（10 例：三闸的正/负/缺文件各面）、`tests/unit/engine/test_architecture_freshness.py`（5 例：边界 tag 选取 + 未更新/已更新/无改动/首里程碑）。引擎 spec 加 TC-ENG-21..24。
- 闸自证：本票实施中 `DOCS_GENERATED_STALE` 与 `SYMBOL_INDEX_STALE` 各真红过一次（改完公共符号没 sync/index），`gate_facts` 的占位符守卫也抓到我写的 `{api,domains}` 字面。
- 验证：`k3dge check --with-tests` 绿（cli/engine/sync/templates）；`pytest -q` 701 passed, 2 skipped。
- 有意留：架构文档**不设闸**（只出事实，不阻断散文）；`_append_to_unreleased` 的"首个里程碑回落"路径随之消失（`seal` 仍有 `consume_unreleased() or 通用行` 兜底）。
