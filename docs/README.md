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
- Write/find/schema rules are **not duplicated here** — the single source is `AGENTS.md` (§Docs) and `docs/<type>/AUTHORING.md`. This file only carries the directory table below.
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
