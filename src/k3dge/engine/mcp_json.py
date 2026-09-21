""".mcp.json endpoint registry — read-only parse. No MCP client, no pipeline.

Host for the `mcpServers` map (value-9). `cli` and `engine` read through here.
`templates/scaffold` stays an island (ADR-0001: templates ↛ engine) and keeps
its own write-side parse.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple

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


def probe_peer_mcp(workspace: Path, pid: str) -> Tuple[Optional[Path], Optional[str], Optional[str]]:
    """Locate a sibling peer MCP module + the PYTHONPATH that can import it.

    **单一实现**：写侧（`cli.mcp_peers._sync_peers_into_mcp`）与新鲜度闸
    （`evaluator` 的 `MCP_JSON_PEER_MISSING`）都走这里——否则"哪些 peer 该出现在
    `.mcp.json`"会有两份判据，迟早漂移。纯路径探测，不改盘、不起进程。
    """
    sibling = workspace.parent / pid
    alt_sibling = workspace / pid
    probe = sibling if sibling.is_dir() else (alt_sibling if alt_sibling.is_dir() else None)
    if probe is None:
        return None, None, None
    mod = None
    if (probe / "src" / pid / "mcp.py").is_file():
        mod = f"{pid}.mcp"
    elif (probe / "src" / pid / "cli" / "mcp.py").is_file():
        mod = f"{pid}.cli.mcp"
    elif (probe / "pyproject.toml").is_file():
        mod = f"{pid}.mcp"
    py_path = None
    src = probe / "src"
    if src.is_dir():
        try:
            py_path = os.path.relpath(src, workspace)
        except ValueError:
            py_path = str(src)
    return probe, mod, py_path
