"""Scaffold generator, invoked by `k3dge-init.sh`."""

from __future__ import annotations

import json
import stat
from importlib import resources
from pathlib import Path
from typing import Optional, Sequence


def _asset(*parts: str) -> str:
    node = resources.files(__package__) / "assets"
    for part in parts:
        node = node / part
    return node.read_text(encoding="utf-8")


AGENTS_TEMPLATE = _asset("agents.md")

SPEC_TEMPLATE = _asset("spec.md.template")

GATE_SH_TEMPLATE = _asset("gate.sh")

GATE_PY_TEMPLATE = _asset("gate.py")

GATE_PS1_TEMPLATE = _asset("gate.ps1")

K3DGE_INIT_SH_TEMPLATE = _asset("init.sh")

K3DGE_INIT_WRAPPER = _asset("k3dge-init-wrapper.sh")

K3DGE_INIT_PS1_WRAPPER = _asset("k3dge-init-wrapper.ps1")

INIT_PS1_TEMPLATE = _asset("init.ps1")

DOCS_TOML_TEMPLATE = _asset("docs.toml.template")

GENERATE_DOCS_SH_TEMPLATE = _asset("generate-docs.sh")

GENERATE_DOCS_PS1_TEMPLATE = _asset("generate-docs.ps1")

PRE_COMMIT_TEMPLATE = _asset("pre-commit.yaml.template")

ARCHITECTURE_TEMPLATE = _asset("architecture.md.template")

REVIEWS_README_TEMPLATE = _asset("reviews-readme.md")

TASKS_README_TEMPLATE = _asset("tasks-readme.md")

BRANCHES_README_TEMPLATE = _asset("branches-readme.md")

MEMO_README_TEMPLATE = _asset("memo-readme.md")

RULE_ASSETS = (
    "00-core-discipline.md",
    "01-docs-structure.md",
    "02-simplification.md",
    "03-self-contained.md",
)

DEFAULT_MANIFEST = {
    "name": "project",
    "version": "0.1.0",
    "package_root": "src",
    "domains": {},
    "ignore": [],
}

def _write_if_missing(path: Path, content: str, executable: bool = False) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return True


def scaffold(target: Path) -> None:
    import datetime

    target.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()

    _write_if_missing(target / "AGENTS.md", AGENTS_TEMPLATE)
    _write_if_missing(
        target / ".agent" / "manifest.json",
        json.dumps(DEFAULT_MANIFEST, indent=2) + "\n",
    )
    for name in RULE_ASSETS:
        _write_if_missing(
            target / ".agent" / "rules" / name,
            _asset("rules", name),
        )
    _write_if_missing(target / ".agent" / "README.md", _asset("agent-readme.md"))
    _write_if_missing(
        target / "docs" / "specs" / "_template" / "spec.md",
        SPEC_TEMPLATE.format(domain="<domain>", date=today),
    )
    _write_if_missing(target / ".pre-commit-config.yaml", PRE_COMMIT_TEMPLATE)
    _write_if_missing(target / "scripts" / "gate.sh", GATE_SH_TEMPLATE, executable=True)
    _write_if_missing(target / "scripts" / "gate.py", GATE_PY_TEMPLATE, executable=True)
    _write_if_missing(target / "scripts" / "gate.ps1", GATE_PS1_TEMPLATE)
    _write_if_missing(target / "scripts" / "init.sh", K3DGE_INIT_SH_TEMPLATE, executable=True)
    _write_if_missing(target / "scripts" / "init.ps1", INIT_PS1_TEMPLATE)
    _write_if_missing(target / "k3dge-init.sh", K3DGE_INIT_WRAPPER, executable=True)
    _write_if_missing(target / "k3dge-init.ps1", K3DGE_INIT_PS1_WRAPPER)

    (target / "docs" / "adr").mkdir(parents=True, exist_ok=True)
    (target / "docs" / "tasks").mkdir(parents=True, exist_ok=True)
    _write_if_missing(target / "docs" / "tasks" / "README.md", TASKS_README_TEMPLATE)
    (target / "docs" / "guides").mkdir(parents=True, exist_ok=True)
    (target / "docs" / "reference").mkdir(parents=True, exist_ok=True)
    (target / "docs" / "branches").mkdir(parents=True, exist_ok=True)
    _write_if_missing(target / "docs" / "branches" / "README.md", BRANCHES_README_TEMPLATE)
    (target / "logs").mkdir(parents=True, exist_ok=True)
    (target / "docs" / "log").mkdir(parents=True, exist_ok=True)
    _write_if_missing(target / "docs" / "log" / "README.md", "# Log — Harness 操作日志\n\n`k3dge check / sync` 的机器日志，append-only。\n")
    (target / "docs" / "reviews").mkdir(parents=True, exist_ok=True)
    _write_if_missing(target / "docs" / "reviews" / "README.md", REVIEWS_README_TEMPLATE)
    (target / "docs" / "memo").mkdir(parents=True, exist_ok=True)
    (target / "docs" / "memo" / "archive").mkdir(parents=True, exist_ok=True)
    _write_if_missing(target / "docs" / "memo" / "README.md", MEMO_README_TEMPLATE)
    _write_if_missing(target / "docs" / "architecture" / "overview.md", ARCHITECTURE_TEMPLATE)
    _write_if_missing(target / ".agent" / "docs.toml", DOCS_TOML_TEMPLATE)
    _write_if_missing(target / "scripts" / "generate-docs.sh", GENERATE_DOCS_SH_TEMPLATE, executable=True)
    _write_if_missing(target / "scripts" / "generate-docs.ps1", GENERATE_DOCS_PS1_TEMPLATE)


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(prog="k3dge.templates.scaffold")
    parser.add_argument("target", nargs="?", default=".", help="target project root")
    args = parser.parse_args(argv)
    scaffold(Path(args.target).resolve())
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
