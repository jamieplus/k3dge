"""Scaffold ↔ repo file pairs for the self-host TEMPLATE_DRIFT gate.

Engine owns this registry so it does not import k3dge.templates (ADR 0018).
Tests and any templates-side consumer import from here.

Not in PAIRS (intentional, do not "complete" the list):
- architecture.md.template — downstream generic placeholder; never byte-compare
  against this repo's four-domain docs/architecture/overview.md (G-04 / P4-05).
- reviews-readme.md — downstream empty index; this repo's docs/reviews/README.md
  is the living audit catalog (same split as architecture).
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
    ("docs.toml.template", ".agent/docs.toml"),
    ("spec.md.template", "docs/specs/_template/spec.md"),
    ("tasks-readme.md", "docs/tasks/README.md"),
    ("pre-commit.yaml.template", ".pre-commit-config.yaml"),
    ("branches-readme.md", "docs/branches/README.md"),
    ("memo-readme.md", "docs/memo/README.md"),
    ("downstream.md", "docs/guides/downstream.md"),
]
