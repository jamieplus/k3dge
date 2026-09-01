# Rule 00: Core Discipline

> Protocol slice for tools that look under `.agent/rules/` (ADR-0010).
> Live agent protocol is repo-root `AGENTS.md`. If this file disagrees, `AGENTS.md` wins; fix this file in the same task.

Immutable, machine-gated invariants. These are enforced by `k3dge check`, not by reading.

1. Every code change under `src/<domain>/` that alters a public interface MUST update
   `docs/specs/<domain>/spec.md` via `k3dge sync` in the same task.
2. Every registered domain MUST have a spec with the three required sections:
   Domain Boundary, Public Interfaces, Verification Matrix.
3. No domain may be introduced under `package_root` without a manifest entry.
4. Contract hashes are derived from code, never hand-written.
