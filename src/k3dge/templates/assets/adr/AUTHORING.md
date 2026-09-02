# Authoring

Copy `_template.md`. Soft rules (k3dit may judge text quality; k3dge does not):

- Context: constraints only — no chat log, no timeline, no "the user said".
- Decision: invariants and explicit non-goals.
- Consequences: upside, downside, reopen criterion.
- Wrong: "Twenty minutes later we decided…" / "the agent found…". Right: name the constraint and the choice.

Do not judge whether the decision is a *good* idea (k3lity, soft). k3dit may flag two Accepted Decision sections that directly negate each other.

## Record lifecycle (from `README.md`; enforce where a machine can)

- **Append-only after `Status: Accepted`.** Do not rewrite an Accepted decision's prose in place. To change one: open a **new** ADR with `Supersedes: ADR-NNNN` and set the old file's `Status: Superseded by ADR-NNNN` (or `Amended by ADR-NNNN` for a non-conflicting addendum). **Numbers are never reused**; physical delete needs explicit human authorization.
- **Section numbers must ascend** in document order (`## 1` → `## 2` → `### 2.1` → `### 2.1.1` …). This one is machine-gated: `k3dge check` fails it with `ADR_SECTION_ORDER`, because appending a decision out of order (or reusing a number) is exactly how the prose gets silently rewritten.
- A durable design change = its own ADR, judged by k3dit/human — the same seat must not both write and ratify (ADR-0006). An agent editing an ADR without a human/k3dit pass is **not** a decision record yet.

Structure gate is `.schema.json` (`k3dge check`).
