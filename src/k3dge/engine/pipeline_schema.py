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

from pathlib import Path
import sys
from typing import List, Optional, Tuple

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


# --- action ref 解析（纯配置读取，无副作用）---
# 归属：闸核层。`pipeline_runner`（出向/生命周期）从这里 import —— 方向 lifecycle → gate，
# 符合 T-02（闸核不得 import 生命周期，`test_gate_imports` 守）。原先住在 runner 里，
# 于是闸核想校验“声明的外部步能否解析”就得反向 import 生命周期层（实测红）。
def resolve_role(pipeline: dict, name: str) -> str:
    """`[roles.<name>] bind = "<server>"` → 具体 server 名；无绑定返回原名。

    规则 08 / peer contract §0：编排只认角色（audit/quality/cache），角色→实现的绑定
    是配置事实；k3dge 的代码路径上不出现具体 harness 名。
    """
    roles = pipeline.get("roles") if isinstance(pipeline, dict) else None
    if isinstance(roles, dict):
        entry = roles.get(name)
        if isinstance(entry, dict):
            bind = entry.get("bind")
            if isinstance(bind, str) and bind and bind != name:
                return bind
    return name


def resolve_action(pipeline: dict, action_ref: str) -> Optional[List[dict]]:
    """Resolve `role.actions.name` / `peer.actions.name` (or 2-part alias) to transports."""
    if not pipeline:
        return None
    parts = action_ref.split(".")
    if parts:
        bound = resolve_role(pipeline, parts[0])
        if bound != parts[0]:
            action_ref = ".".join([bound] + parts[1:])
    peers = pipeline.get("peers", {})
    parts = action_ref.split(".")
    if len(parts) >= 3 and parts[1] == "actions":
        peer = peers.get(parts[0], {})
        acts = peer.get("actions", {}) if isinstance(peer, dict) else {}
        action = acts.get(parts[2]) if isinstance(acts, dict) else None   # 类型守卫，别裸 .get（ocr-094）
        if isinstance(action, dict) and action.get("transports"):
            return action["transports"]
    # 2-part alias: peer.name
    if len(parts) == 2:
        # 3-part 分支有 `isinstance` 守卫，这里裸 `.get`：`peer`/`actions` 非对象时 AttributeError（ocr2-070）。
        peer = peers.get(parts[0], {}) if isinstance(peers, dict) else {}
        _acts = peer.get("actions", {}) if isinstance(peer, dict) else {}
        action = _acts.get(parts[1]) if isinstance(_acts, dict) else None
        if isinstance(action, dict) and action.get("transports"):
            return action["transports"]
        if peer.get("transports"):
            return peer["transports"]
    return None


# k3dit:leftover Q-6 CC28 validate_pipeline_config 分拆校验
def _validate_legacy_keys(data) -> List[PipelineViolation]:
    legacy = [k for k in ("harnesses", "hooks") if k in data]
    if legacy:
        return [("PIPELINE_SCHEMA_INVALID",
                 "legacy keys %s are not read; migrate to [peers]/[pipelines] (ADR-0006)" % ", ".join(legacy))]
    return []


def _declares_mcp(peer_cfg) -> bool:
    """该 peer 是否声明了任何 `mcp` 跳（peer 级或 action 级）。

    约束的**真实危害**是"声明了 mcp 跳却没有注册的 server"；纯 cli 传输的 peer（如 MCP 面已退役的
    k3dit）不需要在 `.mcp.json` 里留条目——旧规则要求"角色绑定的 peer 必须在册"，会把合法的
    cli-only peer 判红（2026-09-26 实测：k3dit 撤 MCP 服务端后 PIPELINE_PEER_UNWIRED 误报）。
    """
    if not isinstance(peer_cfg, dict):
        return False

    def _has_mcp(trs) -> bool:
        return any(isinstance(x, dict) and x.get("provider") == "mcp" for x in (trs or []))

    if _has_mcp(peer_cfg.get("transports")):
        return True
    acts = peer_cfg.get("actions")
    for spec in (acts.values() if isinstance(acts, dict) else []):   # 非映射别 .values() 崩（ocr-095）
        if isinstance(spec, dict) and _has_mcp(spec.get("transports")):
            return True
    return False


def _validate_roles(roles, servers, peers=None):
    """returns (errors, {role: bind})."""
    errors: List[PipelineViolation] = []
    role_bind: dict = {}
    for r_name, r_cfg in (roles or {}).items():
        bind = r_cfg.get("bind") if isinstance(r_cfg, dict) else None
        kind = r_cfg.get("kind", "gate") if isinstance(r_cfg, dict) else "gate"
        if kind not in ("gate", "service"):
            errors.append(("PIPELINE_SCHEMA_INVALID",
                           f"role '{r_name}' kind must be 'gate' or 'service'"))
        if not isinstance(bind, str) or not bind:
            errors.append(("PIPELINE_SCHEMA_INVALID",
                           f"role '{r_name}' must declare a non-empty string 'bind'"))
        elif servers is not None and bind not in servers and _declares_mcp((peers or {}).get(bind)):
            errors.append(("PIPELINE_PEER_UNWIRED",
                           f"role '{r_name}' binds to '{bind}'：声明了 mcp 跳但 .mcp.json 里没有该 server"))
        else:
            role_bind[r_name] = bind
    return errors, role_bind


