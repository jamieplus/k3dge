---
Status: Accepted
Date: 2026-08-30
Deciders: Core Maintainer
---

# ADR-0018: Managed document layout (Authoring, template, Gate, catalog)

## 1. 上下文 (Context)

Agents writing `docs/` need a type-local contract they can copy, a structure gate that does not parse prose, and a catalog they can address without grepping bodies. A single long README that mixes navigation, ungated "L2" lists, templates, and full indexes pollutes context and does not tell the agent which file to open.

## 2. 决策 (Decision)

1. **Type = first path segment under `docs/`.** Nested paths (`docs/tasks/archive/…`) use that type's contract. New type = new directory; do not add type rules to `AGENTS.md` or `docs/protocols/`.
2. **Four pieces per type. Markdown that agents write uses English filenames** (no Chinese `.md` names). Pieces:
   - `README.md` — human orientation (what this directory is, Address/Write).
   - `AUTHORING.md` — short soft rules (template first, few don'ts, one counterexample). Visible English name; agents must read it when writing.
   - `_template.md` — copy-paste skeleton. Leading underscore marks "not a content document".
   - `.schema.json` — structure gate (hidden English name). k3dge reads this path only. Missing file → no structure gate for that type.
3. **Routing formula lives only in `AGENTS.md`:** write `docs/<type>/…` → open `AUTHORING.md` and copy `_template.md` if present. Find → default `k3dge doc list` / `k3dge doc where`. Body scan → `k3dge doc grep` (path or `path:line` only, never snippets). Do not raw-grep `docs/`.
4. **Catalog:** `k3dge sync` writes `docs/generated/docs-index.json` (path, type, id, title, status, short tokens) from filename + frontmatter + first heading. `k3dge check` fails on `DOC_INDEX_STALE`. `README.md`, `AUTHORING.md`, `_template.md`, and `archive/` are excluded from cards. There is no hand-maintained type index (`summary.md` / `SUMMARY.md`).
5. **Hide the machine gate, not the prose.** `.schema.json` is a dotfile so listing tools skip it; engine loads it via a hardcoded path. `AUTHORING.md` and templates stay visible. Do not use Chinese filenames for any of these.
6. **Pre-commit doc-gate** requires `docs/<type>/README.md` and `AUTHORING.md` when staged docs change. It does not parse `.schema.json` (that is `k3dge check`).
7. **Consumers:** k3dge = `.schema.json` + catalog. k3dit = `AUTHORING.md` + diff (text quality, ADR set coherence). k3lity = whether an agreement is a good idea (soft, never a commit gate).
8. **`docs/protocols/`** holds only `audit_default.md` / `verify_default.md` peer fallbacks.

## 3. 产生后果 (Consequences)

- **Up**: one hop from path to rules; structure is machine-checkable; list/where keeps bodies out of context.
- **Down**: every type directory must keep `AUTHORING.md`; types that add `.schema.json` must keep existing files legal or they go red. Dotfiles are easy to miss in a file listing — that is intended for the gate file only.
- **Reopen when**: a harness can inject Authoring at the IO boundary without owning the agent runtime; or catalog tokens are proven too thin for recall.
