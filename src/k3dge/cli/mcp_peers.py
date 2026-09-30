"""MCP peer management: probe, sync, fallback warnings.

Extracted from cli/main.py to reduce its size and isolate MCP peer logic.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

from k3dge.engine.mcp_json import probe_peer_mcp


def _peer_fallback_warn(peer: str, reason: str, fallback: str) -> None:
    """Highlighted warning when an external peer is unavailable and we fall back to default."""
    msg = f"Peer '{peer}' failed ({reason}) → fallback to DEFAULT '{fallback}'"
    # High-visibility: red background + yellow text + plain fallback for non-TTY
    banner = f"\033[1;41mWARN[DOWNGRADE]\033[0m \033[1;33m{msg}\033[0m"
    print(banner, file=sys.stderr)
    print(f"WARN[DOWNGRADE] {msg}", file=sys.stderr)


def _peer_fallback(pcfg: dict) -> str:
    """Resolve the terminal fallback descriptor for a peer from its transport chains.

    A peer may carry peer-level `transports` (single-purpose) or `actions.<name>.transports`
    (multi-purpose). The fallback is the last transport's descriptor: a `manual` provider
    yields its `protocol`, a `skip` provider yields "skip".
    """
    chains = []
    if pcfg.get("transports"):
        chains.append(pcfg["transports"])
    for action_cfg in pcfg.get("actions", {}).values():
        ts = action_cfg.get("transports")
        if ts:
            chains.append(ts)
    for transports in chains:
        if not transports:
            continue
        last = transports[-1]
        if last.get("provider") == "manual":
            return last.get("protocol", "audit_default.md")
        if last.get("provider") == "skip":
            return "skip"
    return "audit_default.md"




def _peer_mcp_entry(mod: str, pythonpath: Optional[str]) -> dict:
    entry: dict = {"command": "python", "args": ["-m", mod]}
    if pythonpath:
        entry["env"] = {"PYTHONPATH": pythonpath}
    return entry


def _ensure_peer_pythonpath(existing: dict, pythonpath: Optional[str]) -> bool:
    """Fill PYTHONPATH on an existing peer entry. Returns True if mutated."""
    if not pythonpath or not isinstance(existing, dict):
        return False
    env = existing.get("env")
    if not isinstance(env, dict):
        env = {}
    if env.get("PYTHONPATH"):
        return False
    merged = dict(env)
    merged["PYTHONPATH"] = pythonpath
    existing["env"] = merged
    return True


def _load_tomllib():
    """tomllib (py3.11+) or tomli fallback; None when neither is importable."""
    try:
        import tomllib
        return tomllib
    except ImportError:
        try:
            import tomli  # type: ignore[import-not-found]
            return tomli
        except ImportError:
            return None


# value-9: engine+cli 读口在 mcp_json；templates/scaffold 仍自解析（孤岛，ADR-0001）
def _mcp_servers(workspace: Path) -> dict:
    """.mcp.json `mcpServers` map (read-only); {} when absent/broken."""
    from k3dge.engine.mcp_json import load_mcp_endpoints

    return load_mcp_endpoints(workspace)


def _sync_peers_into_mcp(workspace: Path, cfg: dict) -> Optional[str]:
    """Merge enabled peers from pipeline.toml into .mcp.json. Returns error string or None."""
    mcp_path = workspace / ".mcp.json"
    if mcp_path.is_file():
        try:
            data = json.loads(mcp_path.read_text(encoding="utf-8"))
        except Exception as exc:
            # 存在但读不了 ⇒ **绝不**用空骨架覆盖（否则用户手写的 mcpServers/其它顶层键静默丢失，ocr-004）。
            return f".mcp.json 存在但不可解析（{exc}）⇒ 跳过写盘（不覆盖用户内容）"
        if not isinstance(data, dict):
            return ".mcp.json 根节点不是对象 ⇒ 跳过写盘（不覆盖用户内容）"
    else:
        data = {"mcpServers": {}}
    if "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
        data["mcpServers"] = {}
    changed = False
    for pid, pcfg in cfg.get("peers", {}).items():
        if pid == "k3dge" or not pcfg.get("enabled", True):
            continue
        probe, mod, py_path = probe_peer_mcp(workspace, pid)
        if probe is None or mod is None:
            if pid not in data["mcpServers"]:
                sibling = workspace.parent / pid
                alt_sibling = workspace / pid
                _peer_fallback_warn(pid, f"sibling not found at {sibling} nor {alt_sibling} or no mcp module", _peer_fallback(pcfg))
            continue
        existing = data["mcpServers"].get(pid)
        if existing is None:
            data["mcpServers"][pid] = _peer_mcp_entry(mod, py_path)
            changed = True
            print(f"[MCP] auto-added peer '{pid}' from sibling {probe} as python -m {mod}", file=sys.stderr)
        elif _ensure_peer_pythonpath(existing, py_path):
            changed = True
            print(f"[MCP] filled PYTHONPATH for peer '{pid}' -> {py_path}", file=sys.stderr)
    if changed:
        try:
            tmp = mcp_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            tmp.replace(mcp_path)
        except Exception as exc:
            return f"[MCP] peer merge write failed: {exc}"
    return None


def _warn_missing_peer_servers(workspace: Path, cfg: dict) -> None:
    """Warn for enabled pipeline peers absent from .mcp.json (no sibling / not synced)."""
    servers = _mcp_servers(workspace)
    for pid, pcfg in cfg.get("peers", {}).items():
        if pid == "k3dge" or not pcfg.get("enabled", True):
            continue
        if pid not in servers:
            _peer_fallback_warn(pid, "enabled in pipeline.toml but missing in .mcp.json (no sibling or not synced via 'k3dge mcp sync')", _peer_fallback(pcfg))


def cmd_mcp_sync(workspace: Path) -> int:
    from k3dge.templates.scaffold import ensure_mcp_config

    ok_mcp = ensure_mcp_config(workspace)
    if not ok_mcp:
        print("[MCP] .mcp.json skipped due to corruption, see WARN above; not overwriting", file=sys.stderr)
    # Peer merging from pipeline.toml is best-effort; report if pipeline is unreadable
    # tomllib is 3.11+, tomli is fallback for 3.10; neither present → skip peer merging gracefully
    tomllib_mod = _load_tomllib()
    if tomllib_mod is None:
        _peer_fallback_warn("pipeline", "tomllib/tomli not available (py<3.11 without tomli)", "skip peer merging, keep k3dge only")
    else:
        cfg_path = workspace / ".agent" / "pipeline.toml"
        if cfg_path.is_file():
            try:
                cfg = tomllib_mod.loads(cfg_path.read_text(encoding="utf-8"))
            except Exception as exc:
                print(f"[MCP] pipeline.toml parse failed: {exc}", file=sys.stderr)
                return 1
            try:
                err = _sync_peers_into_mcp(workspace, cfg)
            except Exception as exc:
                err = f"[MCP] pipeline handling failed: {exc}"
            if err:
                print(err, file=sys.stderr)
                return 1
        else:
            _peer_fallback_warn("pipeline", ".agent/pipeline.toml not found", "keep k3dge only")
    print(f"[MCP] synced {workspace / '.mcp.json'}")
    return 0


def cmd_mcp_probe(args, workspace: Path) -> int:
    # Live handshake per declared server. Deliberately NOT part of `check`:
    # `check` is a pure static hard gate (ADR-0006 §2.3.2).
    from k3dge.engine.pipeline_runner import load_mcp_endpoints, probe_servers

    timeout = int(getattr(args, "timeout", 20) or 20)
    servers = load_mcp_endpoints(workspace)
    if not servers:
        print(f"[MCP] no servers declared in {workspace / '.mcp.json'}", file=sys.stderr)
        return 1
    rows = probe_servers(workspace, timeout=timeout)
    as_json = getattr(args, "json", False)
    if as_json:
        print(json.dumps({"ok": all(r[1] for r in rows), "servers": [
            {"name": n, "ok": ok, "detail": d, "tools": t} for n, ok, d, t in rows
        ]}, indent=2, ensure_ascii=False))
        return 0 if all(r[1] for r in rows) else 1
    alive = 0
    for name, ok, detail, tools in rows:
        alive += 1 if ok else 0
        print(f"  [{'ALIVE' if ok else 'DEAD '}] {name:8s} tools={tools if tools else '-'} {(':: ' + detail) if detail else ''}")
    print(f"[MCP] probed {len(rows)} declared server(s): {alive} alive, {len(rows) - alive} dead ({workspace / '.mcp.json'})")
    if alive < len(rows):
        print("WARN[DOWNGRADE] any audit/quality action on a DEAD server falls back to manual,\n"
              "                and a manual report is NOT an independent audit (ADR-0006 §2.4)", file=sys.stderr)
    return 0 if alive == len(rows) else 1
