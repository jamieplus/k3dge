""".mcp.json endpoint registry — read-only parse. No MCP client, no pipeline.

Host for the `mcpServers` map (value-9). `cli` and `engine` read through here.
`templates/scaffold` stays an island (ADR-0001: templates ↛ engine) and keeps
its own write-side parse.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Set

_MCP_CONFIG_REL = ".mcp.json"


def load_mcp_document(workspace: Path) -> Optional[Dict[str, Any]]:
    """Full `.mcp.json` object, or None if missing / unreadable / not a dict."""
    p = workspace / _MCP_CONFIG_REL
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def load_mcp_endpoints(workspace: Path) -> Dict[str, Any]:
    """`mcpServers` map; `{}` when absent or broken."""
    data = load_mcp_document(workspace)
    if data is None:
        return {}
    servers = data.get("mcpServers")
    return servers if isinstance(servers, dict) else {}


def mcp_server_names(workspace: Path) -> Optional[Set[str]]:
    """Declared server names. None if the file is absent or unreadable (schema skip)."""
    data = load_mcp_document(workspace)
    if data is None:
        return None
    servers = data.get("mcpServers")
    return set(servers) if isinstance(servers, dict) else None
