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
    """Declared server names.

    `None` **只**表示"文件缺失/不可读"（schema 跳过）；文件在但没有 `mcpServers`（或写成数组/
    字符串）是**已配置但一个都没有** ⇒ 返回空集。旧写法两种都返回 None，下游 `is None` 分支
    据此跳过 `MCP_JSON_PEER_MISSING` 检查 ⇒ 坏配置静默变绿（docstring 与实现不一致，ocr-261）。
    """
    data = load_mcp_document(workspace)
    if data is None:
        return None
    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        import sys

        print("[mcp_json] WARN: .mcp.json 存在但 mcpServers 缺失/不是表 ⇒ 按『无 server』处理",
              file=sys.stderr)
        return set()
    return set(servers)


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
    # 三元组不变量：**没有真的探到 mcp.py 就三个都返回 None**。旧版兜底分支只证明
    # "sibling 是个 pyproject 项目"就回一个模块名，写侧据此写进 .mcp.json ⇒ 外部 harness
    # 拿到一个永远起不来的 server（静态闸查不出，ocr-262）。
    mod: Optional[str] = None
    root: Optional[Path] = None
    for cand_mod, cand_root in (
        (f"{pid}.mcp", probe / "src"), (f"{pid}.cli.mcp", probe / "src"),
        (f"{pid}.mcp", probe), (f"{pid}.cli.mcp", probe),
    ):
        rel = cand_mod.split(".")
        if (cand_root.joinpath(*rel[:-1]) / "mcp.py").is_file():
            mod, root = cand_mod, cand_root
            break
    if mod is None or root is None:
        return probe, None, None
    try:
        py_path = os.path.relpath(root, workspace)
    except ValueError:
        py_path = str(root)
    return probe, mod, py_path
