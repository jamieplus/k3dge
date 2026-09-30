"""Version management: single source in pyproject.toml, mirrored to manifest and __init__."""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path
from typing import Tuple

from k3dge.engine.models import Violation

_VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)
# 宽容版回退（无 tomllib 的 3.10）：单引号/缩进都认；`[project]` 段内找，或行内表
# `project = { version = "…" }`。旧只认 `^version = "` ⇒ 合法 TOML 读不到 ⇒ None，
# 下游把"pyproject 没有版本行"当成"pyproject 不存在"，版本闸静默（335/338）。
_VERSION_LINE_RELAXED = re.compile(
    r"""(?m)^[ \t]*version[ \t]*=[ \t]*(?:"([^"]*)"|'([^']*)')""")
_VERSION_INLINE_RE = re.compile(
    r"""(?m)^project[ \t]*=[ \t]*\{[^}]*?version[ \t]*=[ \t]*(?:"([^"]*)"|'([^']*)')""")
_INIT_VERSION_RE = re.compile(r'^__version__\s*=\s*"([^"]+)"', re.MULTILINE)


def _pyproject_path(workspace: Path) -> Path:
    return workspace / "pyproject.toml"


def _manifest_path(workspace: Path) -> Path:
    return workspace / ".agent" / "manifest.json"


def _init_path(workspace: Path) -> Path:
    # Use manifest.package_root when available (downstream may be src/<name> vs src/k3dge)
    try:
        from k3dge.engine.manifest import Manifest

        manifest = Manifest.load(workspace)
        candidate = workspace / manifest.package_root / "__init__.py"
        if candidate.is_file():
            return candidate
        name = manifest.data.get("name")
        if name and manifest.package_root.replace("\\", "/").rstrip("/") == "src":
            alt = workspace / "src" / name / "__init__.py"
            if alt.is_file():
                return alt
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        pass
    return workspace / "src" / "k3dge" / "__init__.py"


def parse_version(v: str) -> Tuple[int, int, int]:
    parts = v.strip().lstrip("v").split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"Invalid SemVer '{v}': expected non-negative X.Y.Z")
    return int(parts[0]), int(parts[1]), int(parts[2])


def format_version(major: int, minor: int, patch: int) -> str:
    return f"{major}.{minor}.{patch}"


def _read_utf8(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"cannot decode {path} as UTF-8") from exc


def _atomic_write(path: Path, text: str) -> None:
    """委托 `engine.atomic`（版本文件与 sync 产物同一套写法，别各写一遍）。"""
    from k3dge.engine.atomic import atomic_write_text

    atomic_write_text(path, text)


def _pyproject_version(text: str) -> str | None:
    """从 pyproject 正文取 `[project] version`（3.11+ 用 tomllib，3.10 用宽容正则）。"""
    try:
        import tomllib
    except ModuleNotFoundError:            # pragma: no cover - 3.10
        tomllib = None
    if tomllib is not None:
        try:
            data = tomllib.loads(text)
        except Exception:
            return None
        v = (data.get("project") or {}).get("version")
        return str(v) if isinstance(v, str) else None
    m = _VERSION_INLINE_RE.search(text)
    if m:
        return m.group(1) or m.group(2)
    seg = re.split(r"(?m)^\s*\[[^\]]*\]\s*$", text)
    heads = re.findall(r"(?m)^\s*\[([^\]]*)\]", text)
    for body, head in zip(seg[1:], heads):
        if head.strip() != "project":
            continue
        lm = _VERSION_LINE_RELAXED.search(body)
        if lm:
            return lm.group(1) or lm.group(2)
    return None


def get_pyproject_version(workspace: Path) -> str | None:
    p = _pyproject_path(workspace)
    if not p.is_file():
        return None
    return _pyproject_version(_read_utf8(p))


def manifest_read_error(workspace: Path) -> str:
    """manifest **存在但读不出**的成因（空串＝没问题）。

    与"文件不存在"混成一个 None ⇒ `get_version`/`validate_versions` 的 canonical 变 None
    直接 `return []`：坏 JSON 让版本闸在脚手架下彻底静默（337）。
    """
    p = _manifest_path(workspace)
    if not p.is_file():
        return ""
    try:
        data = json.loads(_read_utf8(p))
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        return f"{p.name} 读不出/不是合法 JSON（{type(exc).__name__}: {exc}）"
    if not isinstance(data, dict):
        return f"{p.name} 顶层不是对象"
    return ""


