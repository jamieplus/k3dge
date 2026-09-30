"""Peer-action executor for `.agent/pipeline.toml` (k3dge invokes the lens).

`pipeline_schema.py` only statically validates structure. This module is the
*executor*: given a peer action reference (e.g. `k3dit.actions.audit`), it walks
that action's `transports` chain and runs the first transport that succeeds.

Chain order per ADR-0006 §2.3: `mcp -> cli -> manual`; `skip` records only.
- `mcp`:  real outbound stdio client. The endpoint (command/args/env/cwd) comes from
  `.mcp.json[mcpServers.<peer>]` **only** — `pipeline.toml` carries flow + tool name,
  never a second copy of the connection recipe (ADR-0006 §2.3.3).
- `cli`:  run `command` via subprocess (the lens's own CLI, e.g. `k3dit check-report`).
- `manual`: print the `protocol` path and wait for the human/agent to produce the
  artifact; then verify the artifact exists on disk.

Identity rule (ADR-0006 §2.2): a transport of peer X may only reach X's own server
or X's own CLI. The pre-2026-09-02 code resolved every peer's `mcp` transport through
`shutil.which` of one bind and ran that CLI for every tool, so another peer's tools
would have been answered by the wrong server — that path is gone and must not come back.

Downgrade rule (ADR-0006 §2.4): moving off `mcp` because it failed is never silent —
each hop emits `WARN[DOWNGRADE] action=… from=… to=… reason=…` on stderr and into
`logs/k3dge.log`, and the reason carries the peer's own stderr tail (a bare
"Connection closed" hid the 2026-09-02 incident where 3/4 servers died at `run()`).

k3dge never audits or scores — it only *invokes* the peer and gates on the
returned artifact. This keeps the sidecar boundary (ADR-0006): the work agent
fixes, the audit-role lens audits, k3dge only routes + gates.
"""

from __future__ import annotations

import datetime
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from k3dge.engine.mcp_json import load_mcp_endpoints
from k3dge.engine.pipeline_schema import (  # 单源：provider 合法集 + action ref 解析归闸核层
    _VALID_PROVIDERS,
    resolve_action,
    resolve_role,
)

try:
    import tomllib  # py3.11+
except ModuleNotFoundError:  # pragma: no cover
    try:
        import tomli as tomllib  # type: ignore
    except ModuleNotFoundError:
        tomllib = None  # type: ignore

_PIPELINE_REL = ".agent/pipeline.toml"
_MCP_CONFIG_REL = ".mcp.json"
_LOG_REL = "logs/k3dge.log"
# Interpreter declared in .mcp.json that we land on this machine's venv when missing.
_FALLBACK_INTERPRETERS = ("python", "python3")


@dataclass
class TransportResult:
    ok: bool
    provider: Optional[str]
    detail: str
    skipped: bool = False
    downgrades: List[str] = field(default_factory=list)
    payload: str = ""
    """Untruncated peer response (JSON from an MCP `tools/call`, raw stdout from a CLI).

    `detail` is the human-facing summary and may be truncated; anything a caller has to
    parse (suggested report path, findings) reads `payload`."""


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


def _append_log(workspace: Path, line: str) -> None:
    """Append one machine-readable line; the harness log is an audit trail, not a scratch pad."""
    try:
        log = workspace / _LOG_REL
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:  # pragma: no cover - defensive
        pass


def _emit_downgrade(workspace: Path, action_ref: str, frm: str, to: str, reason: str, io) -> str:
    """ADR-0006 §2.4: every hop off a stronger transport is announced and persisted."""
    note = f"action={action_ref} {frm}->{to} reason={reason}"
    print(f"WARN[DOWNGRADE] {note}", file=io, flush=True)
    ts = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    _append_log(workspace, f"[{ts}] WARN[DOWNGRADE] {note}")
    from k3dge.engine import events
    events.emit(workspace, "downgrade", action=action_ref, frm=frm, to=to, reason=reason)
    return note


# ---------------------------------------------------------------------------
# Outbound MCP client (ADR-0006 §2.3): `.mcp.json` is the only endpoint source
# (parse in mcp_json; spawn stays here).
# ---------------------------------------------------------------------------


