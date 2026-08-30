"""Deterministic protocol dispatch: task_type -> protocol markdown.

The resolver is the fixed, config-driven half of the "worker reads the operation
spec before acting" discipline. It never runs an agent and never resets a session;
it only maps a task type to the protocol file on disk so an upstream harness can
inject that protocol into a fresh, bounded-attention context. See ADR 0012.
"""

from __future__ import annotations

import datetime
import fnmatch
import hashlib
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from k3dge.engine.contract import normalize

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:  # pragma: no cover
        tomllib = None  # type: ignore[assignment]


# Fallback registry so downstream repos without .agent/protocols.toml still
# resolve the two protocols k3dge ships. The on-disk TOML overrides these.
def specificity(pattern: str) -> Tuple[int, int, int]:
    """Specificity Tuple = (LiteralSegments, -WildcardSegments, PathDepth).

    Higher tuple wins (most-specific glob). Two globs with the same tuple that
    overlap on a file are an unresolvable tie (PROTOCOL_REGISTRY_INVALID).
    """
    segs = [s for s in pattern.split("/") if s != ""]
    lit = sum(1 for s in segs if "*" not in s)
    wild = sum(1 for s in segs if "*" in s)
    return (lit, -wild, len(segs))


def _repo_files(workspace: Path) -> List[str]:
    """Enumerate repo files: git ls-files when available, else a tree walk fallback."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "-c", "-o", "--exclude-standard"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode == 0:
            files = [l for l in out.stdout.splitlines() if l.strip()]
            if files:
                return files
    except Exception:
        pass
    files: List[str] = []
    for p in workspace.rglob("*"):
        if not p.is_file() or ".git" in p.parts or p.name.endswith(".tmp"):
            continue
        try:
            files.append(str(p.relative_to(workspace)).replace("\\", "/"))
        except ValueError:
            continue
    return files


_BUILTIN_REGISTRY: Dict[str, str] = {
    "audit": "docs/protocols/audit_default.md",
    "verify": "docs/protocols/verify_default.md",
}
_BUILTIN_DEFAULT = "audit"

_REGISTRY_REL = ".agent/protocols.toml"


class ProtocolResolutionError(ValueError):
    """Raised when a task_type cannot be mapped to an existing protocol file."""


@dataclass
class ProtocolRef:
    task_type: str
    rel: str
    path: Path
    exists: bool
    require_attend: bool = False


class ProtocolResolver:
    """Map a task_type to its protocol file deterministically from config."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.registry, self.default_type, self.path_map = self._load()

    def _load(self) -> Tuple[Dict[str, str], str, Dict[str, str]]:
        cfg_path = self.workspace / _REGISTRY_REL
        if tomllib is not None and cfg_path.is_file():
            try:
                data = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
            except Exception:
                return dict(_BUILTIN_REGISTRY), _BUILTIN_DEFAULT, {}
            protocols = data.get("protocols", {}) if isinstance(data.get("protocols"), dict) else {}
            registry = {k: str(v) for k, v in protocols.items() if isinstance(v, str)}
            if not registry:
                return dict(_BUILTIN_REGISTRY), _BUILTIN_DEFAULT, {}
            default = data.get("settings", {}).get("default") if isinstance(data.get("settings"), dict) else None
            if not isinstance(default, str) or default not in registry:
                default = next(iter(registry))
            paths = data.get("paths", {}) if isinstance(data.get("paths"), dict) else {}
            path_map = {str(k): str(v) for k, v in paths.items() if isinstance(v, str)}
            return registry, default, path_map
        return dict(_BUILTIN_REGISTRY), _BUILTIN_DEFAULT, {}

    def list_types(self) -> List[str]:
        return sorted(self.registry)

    def resolve(self, task_type: str) -> ProtocolRef:
        rel = self.registry.get(task_type)
        if rel is None:
            if task_type in (None, "", "default"):
                task_type = self.default_type
                rel = self.registry.get(self.default_type)
        if rel is None:
            avail = ", ".join(self.list_types()) or "(empty)"
            raise ProtocolResolutionError(
                f"no protocol registered for task_type '{task_type}'; available: {avail}"
            )
        path = self.workspace / rel
        return ProtocolRef(
            task_type=task_type,
            rel=rel,
            path=path,
            exists=path.is_file(),
            require_attend=True,
        )

    def _match_path(self, rel_path: str) -> Optional[str]:
        """Best (most specific) protocol key for a relative path; None if no match.

        Most-specific wins by Specificity Tuple (LiteralSegments, -WildcardSegments,
        PathDepth) descending. Same-tuple ties are rejected by validate_protocols_config,
        so the resolver never has to break an unambiguous tie.
        """
        best: Optional[str] = None
        best_score: tuple[int, int, int] = (-1, 0, -1)
        for pat, ptype in self.path_map.items():
            if fnmatch.fnmatch(rel_path, pat):
                score = specificity(pat)
                if score > best_score:
                    best_score = score
                    best = ptype
        return best

    def resolve_by_path(self, target: Path | str) -> Optional[ProtocolRef]:
        """Resolve the protocol for a file the agent is about to touch.

        Returns None when no path mapping matches, meaning the agent proceeds
        under the base spec (protocols augment, never replace). Most-specific
        glob wins, so `docs/reviews/**` overrides `docs/**`.
        """
        p = Path(target)
        # Resolve relative paths against the workspace so an agent can pass a
        # repo-relative file path (the common case) and still match [paths] globs.
        abs_p = p if p.is_absolute() else (self.workspace / p)
        rel: str
        try:
            rel = str(abs_p.relative_to(self.workspace))
        except ValueError:
            rel = abs_p.as_posix()
        rel = rel.replace("\\", "/")
        ptype = self._match_path(rel)
        if ptype is None:
            return None
        return self.resolve(ptype)

    def resolve_raw(self, task_type: str) -> str:
        ref = self.resolve(task_type)
        if not ref.exists:
            raise ProtocolResolutionError(f"protocol file not found for '{task_type}': {ref.rel}")
        return ref.path.read_text(encoding="utf-8")

    def challenge(
        self, target: Path | str | None = None, task_type: str | None = None, task_id: str = ""
    ) -> Optional[str]:
        """Dynamic load-proof for a workshop entry.

        Returns `sha256(normalize(protocol_text) + task_id)[:12]`. The agent can
        only answer after the protocol was injected into its live context (not
        merely grepped), so a correct reply proves attention was reset by the
        protocol. Returns None when no protocol maps (base spec, no helmet needed).
        """
        ref: Optional[ProtocolRef] = None
        if target is not None:
            ref = self.resolve_by_path(target)
        elif task_type:
            try:
                ref = self.resolve(task_type)
            except ProtocolResolutionError:
                ref = None
        if ref is None:
            return None
        text = ref.path.read_text(encoding="utf-8") if ref.exists else ""
        digest = hashlib.sha256((normalize(text) + task_id).encode("utf-8")).hexdigest()
        return digest[:12]

    def expected_constraints(self, target: Path | str | None = None, task_type: str | None = None) -> Optional[List[str]]:
        """Declared machine-checkable constraints of the mapped protocol (the checklist)."""
        ref: Optional[ProtocolRef] = None
        if target is not None:
            ref = self.resolve_by_path(target)
        elif task_type:
            try:
                ref = self.resolve(task_type)
            except ProtocolResolutionError:
                ref = None
        if ref is None or not ref.exists:
            return None
        return _parse_constraints(ref.path.read_text(encoding="utf-8"))

    def validate_ticket(
        self,
        target: Path | str | None = None,
        task_type: str | None = None,
        ticket: object = None,
        task_id: str = "",
    ) -> List[str]:
        """L2 entry-ticket validation: the agent's structured acknowledgment of the protocol.

        Proves a *synthesis* step (the agent bound every declared constraint to the
        task), not mere copying. Validates shape/completeness, NOT truth — the final
        deliverable is still gated by `k3dge check` (L3). Returns [] when valid; each
        element is a human-readable error. No protocol mapped => no ticket required.
        """
        ref: Optional[ProtocolRef] = None
        if target is not None:
            ref = self.resolve_by_path(target)
        elif task_type:
            try:
                ref = self.resolve(task_type)
            except ProtocolResolutionError:
                ref = None
        if ref is None:
            return []
        errors: List[str] = []
        if not isinstance(ticket, dict):
            return ["ticket must be a JSON object"]
        if ticket.get("protocol") != ref.task_type:
            errors.append(
                f"ticket.protocol '{ticket.get('protocol')}' != resolved protocol '{ref.task_type}'"
            )
        tid = ticket.get("task_id", "")
        if task_id and tid != task_id:
            errors.append(f"ticket.task_id '{tid}' != required '{task_id}'")
        binding = ticket.get("binding")
        if not isinstance(binding, list) or not binding:
            errors.append("ticket.binding must be a non-empty list")
            return errors
        norm_bind: List[str] = []
        for i, b in enumerate(binding):
            if not isinstance(b, dict):
                errors.append(f"binding[{i}] must be an object")
                continue
            c = b.get("constraint")
            h = b.get("how")
            if not isinstance(c, str) or not c.strip():
                errors.append(f"binding[{i}].constraint must be a non-empty string")
            else:
                norm_bind.append(_norm(c))
            if not isinstance(h, str) or not h.strip():
                errors.append(f"binding[{i}].how must be a non-empty string")
        # Completeness: every declared constraint must be acknowledged in the ticket.
        declared = self.expected_constraints(target=target, task_type=task_type) or []
        if declared:
            joined = " ".join(norm_bind)
            for d in declared:
                if _norm(d) not in joined:
                    errors.append(f"ticket missing binding for declared constraint: {d}")
        return errors

    def verify(
        self,
        target: Path | str | None = None,
        task_type: str | None = None,
        ticket: object = None,
        task_id: str = "",
    ) -> Dict[str, object]:
        """Soft gate (ADR 0022, revised): advisory L1+L2 verdict, never a hard block.

        - `pass`: no protocol mapped (base spec) OR ticket valid.
        - `advise`: protocol required but ticket invalid/missing — returns remediation
          so a cooperating agent self-corrects ("劝返"). No enforcement; the agent may
          still proceed, in which case the deviation is meant to be surfaced by `report`
          / `k3dge check` (L3, run where the agent cannot reach it).
        """
        ref: Optional[ProtocolRef] = None
        if target is not None:
            ref = self.resolve_by_path(target)
        elif task_type:
            try:
                ref = self.resolve(task_type)
            except ProtocolResolutionError:
                ref = None
        if ref is None:
            return {"verdict": "pass", "reason": "no protocol mapped; proceed under base spec"}
        chal = self.challenge(target=target, task_type=task_type, task_id=task_id)
        errs = self.validate_ticket(target=target, task_type=task_type, ticket=ticket, task_id=task_id)
        if errs:
            return {
                "verdict": "advise",
                "protocol": ref.task_type,
                "challenge": chal,
                "errors": errs,
                "remediation": (
                    "run `k3dge protocol resolve --path <file>` then "
                    "`k3dge protocol ticket --path <file> --task-id <id>` binding every "
                    "declared constraint; re-run `k3dge protocol verify`"
                ),
            }
        return {"verdict": "pass", "protocol": ref.task_type}


