---
name: k3dge-audit
description: >-
  Run the independent k3dge 5-pass / 8-dimension code audit protocol.
  Use when: 审计, 5-Pass, 8维审计, /k3dge-audit, review the repo with isolated lenses.
---

# k3dge-audit

You are running the **audit harness**, not `k3dge check`. Do not invent lenses. Do not put findings only in chat.

## Before anything

1. Read sibling repo `k3dit` (`../k3dit/docs/guides/protocol.md`) — source of truth for passes.
2. Read `docs/reviews/SUMMARY.md` and `docs/architecture/overview.md` §5.1. Do not re-open 有意留.
3. One pass at a time. Never mix Pass 1–5 in a single reasoning sweep.

## Output

Write `docs/reviews/YYYY-MM-DD-<scope>.md` with the 9-column table from PROTOCOL.md.

Disposition is exactly one of: 已修 / 转 `docs/tasks/` / 有意留 (reason + when to reopen).

Unfixed findings must become `docs/tasks/` entries in the same turn.

Optional: `k3dit check-report <that-file>` (`pip install -e ../k3dit`).

## Facts vs judgment

Use `k3dge check` / spec files / `.agent/manifest.json` as **facts**. The protocol is **judgment**. Never add audit logic to `src/k3dge`.