def resolve_endpoint_command(workspace: Path, endpoint: dict) -> Tuple[Optional[str], str]:
    """Land a declared interpreter on this machine, noisily.

    `.mcp.json` stays the source of truth; this only reports how the declared command
    was resolved. A bare `python` that is not on PATH falls back to
    `<workspace>/.venv/bin/python` and the substitution is stated in the returned note
    (callers print it) — never a silent rewrite of the recipe.
    """
    declared = endpoint.get("command") if isinstance(endpoint, dict) else None
    if not isinstance(declared, str) or not declared:
        return None, "endpoint declares no command"
    probe = Path(declared)
    if probe.is_absolute():
        return (declared, declared) if probe.exists() else (None, f"interpreter not found: {declared}")
    found = shutil.which(declared)
    if found:
        return found, declared
    if declared in _FALLBACK_INTERPRETERS:
        venv = workspace / ".venv" / "bin" / declared
        if venv.exists():
            return str(venv), f"{declared} -> {venv} (fallback: declared name not on PATH)"
    return None, f"interpreter not found: {declared} (not on PATH, no .venv)"


def build_server_params(workspace: Path, endpoint: dict, command: str) -> dict:
    """Normalize one `.mcp.json` entry into `StdioServerParameters` kwargs.

    `cwd` defaults to the consuming workspace, so a relative `PYTHONPATH` (e.g.
    `../k3che/src`) resolves identically for k3dge and for the external harness that
    reads the same file.
    """
    args = endpoint.get("args") or []
    env = endpoint.get("env")
    cwd = endpoint.get("cwd") or "."
    cwd_path = Path(cwd)
    if not cwd_path.is_absolute():
        cwd_path = (workspace / cwd).resolve()
    return {
        "command": command,
        "args": [str(a) for a in args],
        "env": dict(env) if isinstance(env, dict) else None,
        "cwd": str(cwd_path),
    }


def _unwrap_exc(exc: BaseException) -> str:
    """Flatten anyio TaskGroups / ExceptionGroups down to the leaf that failed."""
    cur: BaseException = exc
    for _ in range(8):
        subs = getattr(cur, "exceptions", None)
        if not subs:
            break
        cur = subs[0]
    return f"{type(cur).__name__}: {cur}".strip()[:400]


def call_mcp_tool(params: dict, tool: str, arguments: dict, timeout: int) -> Tuple[bool, str, List[str], str]:
    """Spawn -> initialize -> tools/list -> (optional) tools/call. Returns (ok, text, tools, stderr).

    Empty `tool` means "handshake and list only" (what `k3dge mcp probe` uses).
    """
    import asyncio
    import tempfile

    try:
        from mcp import ClientSession  # type: ignore[import-not-found]
        from mcp.client.stdio import StdioServerParameters, stdio_client  # type: ignore[import-not-found]
    except ImportError as exc:
        return False, f"mcp SDK not importable in this interpreter: {exc}", [], ""

    # The SDK pipes the child's stderr onto this handle's fd, so it must be a real
    # file — an in-memory StringIO dies with `UnsupportedOperation: fileno`.
    errfile = tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace")

    async def _run():
        async with stdio_client(StdioServerParameters(**params), errlog=errfile) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listed = [t.name for t in (await session.list_tools()).tools]
                if not tool:
                    return True, "", listed
                if tool not in listed:
                    return False, f"tool '{tool}' not offered; server offers {sorted(listed)}", listed
                res = await session.call_tool(tool, arguments or {})
                text = "".join(getattr(c, "text", "") for c in (res.content or []))
                # `is_error` is the peer answering "your call is wrong" — a failed
                # transport, not a success, or the chain would never downgrade.
                # SDK 2.x models are snake_case (1.x wire/SDK used isError): read both.
                flagged = getattr(res, "is_error", None)
                if flagged is None:
                    flagged = getattr(res, "isError", False)
                return (not flagged), text, listed

    def _stderr() -> str:
        try:
            errfile.seek(0)
            return errfile.read().strip()
        except OSError:  # pragma: no cover - defensive
            return ""

    try:
        ok, text, listed = asyncio.run(asyncio.wait_for(_run(), timeout=timeout))
        return ok, text, listed, _stderr()
    except (KeyboardInterrupt, SystemExit):
        raise                     # 人工中断/退出不得被降格成"mcp 失败"再跑 CLI（ocr-091）
    except Exception as exc:  # timeout / dead child / protocol error
        tail = _stderr()
        detail = _unwrap_exc(exc)
        if tail and tail.splitlines()[-1] not in detail:
            detail = f"{detail} | stderr: {tail.splitlines()[-1][:200]}"
        return False, detail, [], tail
    finally:
        try:
            errfile.close()
        except OSError:  # pragma: no cover - defensive
            pass


