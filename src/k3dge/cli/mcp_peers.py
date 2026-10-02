"""MCP peer management: probe, sync, fallback warnings.

Extracted from cli/main.py to reduce its size and isolate MCP peer logic.
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
from pathlib import Path
from typing import Optional

from k3dge.engine.mcp_json import probe_peer_mcp


def _peer_fallback_warn(peer: str, reason: str, fallback: str) -> None:
    """Highlighted warning when an external peer is unavailable and we fall back to default."""
    msg = f"Peer '{peer}' failed ({reason}) → fallback to DEFAULT '{fallback}'"
    # docstring 说"非 TTY 走纯文本"，旧实现**两条都印** ⇒ 每条告警重复两遍，且 CI/日志里
    # 仍混入转义垃圾（下游按 WARN[DOWNGRADE] 计数会翻倍，385）
    is_tty = bool(getattr(sys.stderr, "isatty", lambda: False)())
    line = (f"\033[1;41mWARN[DOWNGRADE]\033[0m \033[1;33m{msg}\033[0m" if is_tty
            else f"WARN[DOWNGRADE] {msg}")
    print(line, file=sys.stderr)


def _peer_fallback(pcfg: dict) -> str:
    """Resolve the terminal fallback descriptor for a peer from its transport chains.

    A peer may carry peer-level `transports` (single-purpose) or `actions.<name>.transports`
    (multi-purpose). The fallback is the last transport's descriptor: a `manual` provider
    yields its `protocol`, a `skip` provider yields "skip".
    """
    # pipeline.toml 是用户可编辑的外部输入：一个坏 peer（actions 写成数组表、transports 元素写成
    # 字符串）不得让整条合并 AttributeError 崩掉（ocr-186）。逐层 isinstance 收窄，坏结构只跳过该跳。
    if not isinstance(pcfg, dict):
        return "audit_default.md"
    chains = []
    if pcfg.get("transports"):
        chains.append(pcfg["transports"])
    actions = pcfg.get("actions")
    if isinstance(actions, dict):
        for action_cfg in actions.values():
            if isinstance(action_cfg, dict) and action_cfg.get("transports"):
                chains.append(action_cfg["transports"])
    for transports in chains:
        if not isinstance(transports, list) or not transports:
            continue
        last = transports[-1]
        if not isinstance(last, dict):
            continue
        if last.get("provider") == "manual":
            return str(last.get("protocol", "audit_default.md"))
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
    if "mcpServers" not in data:
        data["mcpServers"] = {}
    elif not isinstance(data["mcpServers"], dict):
        # 可解析但 `mcpServers` 非对象（数组/标量）⇒ **绝不**覆写为空骨架（与上分支同理，ocr2-027）。
        # 覆写会静默丢掉用户内容；拒改比"修好"安全。
        return f".mcp.json 的 mcpServers 非对象（{type(data['mcpServers']).__name__}）⇒ 跳过写盘（不覆盖用户内容）"
    changed = False
    peers = cfg.get("peers", {})
    # `pipeline.toml` 是用户可编辑的外部输入：`[[peers]]`（数组表）或 `peers.x = true`
    # 会让下面的 `.items()`/`.get()` 抛 AttributeError（ocr2-175）⇒ 先验形状。
    if not isinstance(peers, dict):
        return f"pipeline.toml 的 [peers] 不是表（{type(peers).__name__}）⇒ 跳过 peer 合并（不覆盖用户内容）"
    for pid, pcfg in peers.items():
        if pid == "k3dge" or not isinstance(pcfg, dict) or not pcfg.get("enabled", True):
            if isinstance(pcfg, dict) is False and pid != "k3dge":
                _peer_fallback_warn(pid, f"peers.{pid} 形状不对（{type(pcfg).__name__}，期望表）⇒ 跳过该 peer",
                                    "audit_default.md")
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
        # 固定名 `.mcp.tmp` + 无清理 ⇒ 失败/并发会留半截配置被后续读到（ocr-187）。
        tmp = mcp_path.with_name(f"{mcp_path.name}.{os.getpid()}.tmp")
        try:
            tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            tmp.replace(mcp_path)
        except Exception as exc:
            return f"[MCP] peer merge write failed: {exc}"
        finally:
            with contextlib.suppress(OSError):
                tmp.unlink(missing_ok=True)
    return None


def _warn_missing_peer_servers(workspace: Path, cfg: dict) -> None:
    """Warn for enabled pipeline peers absent from .mcp.json (no sibling / not synced)."""
    servers = _mcp_servers(workspace)
    peers = cfg.get("peers", {})
    # 与 `_sync_peers_into_mcp` 同口径：坏形状不得让整轮告警静默消失（ocr2-176）。
    # 这里的唯一调用方（milestone-align）吞掉所有异常 ⇒ 循环内绝不能抛。
    if not isinstance(peers, dict):
        _peer_fallback_warn("peers", f"[peers] 形状不对（{type(peers).__name__}，期望表）⇒ 无法逐项告警",
                            "audit_default.md")
        return
    for pid, pcfg in peers.items():
        try:
            if pid == "k3dge" or not isinstance(pcfg, dict) or not pcfg.get("enabled", True):
                if pid != "k3dge" and not isinstance(pcfg, dict):
                    _peer_fallback_warn(pid, f"peers.{pid} 形状不对（{type(pcfg).__name__}，期望表）",
                                        "audit_default.md")
                continue
            if pid not in servers:
                _peer_fallback_warn(pid, "enabled in pipeline.toml but missing in .mcp.json (no sibling or not synced via 'k3dge mcp sync')", _peer_fallback(pcfg))
        except Exception as exc:  # 单个坏 peer 不得连坐其余 peer 的告警
            _peer_fallback_warn(str(pid), f"检查失败（{type(exc).__name__}: {exc}）", "audit_default.md")


def cmd_mcp_sync(workspace: Path) -> int:
    from k3dge.templates.scaffold import ensure_mcp_config

    ok_mcp = ensure_mcp_config(workspace)
    if not ok_mcp:
        print("[MCP] .mcp.json skipped due to corruption, see WARN above; not overwriting", file=sys.stderr)
        return 1   # 损坏 ⇒ 不支持续跑 peer 合并，也**不**报 synced 的假成功（ocr-031）
    # Peer merging from pipeline.toml is best-effort; report if pipeline is unreadable
    # tomllib is 3.11+, tomli is fallback for 3.10; neither present → skip peer merging gracefully
    tomllib_mod = _load_tomllib()
    peer_note = ""
    if tomllib_mod is None:
        _peer_fallback_warn("pipeline", "tomllib/tomli not available (py<3.11 without tomli)", "skip peer merging, keep k3dge only")
        # 降级路也印 "synced" + exit 0 会让只读 stdout/rc 的 CI 以为 peer 已合入（ocr2-177）⇒
        # 成功行必须限定范围（k3dge-only），降级原因留在 stderr 告警里。
        peer_note = " (k3dge only; peer merging skipped: no tomllib/tomli)"
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
            peer_note = " (k3dge only; peer merging skipped: no pipeline.toml)"
    print(f"[MCP] synced {workspace / '.mcp.json'}{peer_note}")
    return 0


def cmd_mcp_probe(args, workspace: Path) -> int:
    # Live handshake per declared server. Deliberately NOT part of `check`:
    # `check` is a pure static hard gate (ADR-0006 §2.3.2).
    from k3dge.engine.pipeline_runner import load_mcp_endpoints, probe_servers

    timeout = int(getattr(args, "timeout", 20) or 20)
    servers = load_mcp_endpoints(workspace)
    if not servers:
        # 缺失 / 坏 JSON / 根非对象 / 没写 mcpServers 表 / 写了个空表 是**不同**的事实，
        # 旧都报"no servers declared"（386）。分支不能建立在 `mcp_server_names` 的 None 上——
        # 它的语义已收紧为"仅缺失"（ocr-261 补齐：在而坏 ⇒ set()+WARN），这里直接看文档。
        from k3dge.engine.mcp_json import load_mcp_document

        doc_path = workspace / ".mcp.json"
        doc = load_mcp_document(workspace)
        if not doc_path.is_file():
            why = f"没有 {doc_path}（跑 k3dge mcp sync 生成）"
        elif doc is None:
            why = f"{doc_path} 读不出/形状不对（坏 JSON 或根不是对象）"
        else:
            why = f"{doc_path} 里没有声明任何 server（mcpServers 缺失/非表/空表）"
        print(f"[MCP] {why}", file=sys.stderr)
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
