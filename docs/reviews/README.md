# Reviews — audit archive

Point-in-time reports. Append-only.

- **Address**: `k3dge doc list --type reviews`.
- **Write**: read `AUTHORING.md`.
- **Horizon**: top-level `*.md` is the current milestone. `k3dge milestone seal <id>` moves this-milestone reports to `archive/<id>/` and rewrites leftover hrefs in `LEFTOVERS.md`.
- **Before a new audit**: read `LEFTOVERS.md`. Do not reopen those IDs.