def _run_mcp(
    workspace: Path,
    peer: str,
    tool: str,
    timeout: int,
    io,
    arguments: Optional[dict] = None,
) -> TransportResult:
    endpoint = load_mcp_endpoints(workspace).get(peer)
    if not isinstance(endpoint, dict):
        return TransportResult(False, "mcp", f"{_MCP_CONFIG_REL} declares no mcpServers.{peer} — peer not wired")
    command, how = resolve_endpoint_command(workspace, endpoint)
    if command is None:
        return TransportResult(False, "mcp", how)
    if " (fallback" in how:
        print(f"[PEER-MCP] interpreter landed: {how}", file=io, flush=True)
    params = build_server_params(workspace, endpoint, command)
    # 契约 §1：入参只有调用方显式给出的领域事实；不做隐式注入（避免把消费仓事实偷塞给对端）。
    ok, text, _listed, stderr_tail = call_mcp_tool(params, tool, arguments or {}, timeout)
    head = f"peer={peer} tool={tool or '(handshake)'} via {how}"
    if ok:
        brief = text if len(text) <= 2000 else text[:2000] + "…（截断；完整响应见 payload）"
        return TransportResult(True, "mcp", f"{head}\n{brief}".rstrip(), payload=text)
    detail = f"{head} :: {text}"
    if stderr_tail and "stderr:" not in text and stderr_tail.splitlines()[-1] not in detail:
        detail += f" | last stderr: {stderr_tail.splitlines()[-1][:160]}"
    return TransportResult(False, "mcp", detail, payload=text)


def probe_servers(workspace: Path, timeout: int = 20) -> List[Tuple[str, bool, str, List[str]]]:
    """Return (name, ok, detail, tools) per `.mcp.json` server — a real handshake each.

    A config entry proves nothing: on 2026-09-02 three of four peers matched
    `"k3dit" in mcpServers` while dying inside `mcp.run()`. Static gates never call
    this (ADR-0006 §2.3.2 keeps `check` a pure hard gate).
    """
    out: List[Tuple[str, bool, str, List[str]]] = []
    for name, endpoint in load_mcp_endpoints(workspace).items():
        if not isinstance(endpoint, dict):
            out.append((name, False, "entry is not an object", []))
            continue
        command, how = resolve_endpoint_command(workspace, endpoint)
        if command is None:
            out.append((name, False, how, []))
            continue
        ok, text, listed, stderr_tail = call_mcp_tool(
            build_server_params(workspace, endpoint, command), "", {}, timeout
        )
        detail = how if ok else f"{text}"
        if not ok and stderr_tail and "stderr:" not in detail:
            detail += f" | stderr: {stderr_tail.splitlines()[-1][:160]}"
        out.append((name, ok, detail, sorted(listed)))
    return out


# ---------------------------------------------------------------------------
# Other transports
# ---------------------------------------------------------------------------


def _cli_command(command: str, arguments: Optional[dict]) -> str:
    """把 `{key}` 占位替换成实参（`{bundle}`/`{milestone_id}`/`{path}`…）。

    为什么不用 `str.format`：shell 命令里 `{}`（brace expansion/awk 脚本）很常见，format 会把它们
    当占位符炸掉。这里只做**已知键**的字面替换，未提供的键原样保留（可见地不生效，好过静默错替换）。

    值一律 `shlex.quote`：命令经 `shell=True` 执行，而 `{path}`/`{bundle}` 来自被审仓路径 ⇒ 含空格/
    shell 元字符（`; & $( ) ' "`）时会裂参或命令注入（code-10）。引号化保留 shell 语义（管道/重定向
    仍由命令自身书写），只把**插值**变成单个安全参数。"""
    import shlex

    out = command or ""
    for k, v in (arguments or {}).items():
        if v is None:
            continue
        out = out.replace("{" + str(k) + "}", shlex.quote(str(v)))
    return out


def _run_cli(workspace: Path, command: str, timeout: int, io,
             arguments: Optional[dict] = None) -> TransportResult:
    # k3dit:leftover F-4 @line shell=True 属仓内受信配置（席裁有意留）
    command = _cli_command(command, arguments)
    try:
        # `shell=True` + subprocess.run(timeout=) 只杀 `/bin/sh`：孙进程（真正的透镜 CLI）继续跑，
        # 且后代持有管道会让 communicate 继续阻塞 ⇒ "已降级"的 CLI 还在后台写（ocr-281）。
        proc = subprocess.Popen(
            command, shell=True, cwd=workspace, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, start_new_session=True,
        )
        try:
            so, se = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            import os
            import signal

            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except OSError:      # pragma: no cover - 进程已退
                proc.kill()
            so, se = proc.communicate()
            return TransportResult(False, "cli", f"timeout after {timeout}s（整个进程组已终止）")
        out = (so or "") + (se or "")
        if proc.returncode == 0:
            return TransportResult(True, "cli", out.strip() or "ok", payload=out.strip())
        return TransportResult(False, "cli", f"exit={proc.returncode}: {out.strip()}")
    except subprocess.TimeoutExpired:
        return TransportResult(False, "cli", f"timeout after {timeout}s")
    except Exception as exc:  # pragma: no cover - defensive
        return TransportResult(False, "cli", f"error: {exc}")


