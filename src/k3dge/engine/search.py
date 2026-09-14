"""Symbol index + controlled search (k3dge where / search).

Replaces bare grep/ls as the Agent's only file-discovery surface (physical isolation:
the Agent never touches find/grep directly). `where` is zero-model, zero-grep name
addressing from a prebuilt index; `search` returns narrow snippets to kill Context
Ping-Pong (no `-C > 3` firehose).
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from k3dge.engine import gates

INDEX_REL = "docs/generated/symbol-index.json"
_MAX_CONTEXT = 3


@dataclass(frozen=True)
class Location:
    file: str
    line: Optional[int] = None
    snippet: Optional[str] = None

    def render(self) -> str:
        if self.line is None:
            return self.file
        if self.snippet:
            return f"{self.file}:{self.line}: {self.snippet}"
        return f"{self.file}:{self.line}"


def index_path(workspace: Path) -> Path:
    return workspace / INDEX_REL


def _domain_src_dirs(workspace: Path) -> List[Path]:
    from k3dge.engine.manifest import Manifest

    dirs: List[Path] = []
    try:
        manifest = Manifest.load(workspace)
        for dom in manifest.domains.values():
            src = dom.get("src")
            if src:
                p = workspace / src
                if p.is_dir():
                    dirs.append(p)
    except Exception:
        pass
    if not dirs:
        # Fallback: discover any src/<pkg> package tree (no manifest present).
        src = workspace / "src"
        if src.is_dir():
            for child in src.iterdir():
                if child.is_dir() and (child / "__init__.py").exists():
                    dirs.append(child)
    return dirs


def build_symbol_index(workspace: Path) -> Dict[str, List[dict]]:
    """Map top-level public symbol -> [{file, line}] across all domain src trees."""
    index: Dict[str, List[dict]] = {}
    for src_dir in _domain_src_dirs(workspace):
        for path in sorted(src_dir.rglob("*.py")):
            if path.is_symlink() or not path.is_file():
                continue
            if any(part in (".git", "__pycache__") for part in path.parts):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError, OSError):
                continue
            rel = str(path.relative_to(workspace)).replace("\\", "/")
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if node.name.startswith("_"):
                        continue
                    index.setdefault(node.name, []).append({"file": rel, "line": node.lineno})
    return index


def write_symbol_index(workspace: Path) -> Path:
    out = index_path(workspace)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build_symbol_index(workspace), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def _load_index(workspace: Path) -> Dict[str, List[dict]]:
    p = index_path(workspace)
    if not p.is_file():
        write_symbol_index(workspace)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def where(workspace: Path, symbol: str) -> List[Location]:
    """Deterministic name -> file:line. No grep discovery, no model judgment."""
    index = _load_index(workspace)
    hits = index.get(symbol, [])
    return [Location(file=h["file"], line=h.get("line")) for h in hits]


def _snippet_window(path: Path, line_no: int, context: int, cap: int = _MAX_CONTEXT) -> str:
    context = max(0, min(context, cap))
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    lo = max(0, line_no - 1 - context)
    hi = min(len(lines), line_no + context)
# k3dit:fixed code-5 验证：`_snippet_window`(search.py:113) 用 `lo=max(0,line_no-1-context)`(:119) 切片 `lines[lo:hi]`(:122)，匹配行前 context 行入窗；调用点 search.py:225 传同 cap，tests/unit/engine/test_search.py 覆盖。若窗口仍从 line_no-1 起、丢失前文，则没修对。
    window = lines[lo:hi]
    text = "\n".join(window)
    if len(text) > 240:
        text = text[:240].rstrip() + "…"
    return text


def _run_ripgrep(workspace: Path, query: str) -> Optional[List[str]]:
    try:
        res = subprocess.run(
            ["rg", "-n", "--with-filename", "--no-heading", "--hidden", "--glob", "!docs/generated/**", query],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if res.returncode not in (0, 1):
        return None
    return [ln for ln in res.stdout.splitlines() if ln.strip()]


def _gitignored_prefixes(workspace: Path) -> set:
    """git 忽略的路径前缀（`.gitignore`/`.git/info/exclude`），供兜底对齐 rg。

    rg 默认尊重 `.gitignore`，兜底路径必须同口径，否则无 rg 时命中集多出被忽略文件
    （code-7 残留）。非 git 仓 / git 缺席 ⇒ 空集（退化为原行为）。"""
    try:
        r = subprocess.run(
            ["git", "-C", str(workspace), "ls-files", "--others", "--ignored",
             "--exclude-standard", "--directory"],
            capture_output=True, text=True)
    except OSError:
        return set()
    if r.returncode != 0:
        return set()
    return {ln.strip().rstrip("/") for ln in r.stdout.splitlines() if ln.strip()}


def _python_search(workspace: Path, query: str) -> List[str]:
    """rg 缺席时的兜底，刻意对齐 rg 语义：query 当正则（非法正则回退子串）、
    跳过 .git/.venv/venv/node_modules/__pycache__/docs/generated 与 `.gitignore` 项
    （code-7：原纯子串 + 整扫 .venv/node_modules + 不读 .gitignore 使命中集随 rg 装否而变）。"""
    out: List[str] = []
    try:
        rx = re.compile(query)
    except re.error:
        rx = None
    skip_dirs = {".git", ".venv", "venv", "node_modules", "__pycache__"}
    ignored = _gitignored_prefixes(workspace)
    for path in workspace.rglob("*"):
        rel_parts = path.relative_to(workspace).parts
        if not path.is_file() or set(rel_parts) & skip_dirs or rel_parts[:2] == ("docs", "generated"):
            continue
        rel = str(path.relative_to(workspace)).replace("\\", "/")
        if any(rel == p or rel.startswith(p + "/") for p in ignored):
            continue
        try:
            if path.stat().st_size > 1_000_000:   # 体积闸：超大文件不整读（A-2）
                continue
        except OSError:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if (rx.search(line) if rx is not None else query in line):
                out.append(f"{rel}:{i}:{line}")
    return out


def search(
    workspace: Path,
    query: str,
    *,
    snippet: bool = True,
    context: int = 2,
    max_snippet: int = 240,
) -> List[Location]:
    """Controlled search. Returns path:line[: snippet]. Snippet window is clamped to
    _MAX_CONTEXT lines so a query never floods the context window."""
    raw = _run_ripgrep(workspace, query)
    if raw is None:
        raw = _python_search(workspace, query)
    cap = int(gates.get(workspace, "search", "context_max"))
    context = max(0, min(context, cap))  # 单源 context_max；_snippet_window 按同一 cap 钳（不硬编 3）
    locs: List[Location] = []
    for ln in raw:
        # format: file:line:content
        head, sep, content = ln.partition(":")
        if not sep:
            locs.append(Location(file=ln))
            continue
        line_no_str, _, content = content.partition(":")
        try:
            line_no = int(line_no_str)
        except ValueError:
            locs.append(Location(file=head))
            continue
        snippet_text: Optional[str] = None
        if snippet:
            snip = _snippet_window(workspace / head, line_no, context, cap=cap)
            snippet_text = snip[:max_snippet]
        locs.append(Location(file=head, line=line_no, snippet=snippet_text))
    return locs
