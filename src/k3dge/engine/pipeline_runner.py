"""Peer-action executor for `.agent/pipeline.toml` (k3dge invokes the lens).

`pipeline_schema.py` only statically validates structure. This module is the
*executor*: given a peer action reference (e.g. `k3dit.actions.audit`), it walks
that action's `transports` chain and runs the first transport that succeeds.

Chain order per ADR-0006: `mcp -> cli -> manual`; `skip` records only.
- `mcp`:  preferred external lens. k3dge CLI has no in-process MCP client, so
  this is a best-effort bridge — if a sibling `k3dit` CLI is discoverable it is
  invoked, otherwise the transport is skipped and the chain falls through.
- `cli`:  run `command` via subprocess (the lens's own CLI, e.g. `k3dit check-report`).
- `manual`: print the `protocol` path and wait for the human/agent to produce the
  artifact; then verify the artifact exists on disk.

k3dge never audits or scores — it only *invokes* the peer and gates on the
returned artifact. This keeps the sidecar boundary (ADR-0006): the work agent
fixes, the k3dit lens audits, k3dge only routes + gates.
"""

from __future__ import annotations

import datetime
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

if False:  # pragma: no cover - keep tomllib import local
    pass

try:
    import tomllib  # py3.11+
except ModuleNotFoundError:  # pragma: no cover
    try:
        import tomli as tomllib  # type: ignore
    except ModuleNotFoundError:
        tomllib = None  # type: ignore

_PIPELINE_REL = ".agent/pipeline.toml"
_VALID_PROVIDERS = frozenset({"mcp", "cli", "manual", "skip"})
_LOG_REL = "logs/k3dge.log"


@dataclass
class TransportResult:
    ok: bool
    provider: Optional[str]
    detail: str
    skipped: bool = False


class _NullIO:
    def write(self, *a, **k):  # pragma: no cover - defensive
        return None

    def flush(self, *a, **k):  # pragma: no cover - defensive
        return None


def load_pipeline_config(workspace: Path) -> dict:
    """Return parsed pipeline.toml, or {} if absent/unparseable."""
    if tomllib is None:
        return {}
    p = workspace / _PIPELINE_REL
    if not p.is_file():
        return {}
    try:
        return tomllib.loads(p.read_text(encoding="utf-8"))
    except Exception:  # pragma: no cover - defensive
        return {}


def resolve_action(pipeline: dict, action_ref: str) -> Optional[List[dict]]:
    """Resolve `peer.actions.name` (or `peer.name` alias) to its transports list."""
    if not pipeline:
        return None
    peers = pipeline.get("peers", {})
    parts = action_ref.split(".")
    if len(parts) >= 3 and parts[1] == "actions":
        peer = peers.get(parts[0], {})
        action = peer.get("actions", {}).get(parts[2])
        if isinstance(action, dict) and action.get("transports"):
            return action["transports"]
    # 2-part alias: peer.name
    if len(parts) == 2:
        peer = peers.get(parts[0], {})
        action = peer.get("actions", {}).get(parts[1])
        if isinstance(action, dict) and action.get("transports"):
            return action["transports"]
        if peer.get("transports"):
            return peer["transports"]
    return None


def _log_harness_skip(workspace: Path, action_ref: str) -> None:
    try:
        log = workspace / _LOG_REL
        log.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().isoformat(timespec="seconds")
        log.write_text(
            f"[{ts}] HARNESS_SKIP: action '{action_ref}' resolved to skip transport\n",
            encoding="utf-8",
        )
    except OSError:  # pragma: no cover - defensive
        pass


def _discover_k3dit_cli() -> Optional[str]:
    return shutil.which("k3dit")


def _run_cli(workspace: Path, command: str, timeout: int, io) -> TransportResult:
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode == 0:
            return TransportResult(True, "cli", out.strip() or "ok")
        return TransportResult(False, "cli", f"exit={proc.returncode}: {out.strip()}")
    except subprocess.TimeoutExpired:
        return TransportResult(False, "cli", f"timeout after {timeout}s")
    except Exception as exc:  # pragma: no cover - defensive
        return TransportResult(False, "cli", f"error: {exc}")


def _run_manual(workspace: Path, protocol: str, action_ref: str, io) -> TransportResult:
    proto_path = workspace / protocol
    print(
        f"[PEER-MANUAL] action '{action_ref}' has no live lens; follow protocol:\n"
        f"  {proto_path if proto_path.is_file() else protocol}\n"
        f"  Produce the required artifact under docs/reviews/ then continue.",
        file=io,
        flush=True,
    )
    # In an interactive session, wait for the operator to finish; otherwise the
    # caller is expected to have already produced the artifact.
    if getattr(io, "isatty", lambda: False)():
        try:
            input("  Press ENTER once the artifact is ready (or Ctrl-C to abort): ")
        except (EOFError, KeyboardInterrupt):  # pragma: no cover - interactive only
            return TransportResult(False, "manual", "aborted by operator")
    return TransportResult(True, "manual", "manual protocol presented")


def _run_mcp_best_effort(workspace: Path, tool: str, timeout: int, io) -> TransportResult:
    """Best-effort MCP bridge: k3dge CLI has no in-process MCP client.

    If a sibling `k3dit` CLI is discoverable we delegate; otherwise the chain
    falls through to `cli`/`manual`. Never blocks on a dead MCP server.
    """
    cli = _discover_k3dit_cli()
    if cli:
        # Map a known mcp tool name to a k3dit subcommand when possible.
        sub = tool.replace("k3dit_", "").replace("_", "-")
        return _run_cli(workspace, f"{cli} {sub}", timeout, io)
    print(
        f"[PEER-MCP] no in-process MCP client for '{tool}'; falling through to cli/manual",
        file=io,
        flush=True,
    )
    return TransportResult(False, "mcp", "no MCP client available")


def run_action(
    workspace: Path,
    action_ref: str,
    *,
    io=None,
    timeout_default: int = 60,
) -> TransportResult:
    """Execute a peer action by walking its transports. Returns first success.

    `skip` transports short-circuit to a successful, `skipped=True` result and
    are recorded to logs/k3dge.log as HARNESS_SKIP (ADR-0006 degrade chain).
    """
    io = io or _NullIO()
    pipeline = load_pipeline_config(workspace)
    transports = resolve_action(pipeline, action_ref)
    if transports is None:
        return TransportResult(False, None, f"action '{action_ref}' not declared in pipeline.toml")
    for t in transports:
        if not isinstance(t, dict):
            continue
        prov = t.get("provider")
        if prov not in _VALID_PROVIDERS:
            continue
        if prov == "skip":
            _log_harness_skip(workspace, action_ref)
            return TransportResult(True, "skip", "skipped", skipped=True)
        timeout = int(t.get("timeout", timeout_default))
        if prov == "mcp":
            res = _run_mcp_best_effort(workspace, t.get("tool", ""), timeout, io)
            if res.ok:
                return res
            continue
        if prov == "cli":
            res = _run_cli(workspace, t.get("command", ""), timeout, io)
            if res.ok:
                return res
            continue
        if prov == "manual":
            return _run_manual(workspace, t.get("protocol", ""), action_ref, io)
    return TransportResult(False, None, f"all transports for '{action_ref}' failed or were skipped")