def _validate_peers(workspace, peers, servers, role_bind):
    """returns (errors, declared action refs)。

    `declared` 集合在 449 之前是纯写入：唯一消费者 `_validate_pipelines` 从不读它
    （`[pipelines.*]` 已废、只报存在）⇒ 不再收集，只回 errors（第二元保留为空集，签名不变）。
    """
    errors: List[PipelineViolation] = []
    for p_name, p_cfg in peers.items():
        if not isinstance(p_cfg, dict):
            errors.append(("PIPELINE_SCHEMA_INVALID", f"peer '{p_name}' must be a table"))
            continue
        actions = p_cfg.get("actions")
        if actions is not None and not isinstance(actions, dict):
            errors.append(("PIPELINE_SCHEMA_INVALID",
                           f"peer '{p_name}.actions' must be a table"))
            # 不能整条 continue：那会连带跳过 peer 级 transports 的校验（tool 缺失 / endpoint
            # 事实泄漏 / 未注册 server 全部漏判，ocr-284）⇒ 置 None 后继续校 peer 级。
            actions = None
        if actions is not None:
            for a_name, a_cfg in actions.items():

                if not isinstance(a_cfg, dict):
                    # 值写成字符串/数组 ⇒ 报错而非 AttributeError 崩（ocr-096）。
                    errors.append(("PIPELINE_SCHEMA_INVALID",
                                   f"peer '{p_name}.actions.{a_name}' must be a table"))
                    continue
                errors.extend(_validate_transports(
                    workspace, a_cfg.get("transports", []),
                    f"{p_name}.actions.{a_name}", servers, role_bind))
            # peer 级 transports 即使在 actions 表有效时仍是活配置（2-part 别名回退，
            # ocr2-291）：有声明就必须同口径校验。
            if isinstance(p_cfg.get("transports"), list) and p_cfg.get("transports"):
                errors.extend(_validate_transports(
                    workspace, p_cfg.get("transports", []), p_name, servers, role_bind))
        else:

            errors.extend(_validate_transports(
                workspace, p_cfg.get("transports", []), p_name, servers, role_bind))
    return errors, set()  # declared 已无消费者（449）：保留位置返回，签名不变


def _validate_pipelines(pipelines) -> List[PipelineViolation]:
    """`[pipelines.*]` 已废（迁为 `[checks.<op>].stages_<phase>`）：留此只做**迁移守卫**。

    历史病灶：那两处声明只有本函数校验形状，**没有任何执行者读取**——文档声称的
    机制不存在（AGENTS.md §13 缺“到达”环）。外部步现由 `gates.stages()` 声明、
    `milestone_audit.run_audit_flow` 真读；下游若还留着旧段，必须显式红一次逼迁移，
    而不是静默失效。
    """
    errors: List[PipelineViolation] = []
    if not pipelines:
        return errors
    if not isinstance(pipelines, dict):
        return [("PIPELINE_SCHEMA_INVALID", "'pipelines' must be a table")]
    for pipe_name in sorted(pipelines):
        errors.append((
            "PIPELINE_SCHEMA_INVALID",
            f"[pipelines.{pipe_name}] is retired: declare external steps as "
            f"`[checks.<op>].stages_<phase>` in .agent/pipeline.toml "
            f"(or rely on engine/gates.DEFAULTS — `.agent/gates.toml` is retired); "
            f"nothing reads [pipelines.*] anymore",
        ))
    return errors


def _validate_legacy_gates_toml(workspace: Path) -> List[PipelineViolation]:
    """`.agent/gates.toml` 已废（声明面收进 pipeline.toml 一处）：存在即红一次逼迁移。

    不静默忽略——静默忽略会让下游以为自己的覆盖生效了（实测前科：本仓 gates.toml
    覆盖列表漏了 reconcile，功能静默死亡，见 2026-09-17-M10-refactor-adr_archive_to_sync）。
    """
    from k3dge.engine import gates

    if not gates.legacy_config_present(workspace):
        return []
    return [("PIPELINE_SCHEMA_INVALID",
             ".agent/gates.toml is retired: move [checks.*] and thresholds into "
             ".agent/pipeline.toml ([checks.<op>] / [gates.<name>]); nothing reads gates.toml anymore")]


def _validate_declared_stages(workspace: Path, data: dict) -> List[PipelineViolation]:
    """声明的外部步必须解析得到 transports —— 不让声明空转。

    `[checks.*].stages_*` 是 action ref（角色名 `audit.actions.x` 或 peer 直名）；
    解析走 `resolve_action`（含 `[roles.*] bind` 的角色→peer 解析），解析不到 ⇒ 红。
    这是“声明面唯一 + 声明必须有执行者”的机检半边（另半边是执行器真读它）。
    """
    from k3dge.engine import gates

    errors: List[PipelineViolation] = []
    for ref in gates.all_stage_refs(workspace):
        if resolve_action(data, ref) is None:
            errors.append((
                "PIPELINE_UNRESOLVED_STAGE",
                f"declared stage '{ref}' resolves to no transports "
                f"(check [roles.*] bind + [peers.*.actions.*] in .agent/pipeline.toml, "
                f"or override [checks.audit] in .agent/gates.toml)",
            ))
    return errors


