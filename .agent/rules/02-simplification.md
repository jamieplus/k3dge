# Rule 02: Simplification Methodology

> Protocol slice for tools that look under `.agent/rules/` (ADR 0012).
> Live agent protocol is repo-root `AGENTS.md`. If this file disagrees, `AGENTS.md` wins; fix this file in the same task.
> This file is the procedure (not duplicated in AGENTS.md). AGENTS.md §12 points here when simplification is requested.

Evidence-backed process for simplification requests (dead code / over-built logic /
duplicated state). This is a **procedural discipline**, not a gate — it runs when
simplification IS requested, complementing `k3dge check` (which guards drift, not quality).

## Strong candidates (cost > value, with evidence)

- A function/param/config key/file has NO production consumer (only tests or docs reference it).
- Two representations mirror the same fact (e.g. two caches holding the same series).
- A branch/switch every implementation must support but no caller uses.
- A module exists only for test/demo/doc and adds dependency overhead.
- Speculative generality with no product owner.
- Hand-rolled code reimplements what stdlib/an existing dep already does, and the
  swap deletes impl + dedicated tests.

## Prove or reject each candidate

1. Classify consumers first — production (`src/**`, scripts/, CI) vs non-production
   (tests/docs/memo) vs ambiguous (archive, examples).
2. Search the exact symbol / config key / call form; then READ the call sites.
   Search is not a substitute for understanding public interfaces.
3. Reject when: a production caller exists (that's a feature decision); the API is
   protected by an invariant or a hard-won lesson in `docs/adr/` or `docs/branches/`;
   removal forces churn without shrinking public surface; or it's tiny — use an
   inline TODO instead.

## Archive, don't delete

Superseded files move to an archive location with a header note, never silently
deleted. When you can't tell "unfinished" from "orphan", don't touch it — flag it
for the user (per AGENTS.md §8 Paired-Artifact Discipline).
