---
Status: Accepted
Date: 2026-08-31
Deciders: Core Maintainer
---

# ADR-0019: No load-proof; routing formula in AGENTS.md, payload beside the files

## 1. 上下文 (Context)

A path-routed protocol loader (`k3dge protocol`, MCP `k3dge_protocol_*`, `get`/`edit`/`put`, challenge/ticket, `.agent/protocols.toml`) tried to prove the agent had loaded a type protocol before writing. Agents can bypass any artifact they can see. Pre-tool hard gates would require owning the agent runtime (ADR-0006). The middle layer added code without incrementally constraining a determined agent. Commit + CI already supply the hard floor.

## 2. 决策 (Decision)

1. **Do not restore** protocol resolve / attend / challenge / exclusive IO / `protocols.toml`. `engine.protocol` keeps `write_incident` only.
2. **Payload stays in the type directory** (`AUTHORING.md`, `_template.md`; structure gate `.schema.json`) as ADR-0018. **The routing formula stays in `AGENTS.md`** (write: `docs/<type>/` → `AUTHORING.md`; find: `doc list` / `where`; no grep of `docs/`). The formula is addressing, not load-proof.
3. **Peer fallbacks only:** `docs/protocols/audit_default.md` and `verify_default.md`, referenced from `.agent/pipeline.toml`, existence-checked as `PIPELINE_PROTOCOL_NOT_FOUND`.
4. **Hard floor remains server-side:** `scripts/pre-commit` + CI `k3dge check`. `k3dge-commit:` dictionary tokens are hook details (missing = WARN), not cryptography, and must not be upgraded into a proof-of-read protocol.
5. Skipping Authoring is not a machine event. Cost is structure-gate red + k3dit text-quality findings, not a captcha.

## 3. 产生后果 (Consequences)

- **Up**: no fake "must have attended" layer; agents that follow `AGENTS.md` still reach the local contract in one hop.
- **Down**: an agent that ignores `AGENTS.md` will not be proven to have read `AUTHORING.md`. Mitigated by `.schema.json` and external text-quality review.
- **Reopen when**: a host provides pre-action enforcement the agent cannot see (policy gateway). Until then: formula + template + structure gate + CI.