def _run_manual(workspace: Path, protocol: str, action_ref: str, io) -> TransportResult:
    proto_path = workspace / protocol
    if not proto_path.is_file():
        # 协议文件都不在 ⇒ 不能无条件 ok=True（否则"零产物"也能满足闸，ocr-093）。
        return TransportResult(False, "manual", f"protocol file missing: {protocol}")
    print(
        f"[PEER-MANUAL] action '{action_ref}' has no live lens; follow protocol:\n"
        f"  {proto_path if proto_path.is_file() else protocol}\n"
        f"  Produce the required artifact under docs/reviews/ then continue.\n"
        f"  NOTE: a report produced here is NOT an independent audit (ADR-0006 §2.4) —\n"
        f"  highlight it as a downgrade in whatever summary you hand back.",
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
    return TransportResult(True, "manual", "manual protocol presented (not an independent audit)")


def run_action(
    workspace: Path,
    action_ref: str,
    *,
    io=None,
    timeout_default: int = 60,
    arguments: Optional[dict] = None,
) -> TransportResult:
    """Execute a peer action by walking its transports. Returns first success.

    `action_ref`'s first segment is the peer id and therefore the `.mcp.json` server
    key — that is what keeps one peer from answering for another (ADR-0006 §2.2).
    `skip` transports short-circuit to a successful, `skipped=True` result, recorded
    to `logs/k3dge.log` (ADR-0006 degrade chain). Every hop off a failed transport
    emits `WARN[DOWNGRADE]` and is collected on `TransportResult.downgrades` so the
    caller can repeat it in its summary (§2.4.1).
    """
    io = io or _NullIO()
    pipeline = load_pipeline_config(workspace)
    peer = resolve_role(pipeline, action_ref.split(".")[0])
    transports = resolve_action(pipeline, action_ref)
    if transports is None:
        return TransportResult(False, None, f"action '{action_ref}' not declared in pipeline.toml")
    downgrades: List[str] = []
    last_reason = "no transport ran"
    for idx, t in enumerate(transports):
        if not isinstance(t, dict):
            continue
        prov = t.get("provider")
        if not isinstance(prov, str) or prov not in _VALID_PROVIDERS:
            # 不可哈希的 TOML 值（数组/内联表）会让 frozenset 成员判断抛 TypeError（ocr-287）
            continue
        try:                          # `timeout = "60s"` / 表 / bool 都不该让执行器抛（ocr-282）
            timeout = int(t.get("timeout", timeout_default))
        except (TypeError, ValueError):
            timeout = int(timeout_default) if str(timeout_default).isdigit() else 120
            print(f"[PEER] WARN: action '{action_ref}' 的 timeout 非法（{t.get('timeout')!r}）⇒ 用 {timeout}s",
                  file=sys.stderr)
        nxt = next((x.get("provider") for x in transports[idx + 1 :] if isinstance(x, dict)), None)
        if prov == "skip":
            _append_log(workspace, f"[{datetime.datetime.now().astimezone().isoformat(timespec='seconds')}] HARNESS_SKIP: action '{action_ref}' resolved to skip transport")
            return TransportResult(True, "skip", "skipped", skipped=True, downgrades=downgrades)
        if prov == "mcp":
            merged = dict(t.get("args") or {})
            merged.update(arguments or {})
            res = _run_mcp(workspace, peer, str(t.get("tool", "")), timeout, io, merged)
        elif prov == "cli":
            # 与 mcp 分支同构：传输自己声明的 args 是底座，调用期 arguments 覆盖之（此前 cli 整个忽略，
            # 与 `_validate_transports` 对所有 provider 都校 args 的口径漂移，ocr-283）。
            merged_cli = dict(t.get("args") or {})
            merged_cli.update(arguments or {})
            res = _run_cli(workspace, str(t.get("command", "")), timeout, io, merged_cli)
        elif prov == "manual":
            # The failed transport above already emitted its own WARN[DOWNGRADE] with
            # to=manual; emitting again here would double-report one downgrade.
            res = _run_manual(workspace, str(t.get("protocol", "")), action_ref, io)
        else:  # pragma: no cover - filtered by _VALID_PROVIDERS
            continue
        if res.ok:
            res.downgrades = downgrades
            return res
        last_reason = res.detail.replace("\n", " ")[:240]
        if nxt:
            downgrades.append(_emit_downgrade(workspace, action_ref, prov, nxt or "none", last_reason, io))
        else:
            downgrades.append(_emit_downgrade(workspace, action_ref, prov, "none", last_reason, io))
    return TransportResult(
        False, None, f"all transports for '{action_ref}' failed or were skipped", downgrades=downgrades
    )
