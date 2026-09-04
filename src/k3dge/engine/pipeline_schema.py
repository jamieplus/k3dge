"""Static schema validation for `.agent/pipeline.toml` (lifecycle bus governance).

This is the third pillar of k3dge's fact-source gate matrix (alongside
`manifest.json` routing and `spec.md` contract hash). It promotes `pipeline.toml`
from a byte-compared scaffold artifact to a *semantically governed* contract.

Design constraints (ADR-aligned):
- Pure-static: no MCP/CLI probing, no network, no subprocess. Only structure,
  internal symbol reference (`stage -> peer[.actions.<a>]`), and physical
  existence of `manual` protocol files.
- Optional grace: if `.agent/pipeline.toml` is absent, validation is skipped
  (downstream minimal repos may not configure it); if present, 100% strict.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import List, Tuple

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        tomllib = None  # type: ignore

_VALID_PROVIDERS = frozenset({"mcp", "cli", "manual", "skip"})
# Endpoint facts belong to .mcp.json only (docs/protocols/peer_contract.md §0).
_ENDPOINT_KEYS = frozenset({"command", "env", "cwd"})
_PIPELINE_REL = ".agent/pipeline.toml"

# Returned tuple: (rule_code, human_message)
PipelineViolation = Tuple[str, str]


def validate_pipeline_config(workspace: Path) -> List[PipelineViolation]:
    """Validate `.agent/pipeline.toml`. Returns [] when valid or file absent.

    Rule codes: PIPELINE_SYNTAX_ERROR, PIPELINE_SCHEMA_INVALID,
    PIPELINE_UNRESOLVED_STAGE, PIPELINE_PROTOCOL_NOT_FOUND.
    """
    pipeline_file = workspace / _PIPELINE_REL
    if not pipeline_file.is_file():
        return []

    if tomllib is None:
        return [("PIPELINE_SYNTAX_ERROR",
                 "tomllib/tomli unavailable; cannot validate .agent/pipeline.toml")]

    try:
        data = tomllib.loads(pipeline_file.read_text(encoding="utf-8"))
    except Exception as exc:
        return [("PIPELINE_SYNTAX_ERROR", f"TOML parse failed: {exc}")]

    errors: List[PipelineViolation] = []
    legacy = [k for k in ("harnesses", "hooks") if k in data]
    if legacy:
        errors.append(
            (
                "PIPELINE_SCHEMA_INVALID",
                "legacy keys %s are not read; migrate to [peers]/[pipelines] (ADR-0006)"
                % ", ".join(legacy),
            )
        )
    peers = data.get("peers", {})
    if not isinstance(peers, dict):
        return [("PIPELINE_SCHEMA_INVALID", "'peers' must be a table")]
    roles = data.get("roles", {})
    if roles and not isinstance(roles, dict):
        return [("PIPELINE_SCHEMA_INVALID", "'roles' must be a table")]
    role_bind: dict = {}
    servers = _load_mcp_server_names(workspace)
    for r_name, r_cfg in (roles or {}).items():
        bind = r_cfg.get("bind") if isinstance(r_cfg, dict) else None
        kind = r_cfg.get("kind", "gate") if isinstance(r_cfg, dict) else "gate"
        if kind not in ("gate", "service"):
            errors.append(("PIPELINE_SCHEMA_INVALID",
                           f"role '{r_name}' kind must be 'gate' or 'service'"))
        if not isinstance(bind, str) or not bind:
            errors.append(("PIPELINE_SCHEMA_INVALID",
                           f"role '{r_name}' must declare a non-empty string 'bind'"))
        elif servers is not None and bind not in servers:
            errors.append(("PIPELINE_PEER_UNWIRED",
                           f"role '{r_name}' binds to '{bind}' not declared in .mcp.json mcpServers"))
        else:
            role_bind[r_name] = bind
    declared: set[str] = set()

    for p_name, p_cfg in peers.items():
        if not isinstance(p_cfg, dict):
            errors.append(("PIPELINE_SCHEMA_INVALID", f"peer '{p_name}' must be a table"))
            continue
        actions = p_cfg.get("actions")
        if actions is not None:
            if not isinstance(actions, dict):
                errors.append(("PIPELINE_SCHEMA_INVALID",
                               f"peer '{p_name}.actions' must be a table"))
                continue
            for a_name, a_cfg in actions.items():
                declared.add(f"{p_name}.actions.{a_name}")
                declared.add(f"{p_name}.{a_name}")  # 2-part compat alias
                errors.extend(_validate_transports(
                    workspace, a_cfg.get("transports", []),
                    f"{p_name}.actions.{a_name}", servers, role_bind))
        else:
            declared.add(p_name)
            errors.extend(_validate_transports(
                workspace, p_cfg.get("transports", []), p_name, servers, role_bind))

    pipelines = data.get("pipelines", {})
    if pipelines and not isinstance(pipelines, dict):
        errors.append(("PIPELINE_SCHEMA_INVALID", "'pipelines' must be a table"))
    for pipe_name, pipe_cfg in (pipelines or {}).items():
        if not isinstance(pipe_cfg, dict):
            errors.append(("PIPELINE_SCHEMA_INVALID",
                           f"pipeline '{pipe_name}' must be a table"))
            continue
        for stage in pipe_cfg.get("stages", []) or []:
            if stage not in declared:
                errors.append(("PIPELINE_UNRESOLVED_STAGE",
                               f"stage '{stage}' in pipeline '{pipe_name}' "
                               f"is not declared in peers"))

    return errors


def _load_mcp_server_names(workspace: Path):
    """Names declared in .mcp.json[mcpServers]; None if absent/unreadable."""
    p = workspace / ".mcp.json"
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    return set(servers) if isinstance(servers, dict) else None


def _validate_transports(workspace: Path, transports: object, scope: str,
                         servers=None, roles: dict = None) -> List[PipelineViolation]:
    errs: List[PipelineViolation] = []
    if not isinstance(transports, list) or not transports:
        return [("PIPELINE_SCHEMA_INVALID",
                 f"'{scope}' must declare a non-empty 'transports' list")]
    for idx, t in enumerate(transports):
        if not isinstance(t, dict):
            errs.append(("PIPELINE_SCHEMA_INVALID",
                         f"{scope}.transports[{idx}] must be a table"))
            continue
        prov = t.get("provider")
        if prov not in _VALID_PROVIDERS:
            errs.append(("PIPELINE_SCHEMA_INVALID",
                         f"invalid provider '{prov}' in {scope}.transports[{idx}] "
                         f"(expected one of {sorted(_VALID_PROVIDERS)})"))
            continue
        args = t.get("args")
        if args is not None and not isinstance(args, dict):
            errs.append(("PIPELINE_SCHEMA_INVALID",
                         f"{scope}.transports[{idx}]['args'] must be a table (peer tool defaults)"))
        if prov == "mcp":
            leaked = sorted(k for k in _ENDPOINT_KEYS if k in t)
            if leaked:
                errs.append(("PIPELINE_SCHEMA_INVALID",
                             f"{scope}.transports[{idx}] leaks endpoint facts {leaked}; "
                             "they belong in .mcp.json (peer contract §0)"))
            server = (roles or {}).get(scope.split(".")[0], scope.split(".")[0])
            if servers is None:
                errs.append(("PIPELINE_PEER_UNWIRED",
                             f"mcp transport in '{scope}' but .mcp.json is missing/unreadable"))
            elif server not in servers:
                errs.append(("PIPELINE_PEER_UNWIRED",
                             f"mcp transport '{scope}' resolves to server '{server}' "
                             "not declared in .mcp.json mcpServers"))
        if prov == "mcp" and not t.get("tool"):
            errs.append(("PIPELINE_SCHEMA_INVALID",
                         f"missing 'tool' for mcp transport in {scope}.transports[{idx}]"))
        elif prov == "cli" and not t.get("command"):
            errs.append(("PIPELINE_SCHEMA_INVALID",
                         f"missing 'command' for cli transport in {scope}.transports[{idx}]"))
        elif prov == "manual":
            proto = t.get("protocol")
            if not proto:
                errs.append(("PIPELINE_SCHEMA_INVALID",
                             f"missing 'protocol' for manual transport in {scope}.transports[{idx}]"))
            elif not (workspace / proto).is_file():
                errs.append(("PIPELINE_PROTOCOL_NOT_FOUND",
                             f"protocol file '{proto}' in '{scope}' does not exist on disk"))
    return errs