def write_incident(
    workspace: Path,
    target: str | None,
    task_type: str | None,
    task_id: str,
    detail: str,
) -> Path:
    """Escalate a persistent protocol deviation to a human-visible incident note.

    Writes `docs/incidents/INC-YYYYMMDD-protocol-<slug>.md`. This is the "report it to
    a human" backstop when an agent ignores the soft gate and proceeds regardless.
    """
    inc_dir = workspace / "docs" / "incidents"
    inc_dir.mkdir(parents=True, exist_ok=True)
    date = datetime.date.today().isoformat().replace("-", "")
    slug = Path(target).stem if target else (task_type or "protocol")
    safe_slug = re.sub(r"[^A-Za-z0-9._-]", "-", slug)
    path = inc_dir / f"INC-{date}-protocol-{safe_slug}.md"
    body = (
        f"# Incident: protocol deviation (soft gate ignored)\n\n"
        f"- **Path**: {target or '(none)'}\n"
        f"- **Protocol**: {task_type or '(none)'}\n"
        f"- **Task**: {task_id or '(none)'}\n"
        f"- **Date**: {datetime.date.today().isoformat()}\n\n"
        f"## Detail\n\n{detail}\n"
    )
    path.write_text(body, encoding="utf-8")
    return path


def _norm(s: str) -> str:
    # Drop markdown backticks so an agent acknowledging a constraint without quoting
    # it still matches the declared (backtick-wrapped) constraint text.
    return " ".join(s.replace("`", "").lower().split())


