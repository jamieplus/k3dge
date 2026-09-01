# Reviews — audit archive

Point-in-time reports. Append-only.

- **Address**: `k3dge doc list --type reviews` (living, current milestone). Do not grep this directory. `k3dge doc list --type reviews --include-archive` for sealed reports.
- **Write**: read [`AUTHORING.md`](AUTHORING.md). 12-column header is k3dit (`check-report`), not k3dge.
- **Horizon**: top-level `*.md` is the current milestone. `k3dge milestone seal <id>` moves this-milestone reports to `archive/<id>/` and rewrites leftover hrefs in [`LEFTOVERS.md`](LEFTOVERS.md). Older reports without a milestone token live in `archive/untagged/`.
- **Before a new audit**: read [`LEFTOVERS.md`](LEFTOVERS.md). Do not reopen those IDs.
