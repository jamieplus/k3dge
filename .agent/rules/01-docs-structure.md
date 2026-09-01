# Rule 01: Docs Structure

> Protocol slice for tools that look under `.agent/rules/` (ADR-0010).
> Live protocol is repo-root `AGENTS.md`. If this file disagrees, `AGENTS.md` wins.

1. Never place files directly under `docs/` except `docs/README.md`.
2. Write `docs/<type>/…` → that type's `AUTHORING.md` and `_template.md`. Structure gate is `docs/<type>/.schema.json`.
3. Find docs with `k3dge doc list` / `k3dge doc where`. Body scan: `k3dge doc grep` (path only). Do not raw-grep `docs/`.
4. `DOCS_ROOT_DISALLOWED` is enforced by `k3dge check`.
