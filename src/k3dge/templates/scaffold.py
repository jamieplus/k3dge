"""Scaffold generator, invoked by `k3dge-init.sh`."""

from __future__ import annotations

import json
import re
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

PIPELINE_TOML_TEMPLATE = _asset("pipeline.toml.template")

GENERATE_DOCS_SH_TEMPLATE = _asset("generate-docs.sh")

GENERATE_DOCS_PS1_TEMPLATE = _asset("generate-docs.ps1")

PRE_COMMIT_TEMPLATE = _asset("pre-commit.yaml.template")

ARCHITECTURE_TEMPLATE = _asset("architecture.md.template")

REVIEWS_README_TEMPLATE = _asset("reviews-readme.md")

MCP_BRIDGE_TEMPLATE = _asset("mcp-bridge.md.template")

GITIGNORE_TEMPLATE = _asset("gitignore.template")

REVIEWS_SUMMARY_TEMPLATE = _asset("reviews-summary.md.template")

ADR_README_TEMPLATE = _asset("adr-readme.md.template")

DOWNSTREAM_GUIDE_TEMPLATE = _asset("downstream.md")

PROTOCOL_TEMPLATE = _asset("protocols/audit_default.md")

TASKS_README_TEMPLATE = _asset("tasks-readme.md")

BRANCHES_README_TEMPLATE = _asset("branches-readme.md")

MEMO_README_TEMPLATE = _asset("memo-readme.md")

RULE_ASSETS = (
    "00-core-discipline.md",
    "01-docs-structure.md",
    "02-simplification.md",
    "03-self-contained.md",
)

def _slug(raw: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_]+", "_", raw.strip()).strip("_").lower()
    if not s:
        s = "app"
    if s[0].isdigit():
        s = "p_" + s
    return s


