"""Scaffold ↔ repo file pairs for the self-host TEMPLATE_DRIFT gate.

Engine owns this registry so it does not import k3dge.templates (ADR-0014).
Tests and any templates-side consumer import from here.

Not in PAIRS (intentional, do not "complete" the list):
- architecture.md.template — downstream generic placeholder; never byte-compare
  against this repo's four-domain docs/architecture/overview.md (G-04 / P4-05).
- reviews-readme.md — downstream empty index; this repo's docs/reviews/README.md
  is the type front door (same split as architecture).
- reviews/LEFTOVERS.md — downstream empty table; this repo's leftovers are k3dge-specific.
- mcp-bridge.md.template / gitignore.template — downstream-only init files.
- architecture-style splits only; docs/guides/downstream.md is paired (upgrade protocol).
- runtime state and empty skeletons — .agent/milestone, logs/ (P4-08).
"""

from __future__ import annotations

# (asset_path relative to src/k3dge/templates/assets, repo_relative_path)
PAIRS: list[tuple[str, str]] = [
    ("gate.py", "scripts/gate.py"),
    ("gate.sh", "scripts/gate.sh"),
    ("gate.ps1", "scripts/gate.ps1"),
    ("init.sh", "scripts/init.sh"),
    ("init.ps1", "scripts/init.ps1"),
    ("k3dge-init-wrapper.sh", "k3dge-init.sh"),
    ("k3dge-init-wrapper.ps1", "k3dge-init.ps1"),
    ("generate-docs.sh", "scripts/generate-docs.sh"),
    ("generate-docs.ps1", "scripts/generate-docs.ps1"),
    ("agents.md", "AGENTS.md"),
    ("agent-readme.md", ".agent/README.md"),
    ("rules/00-core-discipline.md", ".agent/rules/00-core-discipline.md"),
    ("rules/01-docs-structure.md", ".agent/rules/01-docs-structure.md"),
    ("rules/02-simplification.md", ".agent/rules/02-simplification.md"),
    ("rules/03-self-contained.md", ".agent/rules/03-self-contained.md"),
    ("rules/04-milestone.md", ".agent/rules/04-milestone.md"),
    ("rules/05-branches.md", ".agent/rules/05-branches.md"),
    ("rules/06-memo.md", ".agent/rules/06-memo.md"),
    ("rules/07-audit.md", ".agent/rules/07-audit.md"),
    ("rules/09-absorption.md", ".agent/rules/09-absorption.md"),
    ("docs.toml.template", ".agent/docs.toml"),
    ("pipeline.toml.template", ".agent/pipeline.toml"),
    ("spec.md.template", "docs/specs/_template/spec.md"),
    ("tasks-readme.md", "docs/tasks/README.md"),
    ("tasks/_template.md", "docs/tasks/_template.md"),
    ("memo/_template.md", "docs/memo/_template.md"),
    ("branches/_template.md", "docs/branches/_template.md"),
    ("adr/_template.md", "docs/adr/_template.md"),
    ("adr/AUTHORING.md", "docs/adr/AUTHORING.md"),
    ("adr/.schema.json", "docs/adr/.schema.json"),
    ("tasks/AUTHORING.md", "docs/tasks/AUTHORING.md"),
    ("memo/AUTHORING.md", "docs/memo/AUTHORING.md"),
    ("branches/AUTHORING.md", "docs/branches/AUTHORING.md"),
    ("incidents/AUTHORING.md", "docs/incidents/AUTHORING.md"),
    ("tasks/.schema.json", "docs/tasks/.schema.json"),
    ("memo/.schema.json", "docs/memo/.schema.json"),
    ("branches/.schema.json", "docs/branches/.schema.json"),
    ("incidents/.schema.json", "docs/incidents/.schema.json"),
    ("pre-commit.yaml.template", ".pre-commit-config.yaml"),
    ("branches-readme.md", "docs/branches/README.md"),
    ("memo-readme.md", "docs/memo/README.md"),
    ("downstream.md", "docs/guides/downstream.md"),
    ("protocols/audit_default.md", "docs/protocols/audit_default.md"),
    ("protocols/verify_default.md", "docs/protocols/verify_default.md"),
]
