---
Status: Accepted
# Append-only after Accepted. Revise via `Amended by` / `Superseded by` below — do
# NOT rewrite this decision's prose in place, and never reuse a number (see README).
Supersedes: -
Amended-by: -
Landed-by: src/k3dge/engine/doc_catalog.py
Date: 2026-08-30
Deciders: Core Maintainer
Note: ① 就地修订（protocols/ 描述对齐 ADR-0025 合并审计模块，撤销独立 quality peer/fallback）2026-09-10，经 Core Maintainer 本轮显式授权，依 `docs/adr/AUTHORING.md`；过闸口径 = manual fallback（实测 `command -v k3dit`/`k3dge` 无输出，no live lens）。
      ② 正交收尾（catalog 排除 `archive/` 与 ADR-0023 §2.2 互指）2026-09-10，经 Core Maintainer 本轮显式授权，依 `docs/adr/AUTHORING.md`；过闸口径同上。
      ③ 人读化改写（按 AUTHORING「人读优先」：决策先行、一行一点、长条拆子项；不变量与编号不变）2026-09-10，经 Core Maintainer 本轮显式授权，依 `docs/adr/AUTHORING.md`。
      ④ **合并原 ADR「docs 判据与投影的语义分工」入本条**（物理删旧文件，git 历史留档）2026-09-12，经 Core Maintainer 本轮显式授权，依 `docs/adr/AUTHORING.md`：docs 判据/投影与托管布局同属"docs 治理"一决策；被并者 0002 删除，全仓指针改指本条（**保留本条 §2.3/§2.4/§2.6/§2.8 节号**）。过闸口径 = manual fallback。
      ⑤ **合并原 ADR「No load-proof」入本条 §2.11**（物理删旧文件）2026-09-12，经 Core Maintainer 本轮显式授权：同属 docs 寻址/装载决策；被并者 0019 删除，指针改指本条。过闸口径 = manual fallback。
      ⑥ **合并原 ADR「tasks 与 backlog 合并」入本条 §2.12**（物理删旧文件）2026-09-12，经 Core Maintainer 本轮显式授权：tasks 目录属托管文档布局；被并者 0003 删除，指针改指本条。过闸口径 = manual fallback。
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
11. **不设装载证明（原独立 ADR，合并入本条）**：不恢复 protocol resolve/attend/challenge/exclusive IO/`protocols.toml`（`engine.protocol` 只留 `write_incident`）；payload/routing 按 §2.3，peer fallback 按 §2.8。硬底＝`scripts/pre-commit` + CI `k3dge check`；`k3dge-commit:` token 只是 hook 细节（缺＝WARN），不升级成 proof-of-read。跳过 Authoring 不是机器事件（代价＝结构闸红 + k3dit 文本质量 findings）。Reopen：宿主提供 agent 看不见的 pre-action 强制（policy gateway）。
12. **tasks 单目录 + Status 成熟度（原独立 ADR，合并入本条）**：`docs/backlog/` 与 `docs/tasks/` 合并为单一 `docs/tasks/`；成熟度用条目 `Status`：`idea → deferred → in-progress → done`；backlog 纪律（自包含摘要、开工扫盘、模糊召回）并入 `docs/tasks/AUTHORING.md` 与 `k3dge task list --json`；memo / branches 保持独立。

## 3. 产生后果 (Consequences)

- **Up**: one hop from path to rules; structure is machine-checkable; list/where keeps bodies out of context.
- **Down**: every type directory must keep `AUTHORING.md`; types that add `.schema.json` must keep existing files legal or they go red.
  - Dotfiles are easy to miss in a file listing — intended for the gate file only.
- **Reopen when**: a harness can inject Authoring at the IO boundary without owning the agent runtime; or catalog tokens are proven too thin for recall.
- **判据/投影**：职责分明，同类混淆有 ADR 可查；代价＝两处域表手工同步（接受，换取判据文件不被生成逻辑覆盖）；升级条件＝第 3 对语义相近产物出现或第 2 次同类事故 → 再考虑 `manifest` 的 docs_registry 创建期拦截。