# k3dit:leftover Q-6 CC28 validate_pipeline_config 分拆校验
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

    errors: List[PipelineViolation] = _validate_legacy_keys(data)
    peers = data.get("peers", {})
    if not isinstance(peers, dict):
        return [("PIPELINE_SCHEMA_INVALID", "'peers' must be a table")]
    roles = data.get("roles", {})
    if roles and not isinstance(roles, dict):
        return [("PIPELINE_SCHEMA_INVALID", "'roles' must be a table")]
    from k3dge.engine.mcp_json import mcp_server_names

    servers = mcp_server_names(workspace)
    r_errs, role_bind = _validate_roles(roles, servers, peers)
    errors.extend(r_errs)
    p_errs, _declared = _validate_peers(workspace, peers, servers, role_bind)
    errors.extend(p_errs)
    errors.extend(_validate_pipelines(data.get("pipelines", {})))
    errors.extend(_validate_legacy_gates_toml(workspace))
    errors.extend(_validate_declared_stages(workspace, data))
    return errors


def _validate_mcp_transport(workspace: Path, t: dict, idx: int, scope: str,
                            servers=None, roles=None, **_kw) -> List[PipelineViolation]:
    errs: List[PipelineViolation] = []
    if not t.get("tool"):
        errs.append(("PIPELINE_SCHEMA_INVALID",
                     f"missing 'tool' for mcp transport in {scope}.transports[{idx}]"))
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
    return errs


def _validate_cli_transport(workspace: Path, t: dict, idx: int, scope: str, **_kw) -> List[PipelineViolation]:
    if not t.get("command"):
        return [("PIPELINE_SCHEMA_INVALID",
                 f"missing 'command' for cli transport in {scope}.transports[{idx}]")]
    return []


def _validate_manual_transport(workspace: Path, t: dict, idx: int, scope: str, **_kw) -> List[PipelineViolation]:
    proto = t.get("protocol")
    if proto is not None and (isinstance(proto, (dict, list, bool)) or not isinstance(proto, str)):
        return [("PIPELINE_SCHEMA_INVALID",
                 f"manual transport '{scope}.transports[{idx}]' protocol must be a string")]
    if isinstance(proto, str) and (Path(proto).is_absolute() or ".." in Path(proto).parts):
        # 协议必须在 workspace 内：绝对路径 / `..` 让"读协议"变成读仓外任意文件（ocr-286）
        return [("PIPELINE_SCHEMA_INVALID",
                 f"manual transport '{scope}.transports[{idx}]' protocol 越出 workspace：{proto!r}")]
    if not proto:
        return [("PIPELINE_SCHEMA_INVALID",
                 f"missing 'protocol' for manual transport in {scope}.transports[{idx}]")]
    try:
        # 纯词法检查挡不住仓内软链外逃（`docs/protocols -> ~/.ssh`，ocr2-292）：
        # 解析后必须仍在 workspace 内才算存在。
        cand = (workspace / proto).resolve()
        if not cand.is_relative_to(workspace.resolve()):
            return [("PIPELINE_SCHEMA_INVALID",
                     f"manual transport '{scope}.transports[{idx}]' protocol 越出 workspace（软链）：{proto!r}")]
    except OSError:
        return [("PIPELINE_PROTOCOL_NOT_FOUND",
                 f"protocol file '{proto}' in '{scope}' does not exist on disk")]
    if not (workspace / proto).is_file():
        return [("PIPELINE_PROTOCOL_NOT_FOUND",
                 f"protocol file '{proto}' in '{scope}' does not exist on disk")]
    return []


_PROVIDER_VALIDATORS = {
    "mcp": _validate_mcp_transport,
    "cli": _validate_cli_transport,
    "manual": _validate_manual_transport,
}


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
        # 不可哈希的 TOML 值（数组/内联表/布尔）既非法也不能进 frozenset 成员判断（ocr-287）
        if not isinstance(prov, str) or prov not in _VALID_PROVIDERS:
            errs.append(("PIPELINE_SCHEMA_INVALID",
                         f"invalid provider '{prov}' in {scope}.transports[{idx}] "
                         f"(expected one of {sorted(_VALID_PROVIDERS)})"))
            continue
        args = t.get("args")
        if args is not None and not isinstance(args, dict):
            errs.append(("PIPELINE_SCHEMA_INVALID",
                         f"{scope}.transports[{idx}]['args'] must be a table (peer tool defaults)"))
        validator = _PROVIDER_VALIDATORS.get(prov)
        if validator is not None:
            errs.extend(validator(workspace, t, idx, scope, servers=servers, roles=roles))
    return errs
