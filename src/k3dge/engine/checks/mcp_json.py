"""`.mcp.json` 的 peer 面 vs `pipeline.toml` 声明。自 `ConsistencyEngine` 拆出。"""

from pathlib import Path
from typing import List

from k3dge.engine.models import Violation


def check_mcp_json(workspace: Path) -> List[Violation]:
    """`.mcp.json` 的 peer 面 vs `.agent/pipeline.toml` 声明（同一探测函数，不开第二判据）。"""
    from k3dge.engine import mcp_json as mj

    cfg_path = workspace / ".agent" / "pipeline.toml"
    doc = mj.load_mcp_document(workspace)
    if not cfg_path.is_file() or doc is None:
        return []  # 无声明/无文件 ⇒ 不造违例（缺文件归 PIPELINE_* 与 init 面）
    try:
        import tomllib as _toml
    except ModuleNotFoundError:  # py3.10
        try:
            import tomli as _toml  # type: ignore
        except ModuleNotFoundError:
            return []
    try:
        cfg = _toml.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return []  # 语法错由 PIPELINE_SCHEMA_INVALID 报，不在这里凑第二份
    servers = doc.get("mcpServers")
    if not isinstance(servers, dict):
        return [
            Violation(
                "MCP_JSON_PEER_MISSING",
                "`.mcp.json` has no mcpServers map",
                file_path=".mcp.json",
                detail={"path": ".mcp.json", "peer": "（缺 mcpServers 表）", "reason": "缺 mcpServers"},
            )
        ]
    out: List[Violation] = []
    if "k3dge" not in servers:
        out.append(
            Violation(
                "MCP_JSON_PEER_MISSING",
                "`.mcp.json` does not declare the k3dge server itself",
                file_path=".mcp.json",
                detail={"path": ".mcp.json", "peer": "k3dge"},
            )
        )
    for pid, pcfg in (cfg.get("peers") or {}).items():
        if not isinstance(pcfg, dict) or not pcfg.get("enabled", True) or pid == "k3dge":
            continue
        probe, mod, _pp = mj.probe_peer_mcp(workspace, pid)
        if pid in servers or probe is None or mod is None:
            continue  # 已声明 / sibling 不在（写侧本就会跳过，见 cli.mcp_peers 的回退告警）
        out.append(
            Violation(
                "MCP_JSON_PEER_MISSING",
                f"peer '{pid}' is declared enabled and resolvable but missing from `.mcp.json`",
                file_path=".mcp.json",
                detail={"path": ".mcp.json", "peer": pid},
            )
        )
    return out
