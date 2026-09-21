---
Status: Accepted
Supersedes: -
Amended-by:
  - 🅰1 | Core Maintainer | 2026-09-21 | 新增第 13 项：文档面事实对账（域表/状态集两闸）+ 到达环（闸逻辑归 engine、hooks 与治理件随 init 下发）+ 引用自鉴定 + 排查面豁免
Landed-by: src/k3dge/engine/doc_catalog.py
Date: 2026-08-30
Deciders: Core Maintainer
Note: 修订痕迹见 git 历史。
---

# ADR-0018: Docs 治理（托管布局 + 判据/投影分工）

> **Related**: ADR-0018（协议装载废弃）、ADR-0023（archive 契约）

## 1. 上下文 (Context)

- Agents writing `docs/` need: a type-local contract to copy, a structure gate that does not parse prose, and a catalog addressable without grepping bodies.
- A single long README mixing navigation, ungated "L2" lists, templates, and full indexes pollutes context and does not tell the agent which file to open.

## 2. 决策 (Decision)

1. **Type = first path segment under `docs/`.** Nested paths (`docs/tasks/archive/…`) use that type's contract.
   - New type = new directory; do not add type rules to `AGENTS.md` or `docs/protocols/`.
2. **Four pieces per type; agent-written Markdown uses English filenames** (no Chinese `.md` names).
   - `README.md` — human orientation (what this directory is, Address/Write).
   - `AUTHORING.md` — short soft rules (template first, few don'ts, one counterexample); agents must read it when writing.
   - `_template.md` — copy-paste skeleton; leading underscore marks "not a content document".
   - `.schema.json` — structure gate (hidden English name); k3dge reads this path only; missing file → no gate for that type.
3. **Routing formula lives only in `AGENTS.md`.**
   - Write: `docs/<type>/…` → open `AUTHORING.md`, copy `_template.md` if present.
   - Find: `k3dge doc list` / `k3dge doc where`.
   - Body scan: `k3dge doc grep` (path or `path:line` only, never snippets); do not raw-grep `docs/`.
4. **Catalog:** `k3dge sync` writes `docs/generated/docs-index.json` (path, type, id, title, status, short tokens) from filename + frontmatter + first heading.
   - `k3dge check` fails on `DOC_INDEX_STALE`.
   - `README.md`, `AUTHORING.md`, `_template.md`, `archive/` are excluded from cards (`archive/` contract: ADR-0023 §2.2).
   - No hand-maintained type index (`summary.md` / `SUMMARY.md`).
5. **Hide the machine gate, not the prose.**
   - `.schema.json` is a dotfile so listing tools skip it; engine loads it via a hardcoded path.
   - `AUTHORING.md` and templates stay visible; no Chinese filenames for any of these.
6. **Pre-commit doc-gate** requires `docs/<type>/README.md` and `AUTHORING.md` when staged docs change.
   - It does not parse `.schema.json` (that is `k3dge check`).
7. **Consumers:** k3dge = `.schema.json` + catalog; k3dit = `AUTHORING.md` + diff (text quality, ADR set coherence); k3lity = whether an agreement is a good idea (soft, never a commit gate).
8. **`docs/protocols/`** holds the merged audit module's peer fallbacks (`audit_default.md` / `verify_default.md`, ADR-0025).
   - Quality is a window inside that module, not a separate peer; it has no independent fallback.
9. **判据 vs 投影（原独立 ADR，合并入本条）**：`docs/architecture/overview.md` = **一致性判据**（人写常驻，Agent 跨域改动必读；含依赖方向、数据流、全局不变量）；`docs/generated/*` = **投影**（`k3dge sync` 从 manifest 派生，可随时重建，**永不作为一致性判据**）。`docs/generated/` 即 reference 侧目录（消除旧 `docs/reference/` 同名混淆）。
10. **成对物纪律**（写入 `AGENTS.md`）：动任何"看似冗余"的成对物前，必查 `docs/adr/` 与全局不变量；无据则停下来询问，不得自作主张合并/删除。
11. **不设装载证明（原独立 ADR，合并入本条）**：不恢复 protocol resolve/attend/challenge/exclusive IO/`protocols.toml`（`engine.protocol` 只留 `write_incident`）；payload/routing 按 §2.3，peer fallback 按 §2.8。硬底＝`scripts/pre-commit` + CI `k3dge check`[^🅰1.1]；`k3dge-commit:` token 只是 hook 细节（缺＝WARN），不升级成 proof-of-read。跳过 Authoring 不是机器事件（代价＝结构闸红 + k3dit 文本质量 findings）。Reopen：宿主提供 agent 看不见的 pre-action 强制（policy gateway）。
12. **tasks 单目录 + Status 成熟度（原独立 ADR，合并入本条）**：`docs/backlog/` 与 `docs/tasks/` 合并为单一 `docs/tasks/`；成熟度用条目 `Status`：`idea → deferred → in-progress → done`；backlog 纪律（自包含摘要、开工扫盘、模糊召回）并入 `docs/tasks/AUTHORING.md` 与 `k3dge task list --json`；memo / branches 保持独立。

13. **文档面事实对账 + 到达环（🅰1）**：
    - **对账只针对事实列**：`docs/architecture/{overview,encyclopedia}.md` 的**域表**必须与 `.agent/manifest.json` 的
      `域集/src/spec/tests/depends_on` 逐列一致（`ARCH_TABLE_DRIFT`）；**状态清单**要么不写、要么写全
      `engine/nextstep.STATE_OPTIONS` 十二态 + `engine/state_machine.TaskState` 四值（`ARCH_STATE_DOC_DRIFT`）——
      半张表比不写更糟（旧文曾把 `ratchet_open` 的 priority 排在 `seal_ready` 之上）。散文（`Description`/`一句话`）不进闸。
    - **到达环**：三层闸（doc-gate / schema gate（含 `pure_refs` 引用面）/ 排查闸）的实现归 `engine/doc_gate`（可单测），
      `scripts/{pre-commit,commit-msg}` 与各 `docs/<type>/` 的 `README.md`/`AUTHORING.md` 随 `k3dge init` 下发。
    - **引用闸只解析非自限定引用**：`k3dge ADR-NNNN`（与 `where ADR-NNNN`）指向 k3dge 仓的决策，不在本仓解析面。
    - **排查面豁免 init 下发件**（`INIT_DELIVERED_DOCS`）：它们不是本仓作者的"新建决策"。
    - 代价与 Reopen 条件记账：`docs/reviews/LEFTOVERS.md` 的 `PRE-03`（自限定不再校验）/`PRE-05`（豁免清单手维护）。

## 3. 产生后果 (Consequences)

- **Up**: one hop from path to rules; structure is machine-checkable; list/where keeps bodies out of context.
- **Down**: every type directory must keep `AUTHORING.md`; types that add `.schema.json` must keep existing files legal or they go red.
  - Dotfiles are easy to miss in a file listing — intended for the gate file only.
- **Reopen when**: a harness can inject Authoring at the IO boundary without owning the agent runtime; or catalog tokens are proven too thin for recall.
- **判据/投影**：职责分明，同类混淆有 ADR 可查；代价＝两处域表手工同步（接受，换取判据文件不被生成逻辑覆盖）；升级条件＝第 3 对语义相近产物出现或第 2 次同类事故 → 再考虑 `manifest` 的 docs_registry 创建期拦截。

[^🅰1.1]: 修改（🅰1，2026-09-21，授权：Core Maintainer）：本项的"硬底"直到本条才**实测成立**——此前
    `scripts/pre-commit` / `commit-msg` 不在 `templates/assets` 里，`k3dge init` 后照下发的 `AGENTS.md`
    激活 `core.hooksPath scripts` 时，git 对**不存在的 hook 静默跳过**（实测 `git commit` rc=0，doc-gate /
    引用闸 / 排查闸一句没跑）；同时 5 个 docs 类型缺 README/AUTHORING ⇒ 钩子即使在，下游第一次提交也红。
    本条的四处口径（对账闸 / 到达环 / 引用自限定 / 排查豁免）+ 落地票见
    `docs/tasks/2026-09-21-M11-fix-hooks_reach_downstream.done.md`、`…-feat-arch_table_gate.done.md`、
    `…-docs-arch_flow_coverage.done.md`；机检在 `tests/unit/templates/test_hooks_reach_downstream.py`。