def _parse_constraints(markdown: str) -> List[str]:
    """Extract the machine-checkable constraint list from a protocol's `## Constraints` block.

    Collects bullet/numbered items under the first heading containing 'constraint' or
    '约束', stopping at the next heading. Used by the L2 entry-ticket validator.
    """
    collecting = False
    out: List[str] = []
    for line in markdown.splitlines():
        if re.match(r"^#{1,6}\s.*(constraint|约束)", line, re.IGNORECASE):
            collecting = True
            continue
        if collecting:
            if re.match(r"^#{1,6}\s", line):
                break
            m = re.match(r"^\s*(?:[-*]\s*|\d+[.)]\s*)(.*\S)\s*$", line)
            if m:
                out.append(m.group(1).strip())
    return out


def load_registry(workspace: Path) -> Dict[str, str]:
    return ProtocolResolver(workspace).registry


def default_type(workspace: Path) -> str:
    return ProtocolResolver(workspace).default_type


def validate_protocols_config(workspace: Path) -> List[Tuple[str, str]]:
    """Static gate for .agent/protocols.toml.

    Mirrors pipeline_schema: absent file is graceful (downstream may omit it);
    once present it is 100% strict — every mapped protocol file must exist on disk.
    """
    cfg_path = workspace / _REGISTRY_REL
    if not cfg_path.is_file():
        return []
    if tomllib is None:  # pragma: no cover
        return []
    try:
        data = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [("PROTOCOL_REGISTRY_INVALID", f"protocols.toml parse failed: {exc}")]
    protocols = data.get("protocols", {}) if isinstance(data.get("protocols"), dict) else {}
    out: List[Tuple[str, str]] = []
    if not protocols:
        out.append(("PROTOCOL_REGISTRY_INVALID", "protocols.toml has empty [protocols] registry"))
    for key, val in protocols.items():
        if not isinstance(val, str):
            out.append(("PROTOCOL_REGISTRY_INVALID", f"protocol '{key}' must map to a string path"))
            continue
        if not (workspace / val).is_file():
            out.append(
                ("PROTOCOL_REGISTRY_INVALID", f"protocol '{key}' -> '{val}' not found at {workspace / val}")
            )
    default = data.get("settings", {}).get("default") if isinstance(data.get("settings"), dict) else None
    if isinstance(default, str) and default not in protocols:
        out.append(
            ("PROTOCOL_REGISTRY_INVALID", f"settings.default '{default}' is not a registered protocol")
        )
    paths = data.get("paths", {}) if isinstance(data.get("paths"), dict) else {}
    for pat, val in paths.items():
        if not isinstance(val, str):
            out.append(("PROTOCOL_REGISTRY_INVALID", f"path map '{pat}' must map to a protocol key"))
            continue
        if val not in protocols:
            out.append(
                (
                    "PROTOCOL_REGISTRY_INVALID",
                    f"path map '{pat}' -> '{val}' is not a registered protocol",
                )
            )
    # Specificity-tuple tie detection (equivalence-class partition, then overlap scan).
    # Only globs in the SAME specificity class that actually overlap on a real file are a
    # genuine conflict; different-tuple overlaps are resolved by the resolver (highest wins).
    groups: Dict[Tuple[int, int, int], List[str]] = defaultdict(list)
    for pat in paths:
        groups[specificity(pat)].append(pat)
    for tup, pats in groups.items():
        if len(pats) < 2:
            continue
        for f in _repo_files(workspace):
            hits = [p for p in pats if fnmatch.fnmatch(f, p)]
            if len(hits) >= 2:
                out.append(
                    (
                        "PROTOCOL_REGISTRY_INVALID",
                        f"path globs {sorted(hits)} share specificity {tup} and both match '{f}'; "
                        "only one may win — disambiguate or remove the tie",
                    )
                )
                break
    return out
