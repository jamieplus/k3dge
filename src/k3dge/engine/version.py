"""Version management: single source in pyproject.toml, mirrored to manifest and __init__."""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path
from typing import Tuple

from k3dge.engine.models import Violation

_VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)
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
        # package_root is the package directory itself (e.g. src/k3dge) for k3dge;
        # downstream may be src or src/<project>
        candidate = workspace / manifest.package_root / "__init__.py"
        if candidate.is_file():
            return candidate
        # Fallback: package_root may be a parent (e.g. src) → try src/<name>/__init__.py via manifest name
        name = manifest.data.get("name")
        if name and manifest.package_root.replace("\\", "/").rstrip("/") == "src":
            alt = workspace / "src" / name / "__init__.py"
            if alt.is_file():
                return alt
    except Exception:
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
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def get_pyproject_version(workspace: Path) -> str | None:
    p = _pyproject_path(workspace)
    if not p.is_file():
        return None
    m = _VERSION_RE.search(_read_utf8(p))
    return m.group(1) if m else None


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
    canonical = py_v if py_v is not None else mf_v
    if canonical is None:
        return []
    violations: list[Violation] = []
    if py_v is not None and mf_v != py_v:
        violations.append(
            Violation(
                "VERSION_MISMATCH",
                f"version drift: pyproject.toml={py_v} vs .agent/manifest.json={mf_v}; run 'k3dge version bump' or 'k3dge sync'",
                file_path=str(_manifest_path(workspace)),
            )
        )
    if py_v is not None and init_v != py_v and _init_path(workspace).exists():
        violations.append(
            Violation(
                "VERSION_MISMATCH",
                f"version drift: pyproject.toml={py_v} vs src/k3dge/__init__.py={init_v}; run 'k3dge version bump'",
                file_path=str(_init_path(workspace)),
            )
        )
    if py_v is None and mf_v is not None and init_v is not None and init_v != mf_v:
        violations.append(
            Violation(
                "VERSION_MISMATCH",
                f"version drift: .agent/manifest.json={mf_v} vs src/k3dge/__init__.py={init_v}; run 'k3dge version bump'",
                file_path=str(_init_path(workspace)),
            )
        )
    return violations


def bump_version(workspace: Path, part: str = "patch", set_version: str | None = None) -> str:
    """Bump SemVer and mirror to all existing version files atomically. Returns new version."""
    current = get_version(workspace)
    if current is None:
        raise FileNotFoundError("No version found in pyproject.toml or .agent/manifest.json")
    if set_version:
        new_version = set_version.lstrip("v")
        parse_version(new_version)  # validate
    else:
        major, minor, patch = parse_version(current)
        if part == "major":
            major += 1
            minor = 0
            patch = 0
        elif part == "minor":
            minor += 1
            patch = 0
        elif part == "patch":
            patch += 1
        else:
            raise ValueError(f"Unknown bump part '{part}': choose major/minor/patch")
        new_version = format_version(major, minor, patch)

    # Prepare new contents first (no writes yet) to catch errors early
    updates: list[tuple[Path, str]] = []
    p = _pyproject_path(workspace)
    if p.is_file():
        text = p.read_text(encoding="utf-8")
        new_text, n = _VERSION_RE.subn(f'version = "{new_version}"', text, count=1)
        if n == 0:
            raise RuntimeError("Failed to update pyproject.toml version")
        updates.append((p, new_text))
    mp = _manifest_path(workspace)
    if mp.is_file():
        data = json.loads(mp.read_text(encoding="utf-8"))
        data["version"] = new_version
        updates.append((mp, json.dumps(data, indent=2, ensure_ascii=False) + "\n"))
    ip = _init_path(workspace)
    if ip.is_file():
        itext = ip.read_text(encoding="utf-8")
        inew, n2 = _INIT_VERSION_RE.subn(f'__version__ = "{new_version}"', itext, count=1)
        if n2:
            updates.append((ip, inew))

    # Atomic write with rollback on failure (U-05)
    originals: dict[Path, str] = {}
    try:
        for path, new_content in updates:
            originals[path] = path.read_text(encoding="utf-8")
            path.write_text(new_content, encoding="utf-8")
    except Exception:
        # Rollback any already-written files
        for path, orig in originals.items():
            try:
                path.write_text(orig, encoding="utf-8")
            except Exception:
                pass
        raise

    return new_version


def append_changelog(workspace: Path, new_version: str, notes: str | None = None) -> Path:
    """Append entry to CHANGELOG.md (Keep a Changelog) and return path."""
    changelog = workspace / "CHANGELOG.md"
    today = datetime.date.today().isoformat()
    header = f"## [{new_version}] - {today}\n"
    body = notes.strip() if notes and notes.strip() else f"- Milestone sealed / version bump to {new_version}."
    # Ensure body is a list
    if not body.lstrip().startswith("-"):
        body = f"- {body}"
    entry = f"{header}\n{body}\n\n"

    if not changelog.exists():
        # Create with Keep a Changelog preamble
        preamble = (
            "# Changelog\n\n"
            "All notable changes to this project will be documented in this file.\n\n"
            "The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),\n"
            "and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).\n\n"
        )
        _atomic_write(changelog, preamble + entry)
        return changelog

    text = _read_utf8(changelog)
    # Keep a Changelog: new version goes after [Unreleased] block, before next version
    unreleased_idx = text.find("## [Unreleased]")
    if unreleased_idx != -1:
        next_ver_idx = text.find("## [", unreleased_idx + len("## [Unreleased]"))
        if next_ver_idx != -1:
            new_text = text[:next_ver_idx] + entry + text[next_ver_idx:]
        else:
            if not text.endswith("\n"):
                text += "\n"
            new_text = text + "\n" + entry
    else:
        idx = text.find("## [")
        if idx != -1:
            new_text = text[:idx] + entry + text[idx:]
        else:
            if not text.endswith("\n"):
                text += "\n"
            new_text = text + "\n" + entry
    _atomic_write(changelog, new_text)
    return changelog
