"""Manifest loading and domain routing."""

from __future__ import annotations

import fnmatch
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

MANIFEST_PATH = ".agent/manifest.json"

# POSIX Path.is_absolute() is false for Windows drive paths; reject them anyway.
_WINDOWS_ABS = re.compile(r"^[A-Za-z]:|^//")


class ManifestError(ValueError):
    pass


def _require_relative_path(label: str, val: Any) -> str:
    """Return a posix-relative path or raise ManifestError. Rejects abs, NUL, and `..`."""
    if not isinstance(val, str):
        raise ManifestError(f"{label} must be a string, got {type(val).__name__}")
    if "\x00" in val:
        raise ManifestError(f"{label} must not contain NUL")
    posix = val.replace("\\", "/")
    if (
        not posix
        or posix.startswith("/")
        or Path(posix).is_absolute()
        or _WINDOWS_ABS.match(posix)
    ):
        raise ManifestError(f"{label} must be relative, got '{val}'")
    if ".." in Path(posix).parts:
        raise ManifestError(f"{label} must not contain '..', got '{val}'")
    return posix


def _parse_ignore(data: Dict[str, Any]) -> List[str]:
    ignore = data.get("ignore", [])
    if ignore is None:
        ignore = []
    if not isinstance(ignore, list) or not all(isinstance(x, str) for x in ignore):
        raise ManifestError("'ignore' must be a list of strings")
    return ignore


def _validate_domain(domain: str, cfg, domains: dict) -> None:
    """验证 + 就地归一化单域 cfg（路径、depends_on）。"""
    if not isinstance(cfg, dict):
        raise ManifestError(f"domain '{domain}' config must be a dict, got {type(cfg).__name__}")
    for key in ("src", "spec", "tests"):
        if key not in cfg:
            continue
        val = cfg[key]
        if val in (None, ""):
            cfg[key] = ""      # 显式空/缺省 ⇒ 归一成空串（下游 cfg.get(key, "") 拿到 ""，不炸）
            continue
        # **不看真假**：`false`/`0`/`[]` 等假值非字符串也要经校验（否则绕过 → 运行期 AttributeError，ocr-080）。
        cfg[key] = _require_relative_path(f"domain '{domain}' {key}", val)
    dep = cfg.get("depends_on", [])
    if dep is None:
        dep = []
    if not isinstance(dep, list) or not all(isinstance(x, str) for x in dep):
        raise ManifestError(f"domain '{domain}' depends_on must be a list of strings")
    for x in dep:
        if x not in domains:
            raise ManifestError(f"domain '{domain}' depends_on references unknown domain '{x}'")
    cfg["depends_on"] = dep


class Manifest:
    def __init__(self, data: Dict[str, Any]) -> None:
        if not isinstance(data, dict):
            raise ManifestError(
                f"{MANIFEST_PATH} must contain a JSON object, got {type(data).__name__}"
            )
        self.data = data
        self.name: str = data.get("name", "project")
        if "self_hosting" in data and not isinstance(data["self_hosting"], bool):
            raise ManifestError("'self_hosting' must be a boolean")
        self.self_hosting: bool = bool(data.get("self_hosting", False))
        self.package_root: str = _require_relative_path("package_root", data.get("package_root", "src"))
        self.ignore: List[str] = _parse_ignore(data)
        tmpl = data.get("test_command_template")
        if tmpl is not None and not isinstance(tmpl, str):
            raise ManifestError("'test_command_template' must be a string")
        self.domains: Dict[str, Dict[str, str]] = data.get("domains", {})
        if not isinstance(self.domains, dict):
            raise ManifestError("'domains' must be an object")
        for domain, cfg in self.domains.items():
            _validate_domain(domain, cfg, self.domains)

    def depends_on(self, domain: str) -> List[str]:
        """Domains whose contract this domain is allowed to import (ADR-0001 decision 6)."""
        return list(self.domains.get(domain, {}).get("depends_on", []))

    @classmethod
    def load(cls, workspace: Path) -> "Manifest":
        path = workspace / MANIFEST_PATH
        if not path.exists():
            return cls({"domains": {}, "ignore": []})
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ManifestError(f"invalid JSON in {MANIFEST_PATH}: {exc}") from exc
        except OSError as exc:
            raise ManifestError(f"cannot read {MANIFEST_PATH}: {exc}") from exc
        return cls(data)

    def domain_for_src(self, path: str) -> Optional[str]:
        path = path.replace("\\", "/")
        for domain, cfg in self.domains.items():
            src = cfg.get("src", "").replace("\\", "/")
            if src and (path == src or path.startswith(src.rstrip("/") + "/")):
                return domain
        return None

    def domain_for_spec(self, path: str) -> Optional[str]:
        path = path.replace("\\", "/")
        for domain, cfg in self.domains.items():
            if cfg.get("spec", "").replace("\\", "/") == path:
                return domain
        return None

    def src_path(self, domain: str) -> Optional[str]:
        return self.domains.get(domain, {}).get("src")

    def spec_path(self, domain: str) -> Optional[str]:
        return self.domains.get(domain, {}).get("spec")

    def is_ignored(self, path: str) -> bool:
        if not self.ignore:
            return False
        path_posix = path.replace("\\", "/")
        p = Path(path_posix)
        p_name = p.name
        for pattern in self.ignore:
            if not pattern:
                continue
            pat = pattern.replace("\\", "/")
            if (
                fnmatch.fnmatch(path_posix, pat)
                or fnmatch.fnmatch(p_name, pat)
                or p.match(pat)
            ):
                return True
        return False

    def under_package_root(self, path: str) -> bool:
        path = path.replace("\\", "/")
        root = self.package_root.replace("\\", "/").rstrip("/")
        return path == root or path.startswith(root + "/")