def get_manifest_version(workspace: Path) -> str | None:
    p = _manifest_path(workspace)
    if not p.is_file():
        return None
    try:
        data = json.loads(_read_utf8(p))
        return data.get("version")
    except (json.JSONDecodeError, OSError, ValueError):
        return None


def get_init_version(workspace: Path) -> str | None:
    p = _init_path(workspace)
    if not p.is_file():
        return None
    m = _INIT_VERSION_RE.search(_read_utf8(p))
    return m.group(1) if m else None


def get_version(workspace: Path) -> str | None:
    """Canonical version: pyproject.toml if present, else .agent/manifest.json (downstream scaffold)."""
    py_v = get_pyproject_version(workspace)
    if py_v is not None:
        return py_v
    return get_manifest_version(workspace)


def validate_versions(workspace: Path) -> list[Violation]:
    """Ensure pyproject.toml (if present) ↔ .agent/manifest.json ↔ src/k3dge/__init__.py 必须同值."""
    py_v = get_pyproject_version(workspace)
    mf_v = get_manifest_version(workspace)
    init_v = get_init_version(workspace)
    violations: list[Violation] = []
    err = manifest_read_error(workspace)
    if err:
        violations.append(Violation(
            "VERSION_MISMATCH", f"版本闸无法判定：{err}",
            file_path=str(_manifest_path(workspace)), detail={"drift": err}))
        return violations
    canonical = py_v if py_v is not None else mf_v
    if canonical is None:
        return []
    if py_v is not None and mf_v != py_v:
        violations.append(
            Violation(
                "VERSION_MISMATCH",
                f"pyproject.toml={py_v} != .agent/manifest.json={mf_v}",
                file_path=str(_manifest_path(workspace)),
                detail={"drift": f"pyproject.toml={py_v} ≠ .agent/manifest.json={mf_v}"},
            )
        )
    if py_v is not None and init_v != py_v and _init_path(workspace).exists():
        violations.append(
            Violation(
                "VERSION_MISMATCH",
                f"pyproject.toml={py_v} != src/k3dge/__init__.py={init_v}",
                file_path=str(_init_path(workspace)),
                detail={"drift": f"pyproject.toml={py_v} ≠ src/k3dge/__init__.py={init_v}"},
            )
        )
    if py_v is None and mf_v is not None and init_v is not None and init_v != mf_v:
        violations.append(
            Violation(
                "VERSION_MISMATCH",
                f".agent/manifest.json={mf_v} != src/k3dge/__init__.py={init_v}",
                file_path=str(_init_path(workspace)),
                detail={"drift": f".agent/manifest.json={mf_v} ≠ src/k3dge/__init__.py={init_v}"},
            )
        )
    return violations


def _next_version(current: str, part: str, set_version) -> str:
    """算新版本号（set 覆盖 or major/minor/patch 递增）。"""
    if set_version:
        nv = set_version.lstrip("v")
        parse_version(nv)  # validate
        return nv
    major, minor, patch = parse_version(current)
    if part == "major":
        return format_version(major + 1, 0, 0)
    if part == "minor":
        return format_version(major, minor + 1, 0)
    if part == "patch":
        return format_version(major, minor, patch + 1)
    raise ValueError(f"Unknown bump part '{part}': choose major/minor/patch")


def _collect_version_updates(workspace: Path, new_version: str) -> list:
    """准备 (path, new_text)（先算不写，早失败）。"""
    updates: list = []
    p = _pyproject_path(workspace)
    if p.is_file():
        text = _read_utf8(p)
        if _pyproject_version(text) is None:
            # `dynamic = ["version"]` / 无可匹配版本行 ⇒ 与 `get_version`/`validate_versions`
            # 同口径：当作"pyproject 不持版本"跳过，而不是硬抛 RuntimeError（338）
            pass
        else:
            new_text, n = _VERSION_RE.subn(f'version = "{new_version}"', text, count=1)
            if n == 0:
                relaxed = _VERSION_LINE_RELAXED.search(text)
                if not relaxed:
                    raise RuntimeError("Failed to update pyproject.toml version")
                new_text = text[:relaxed.start()] + f'version = "{new_version}"' + text[relaxed.end():]
            updates.append((p, new_text))
    mp = _manifest_path(workspace)
    if mp.is_file():
        data = json.loads(mp.read_text(encoding="utf-8"))
        data["version"] = new_version
        updates.append((mp, json.dumps(data, indent=2, ensure_ascii=False) + "\n"))
    ip = _init_path(workspace)
    if ip.is_file():
        inew, n2 = _INIT_VERSION_RE.subn(f'__version__ = "{new_version}"', ip.read_text(encoding="utf-8"), count=1)
        if n2:
            updates.append((ip, inew))
    return updates


