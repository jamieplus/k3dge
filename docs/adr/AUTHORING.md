# Authoring

Copy `_template.md`. Soft rules (k3dit may judge text quality; k3dge does not):

- Context: constraints only — no chat log, no timeline, no "the user said".
- Decision: invariants and explicit non-goals.
- Consequences: upside, downside, reopen criterion.
- Wrong: "Twenty minutes later we decided…" / "the agent found…". Right: name the constraint and the choice.

Do not judge whether the decision is a *good* idea (k3lity, soft). k3dit may flag two Accepted Decision sections that directly negate each other.

Structure gate is `.schema.json` (`k3dge check`).