def _first_domain_manifest(name: str) -> dict:
    return {
        "name": name,
        "version": "0.1.0",
        "self_hosting": False,
        "package_root": "src",
        "domains": {
            name: {
                "src": f"src/{name}",
                "spec": f"docs/specs/{name}/spec.md",
                "tests": f"tests/unit/{name}",
                "description": name,
            }
        },
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


def ensure_mcp_config(target: Path) -> bool:
    """Idempotently merge k3dge (and pipeline-enabled peers) into .mcp.json.

    Returns True if config is valid/merged, False if existing file is corrupted (with stderr warning).
    Public API for cli.mcp sync; templates spec contracts this symbol.
    """
    import sys

    mcp_path = target / ".mcp.json"
    # Load existing or start empty; corrupted JSON or non-dict root must not silently destroy peers
    data: dict = {}
    if mcp_path.is_file():
        try:
            raw = mcp_path.read_text(encoding="utf-8")
            loaded = json.loads(raw)
            if not isinstance(loaded, dict):
                print(f"[WARN] .mcp.json is not a JSON object ({mcp_path}), skipped to avoid overwriting peers", file=sys.stderr)
                return False
            data = loaded
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            print(f"[WARN] .mcp.json corrupted ({mcp_path}): {exc}, skipped to avoid overwriting peers", file=sys.stderr)
            return False
    if "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
        data["mcpServers"] = {}
    # k3dge is always present (framework)
    if "k3dge" not in data["mcpServers"]:
        if (target / "src" / "k3dge").is_dir():
            data["mcpServers"]["k3dge"] = {
                "command": "python",
                "args": ["-m", "k3dge.cli.mcp"],
                "env": {"PYTHONPATH": "src"},
            }
        else:
            data["mcpServers"]["k3dge"] = {
                "command": "python",
                "args": ["-m", "k3dge.cli.mcp"],
            }
        # Atomic write via temp file
        tmp = mcp_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        tmp.replace(mcp_path)
        return True
    return True
    # Peers from pipeline.toml are merged on demand via `k3dge mcp sync` (not scaffold time)


def _ensure_mcp_config(target: Path) -> bool:
    """Deprecated alias for ensure_mcp_config."""
    return ensure_mcp_config(target)


def _ensure_first_domain(target: Path, name: str, today: str) -> None:
    """Write or upgrade an empty manifest so the gate has at least one domain."""
    path = target / ".agent" / "manifest.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return
        if isinstance(data, dict) and data.get("domains"):
            return
        data = _first_domain_manifest(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    else:
        _write_if_missing(path, json.dumps(_first_domain_manifest(name), indent=2) + "\n")
    spec = SPEC_TEMPLATE.replace("<domain>", name)
    spec = re.sub(r"(\*\*Last Updated\*\*:).*", rf"\1 {today}", spec)
    _write_if_missing(target / "src" / name / "__init__.py", f'__version__ = "0.1.0"\n')
    _write_if_missing(target / "docs" / "specs" / name / "spec.md", spec)
    _write_if_missing(
        target / "tests" / "unit" / name / "test_smoke.py",
        'def test_smoke() -> None:\n    assert True\n',
    )


def scaffold(target: Path, name: str | None = None) -> None:
    import datetime

    target.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()
    slug = _slug(name or target.name)

    _write_if_missing(target / "AGENTS.md", AGENTS_TEMPLATE)
    _ensure_first_domain(target, slug, today)
    for rule_file in RULE_ASSETS:
        _write_if_missing(
            target / ".agent" / "rules" / rule_file,
            _asset("rules", rule_file),
        )
    _write_if_missing(target / ".agent" / "README.md", _asset("agent-readme.md"))
    _write_if_missing(target / ".agent" / "milestone", "M0\n")
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
    _write_if_missing(target / "docs" / "adr" / "README.md", ADR_README_TEMPLATE)
    (target / "docs" / "tasks").mkdir(parents=True, exist_ok=True)
    _write_if_missing(target / "docs" / "tasks" / "README.md", TASKS_README_TEMPLATE)
    (target / "docs" / "guides").mkdir(parents=True, exist_ok=True)
    _write_if_missing(target / "docs" / "guides" / "mcp-bridge.md", MCP_BRIDGE_TEMPLATE)
    _write_if_missing(target / "docs" / "guides" / "downstream.md", DOWNSTREAM_GUIDE_TEMPLATE)
    (target / "docs" / "protocols").mkdir(parents=True, exist_ok=True)
    _write_if_missing(target / "docs" / "protocols" / "audit_default.md", PROTOCOL_TEMPLATE)
    (target / "docs" / "generated").mkdir(parents=True, exist_ok=True)
    (target / "docs" / "branches").mkdir(parents=True, exist_ok=True)
    _write_if_missing(target / "docs" / "branches" / "README.md", BRANCHES_README_TEMPLATE)
    (target / "logs").mkdir(parents=True, exist_ok=True)
    (target / "docs" / "reviews").mkdir(parents=True, exist_ok=True)
    _write_if_missing(target / "docs" / "reviews" / "README.md", REVIEWS_README_TEMPLATE)
    _write_if_missing(target / "docs" / "reviews" / "SUMMARY.md", REVIEWS_SUMMARY_TEMPLATE)
    _write_if_missing(target / ".gitignore", GITIGNORE_TEMPLATE)
    (target / "docs" / "memo").mkdir(parents=True, exist_ok=True)
    (target / "docs" / "memo" / "archive").mkdir(parents=True, exist_ok=True)
    _write_if_missing(target / "docs" / "memo" / "README.md", MEMO_README_TEMPLATE)
    _write_if_missing(target / "docs" / "architecture" / "overview.md", ARCHITECTURE_TEMPLATE)
    _write_if_missing(target / ".agent" / "docs.toml", DOCS_TOML_TEMPLATE)
    _write_if_missing(target / ".agent" / "pipeline.toml", PIPELINE_TOML_TEMPLATE)
    ensure_mcp_config(target)
    _write_if_missing(target / "scripts" / "generate-docs.sh", GENERATE_DOCS_SH_TEMPLATE, executable=True)
    _write_if_missing(target / "scripts" / "generate-docs.ps1", GENERATE_DOCS_PS1_TEMPLATE)


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(prog="k3dge.templates.scaffold")
    parser.add_argument("target", nargs="?", default=".", help="target project root")
    parser.add_argument("--name", dest="name", default=None, help="project/domain slug (default: directory name)")
    args = parser.parse_args(argv)
    scaffold(Path(args.target).resolve(), name=args.name)
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