def _apply_version_updates(updates: list) -> None:
    """逐文件原子写；任一失败回滚已写者后 raise。"""
    originals: dict = {}
    try:
        for path, new_content in updates:
            originals[path] = _read_utf8(path)
            _atomic_write(path, new_content)
    except Exception:
        for path, orig in originals.items():
            try:
                _atomic_write(path, orig)
            except Exception:
                pass
        raise


def bump_version(workspace: Path, part: str = "patch", set_version: str | None = None) -> str:
    """Bump SemVer and mirror to all existing version files atomically. Returns new version."""
    current = get_version(workspace)
    if current is None:
        raise FileNotFoundError("No version found in pyproject.toml or .agent/manifest.json")
    new_version = _next_version(current, part, set_version)
    _apply_version_updates(_collect_version_updates(workspace, new_version))
    return new_version


_CT_MAP = {"feat": "Added", "fix": "Fixed", "audit": "Fixed", "docs": "Changed", "chore": "Changed", "refactor": "Changed", "sec": "Security"}
_CC_PREFIX = re.compile(r"^\s*(feat|fix|audit|docs|chore|refactor|perf|sec|security)(\(.+\))?\s*:\s*", re.IGNORECASE)
_PREAMBLE = (
    "# Changelog\n\n"
    "All notable changes to this project will be documented in this file.\n\n"
    "The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),\n"
    "and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).\n\n"
)


def _infer_change_type(body: str, change_type):
    if change_type:
        return change_type
    m = _CC_PREFIX.match(body)
    if not m:
        return change_type
    inferred = m.group(1).lower()
    if inferred == "security":
        return "sec"
    if inferred == "perf":
        return "refactor"
    return inferred


def _insert_version_entry(text: str, entry: str) -> str:
    """新版本放 [Unreleased] 之后、下一版本前；无 Unreleased 则首个 ## [ 前或文件末。"""
    uidx = text.find("## [Unreleased]")
    if uidx != -1:
        nver = text.find("## [", uidx + len("## [Unreleased]"))
        if nver != -1:
            return text[:nver] + entry + text[nver:]
    else:
        idx = text.find("## [")
        if idx != -1:
            return text[:idx] + entry + text[idx:]
    if not text.endswith("\n"):
        text += "\n"
    return text + "\n" + entry


def append_changelog(workspace: Path, new_version: str, notes: str | None = None, change_type: str | None = None) -> Path:
    """Append entry to CHANGELOG.md (Keep a Changelog) and return path."""
    changelog = workspace / "CHANGELOG.md"
    today = datetime.date.today().isoformat()
    header = f"## [{new_version}] - {today}\n"
    body = notes.strip() if notes and notes.strip() else f"- Milestone sealed / version bump to {new_version}."
    change_type = _infer_change_type(body, change_type)
    stripped = body.lstrip()
    if not (stripped.startswith("-") or stripped.startswith("###")):
        body = f"- {body}"
    section = _CT_MAP.get((change_type or "").lower())
    entry = f"{header}\n### {section}\n{body}\n\n" if section else f"{header}\n{body}\n\n"
    if not changelog.exists():
        _atomic_write(changelog, _PREAMBLE + entry)
        return changelog
    _atomic_write(changelog, _insert_version_entry(_read_utf8(changelog), entry))
    return changelog


def consume_unreleased(workspace: Path) -> str:
    """Extract ## [Unreleased] body and atomically clear it for next cycle.

    Returns the stripped body (may be empty string). Keeps the header.
    Used by both CLI and MCP seal to keep changelog generation identical.
    """
    changelog = workspace / "CHANGELOG.md"
    if not changelog.is_file():
        return ""
    try:
        text = _read_utf8(changelog)
    except (OSError, ValueError):
        return ""
    unreleased = "## [Unreleased]"
    idx = text.find(unreleased)
    if idx == -1:
        return ""
    next_idx = text.find("## [", idx + len(unreleased))
    end = next_idx if next_idx != -1 else len(text)
    body = text[idx + len(unreleased):end].strip()
    # Clear body for next cycle (keep header) — atomic via tmp+replace
    new_text = text[: idx + len(unreleased)] + "\n\n" + text[end:].lstrip("\n")
    try:
        _atomic_write(changelog, new_text)
    except Exception:
        # Write failure is non-fatal for seal notes; return body anyway and warn
        import sys

        print(f"[WARN] consume_unreleased: failed to clear Unreleased in {changelog}", file=sys.stderr)
    return body
