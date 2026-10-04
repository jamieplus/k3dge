# Rule 09 — External Pattern Absorption

> Protocol slice for tools that look under `.agent/rules/` (ADR-0010).
> Live agent protocol is repo-root `AGENTS.md`. If this file disagrees, `AGENTS.md` wins; fix this file in the same task.

Read when introducing external patterns, prompts, or architectures.

## 1. Four Invariants
1. **Clean-Room Only**: Only absorb models, state machines, and design concepts. ZERO direct code pasting.
2. **De-branding**: NEVER commit third-party logos, SVGs, proprietary tokens, or company trademarks.
3. **No Frankenstein**: Route absorbed patterns into roles already declared in `.agent/pipeline.toml` `[roles.*]`. Do not invent a new role in this rule, and do not name bind implementations here (`[roles.<role>] bind = "…"` is the only place an implementation is named). k3dge is the consistency gate, not a peer.
4. **Attribution**: Prompts/docs referencing permissive sources retain 1-line source attribution.

## 2. License Gate
- **MIT/Apache/BSD**: Allowed, clean-room re-implementation required.
- **GPL/AGPL**: Concept only, zero lines copied.
- **Proprietary**: Only general ergonomics, sanitize payloads.

## 3. Checklist（逐项勾选，不可合并为一条）
- [ ] 1. Abstract into state machine/formula.
- [ ] 2. Close source（与 §1 Clean-Room Only 同一约束，此处是执行项）。
- [ ] 3. Write native.
- [ ] 4. Check diff for trademark leaks.
- [ ] 5. `k3dge sync` + `k3dge check`.
