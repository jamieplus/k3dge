"""Version management: single source in pyproject.toml, mirrored to manifest and __init__."""

from __future__ import annotations

import datetime
import json
import re
import sys
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


def _sub_version_in_project(text: str, new_version: str) -> tuple:
    """只在 `[project]` 段内替换首个 `version = "…"`，返回 `(new_text, n)`。

    全局首个版本行可能是别的表（如 `[tool.x]` 在前）；守卫只认 `[project].version`，
    写必须与读同口径，否则改错地方（ocr2-087）。找不到 `[project]` 段或段内无版本行 ⇒ `(text, 0)`。
    """
    lines = text.splitlines(keepends=True)
    in_project, start, end = False, -1, len(lines)
    for i, ln in enumerate(lines):
        _s = ln.strip()
        if _s.startswith("["):
            if re.match(r"^\[project\]\s*(#.*)?$", _s):
                in_project, start = True, i
            elif in_project:
                end = i
                break
    if start < 0:
        return text, 0
    seg = "".join(lines[start + 1:end])
    new_seg, n = _VERSION_RE.subn(f'version = "{new_version}"', seg, count=1)
    if n == 0:
        # 宽容形（缩进/单引号）也**只在 [project] 段内**替换：全文件搜会命中别的表的
        # `version = '…'`（ocr2-087 同族，写读须同口径）。保留行首缩进（ocr2-538）。
        def _repl(m) -> str:
            g = m.group(0)
            lead = g[:len(g) - len(g.lstrip(" \t"))]
            return f'{lead}version = "{new_version}"'

        new_seg, n = _VERSION_LINE_RELAXED.subn(_repl, seg, count=1)
    if n == 0:
        return text, 0
    return "".join(lines[:start + 1]) + new_seg + "".join(lines[end:]), n


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
        _proj = data.get("project")
        # `project` 是合法 TOML 但非表（标量/数组）时 `(.. or {}).get` 抛 AttributeError（ocr2-085）。
        v = _proj.get("version") if isinstance(_proj, dict) else None
        return str(v) if isinstance(v, str) else None
    return _pyproject_version_relaxed(text)


def _pyproject_version_relaxed(text: str) -> str | None:
    """无 tomllib（3.10）的回退解析：单引号/缩进都认，从 `[project]` 段取 version。

    段界与段头用**同一遍** `finditer` 求（ocr2-327）：`re.split`（段头须独占一行）与
    `re.findall`（无行尾锚、会匹配 `[[array]]`）两套判据混用会让 `zip` 错位、从错的段取版本。
    """
    m = _VERSION_INLINE_RE.search(text)
    if m:
        return m.group(1) or m.group(2)
    heads = list(re.finditer(r"(?m)^\s*\[([^\]]*)\]\s*$", text))
    for i, hm in enumerate(heads):
        if hm.group(1).strip() != "project":
            continue
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        lm = _VERSION_LINE_RELAXED.search(text[hm.end():end])
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
        # `[]`/`"x"`/`1`/`null` 都是合法 JSON 但无 `.get`：AttributeError 不在捕获元组里会裸抛（ocr2-086）。
        return data.get("version") if isinstance(data, dict) else None
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
    violations: list[Violation] = []
    # 非 UTF-8 / 不可读的版本文件不得让闸裸抛（ocr2-328）：降成一条"无法判定"违规。
    try:
        py_v = get_pyproject_version(workspace)
    except (OSError, ValueError) as exc:
        return [Violation("VERSION_MISMATCH", f"版本闸无法判定：pyproject.toml {exc}",
                          file_path=str(_pyproject_path(workspace)), detail={"drift": str(exc)})]
    try:
        init_v = get_init_version(workspace)
    except (OSError, ValueError) as exc:
        return [Violation("VERSION_MISMATCH", f"版本闸无法判定：__init__.py {exc}",
                          file_path=str(_init_path(workspace)), detail={"drift": str(exc)})]
    mf_v = get_manifest_version(workspace)
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
            # 写目标必须锁定在 `[project]` 段内：全局首个 `version = "…"` 可能是别的表
            # （如 `[tool.x]` 在 `[project]` 之前），守卫（`_pyproject_version`）只认
            # `[project].version`，写错地方会改掉无关版本（ocr2-087）。
            new_text, n = _sub_version_in_project(text, new_version)
            if n == 0:
                # 段内已含宽容形替换；到这里只剩**行内表** `project = { … version = "…" }`
                # （合法 TOML，读侧认）——写侧必须同口径，否则 bump 抛 RuntimeError（ocr2-538）。
                inline = _VERSION_INLINE_RE.search(text)
                if inline:
                    if inline.group(1) is not None:
                        s, e = inline.span(1)
                    else:
                        s, e = inline.span(2)
                    new_text = text[:s] + new_version + text[e:]
                else:
                    raise RuntimeError("Failed to update pyproject.toml version")
            updates.append((p, new_text))
    mp = _manifest_path(workspace)
    if mp.is_file():
        # 与 manifest 读侧同口径：`_read_utf8`（非 UTF-8 ⇒ ValueError）+ 顶层须是对象；
        # 裸 `read_text`/item assignment 会以 UnicodeDecodeError/TypeError 半途崩（ocr2-329）。
        data = json.loads(_read_utf8(mp))
        if not isinstance(data, dict):
            raise ValueError(f"{mp.name} 顶层不是对象（{type(data).__name__}）⇒ 版本闸无法判定")
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
            except Exception as rb_exc:
                # 恢复动作本身失败**恰恰最需要暴露**：静默 ⇒ 调用方只看到主异常，
                # 不知道哪个文件仍停在半新半旧（469）
                print(f"[version] WARN: 回滚 {path} 失败（{type(rb_exc).__name__}: {rb_exc}）"
                      "⇒ 该文件仍是本轮新内容，请手工核对", file=sys.stderr)
        raise


def bump_version(workspace: Path, part: str = "patch", set_version: str | None = None) -> str:
    """Bump SemVer and mirror to all existing version files atomically. Returns new version."""
    current = get_version(workspace)
    if current is None:
        raise FileNotFoundError("No version found in pyproject.toml or .agent/manifest.json")
    new_version = _next_version(current, part, set_version)
    _apply_version_updates(_collect_version_updates(workspace, new_version))
    return new_version


#: conventional 前缀 → Keep a Changelog 小节。**与 `changelog._RANGE_TYPES` 同口径**
#: （`perf` 走 Changed：`_infer_change_type` 把 perf 归 refactor，旧表里没有 perf ⇒ 两处漂移，410）
_CT_MAP = {"feat": "Added", "fix": "Fixed", "audit": "Fixed", "docs": "Changed",
           "chore": "Changed", "refactor": "Changed", "perf": "Changed", "sec": "Security"}
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
    except (OSError, ValueError) as exc:
        # 读不出 ≠ Unreleased 为空：调用方（CLI/MCP seal）会把它当发布说明，静默即无说明的发布。
        print(f"[WARN] consume_unreleased: CHANGELOG.md 不可读（{type(exc).__name__}）⇒ 视为空发布说明",
              file=sys.stderr)
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
        print(f"[WARN] consume_unreleased: failed to clear Unreleased in {changelog}", file=sys.stderr)
    return body
