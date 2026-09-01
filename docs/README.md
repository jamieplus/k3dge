# Docs — managed document root

Every `docs/<type>/` is one document kind. Type rules live **in that directory**, not here.

| File | Role | Visible |
| --- | --- | --- |
| `README.md` | What this directory is, how to address it | yes |
| `AUTHORING.md` | Soft rules (how to write). Agents must read this before writing | yes |
| `.schema.json` | Structure gate. Only `k3dge check` reads it | hidden |
| `_template.md` | Skeleton. Leading underscore = not a content document | yes |

`README.md` and `AUTHORING.md` are required (missing `AUTHORING.md` fails the doc-gate hook). `_template.md` and `.schema.json` are optional; no schema file means no structure gate for that type.

- Only this file may sit directly under `docs/` (`DOCS_ROOT_DISALLOWED`).
- **Write** a managed file: open `docs/<type>/AUTHORING.md`; copy `_template.md` if present. Formula is in `AGENTS.md`.
- **Find** a file: default `k3dge doc list` / `k3dge doc where <id>`. Body scan: `k3dge doc grep` (path only). Do not raw-grep `docs/`.
- k3dge checks `docs/<type>/.schema.json` (structure). Text quality is k3dit. Whether an agreement is a good idea is k3lity (soft).
- `specs/` and `generated/` are k3dge-managed; their README is orientation only.

## Subdirectory Index

| Directory | Role |
| --- | --- |
| `adr/` | Architecture Decision Records |
| `architecture/` | System picture (`overview.md`) |
| `branches/` | Falsified in-task attempts |
| `generated/` | Sync output (do not edit) |
| `guides/` | Human how-to |
| `incidents/` | Postmortems |
| `memo/` | Spark inbox |
| `protocols/` | Peer fallback texts only |
| `reviews/` | Audit reports |
| `specs/` | Domain contracts |
| `tasks/` | Work items |
