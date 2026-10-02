"""Symbol index + controlled search (k3dge where / search).

Replaces bare grep/ls as the Agent's only file-discovery surface (physical isolation:
the Agent never touches find/grep directly). `where` is zero-model, zero-grep name
addressing from a prebuilt index; `search` returns narrow snippets to kill Context
Ping-Pong (no `-C > 3` firehose).
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import sys
import time
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from k3dge.engine import gates

INDEX_REL = "docs/generated/symbol-index.json"
_MAX_CONTEXT = 3
#: 兜底扫描（rg 缺席）的遍历预算与单行探测上限（320）
_FALLBACK_BUDGET_SEC = 20.0
_FALLBACK_LINE_CAP = 4000


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
    except Exception as exc:
        # manifest 坏了（形状错/键改名）不能静默回落 `src/<pkg>`：回落面与声明面不一致，
        # 搜到的与闸看的不是同一组文件（ocr2-077）。出声，让调用方知道在用兜底。
        import sys as _sys

        print(f"[search] WARN: manifest 不可用（{exc}）⇒ 回落 src/<pkg> 发现（可能与声明域不一致）",
              file=_sys.stderr)
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
    index = build_symbol_index(workspace)
    if not index and out.is_file():
        # 构建为空但已有**非空**索引 ⇒ 多为 manifest 解析失败放大（坏配置把提交产物清空＝数据丢失）。
        # 保留旧索引（随后 `check` 的 SYMBOL_INDEX_STALE 会把它作为红暴露，不静默）(ocr-110)。
        try:
            existing = json.loads(out.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            existing = {}
        if existing:
            return out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_index_meta(workspace)
    return out


#: 符号索引的**本地签名**侧车（gitignored `.k3dge/`）：只做"这版索引对得上这棵树吗"的缓存，
#: 不是事实源——缺了就走一次全量重建（幂等），`check` 的 `SYMBOL_INDEX_STALE` 仍是权威判据。
INDEX_META_REL = ".k3dge/symbol-index.meta.json"

def index_meta_path(workspace: Path) -> Path:
    return Path(workspace) / INDEX_META_REL


def _tree_signature(workspace: Path) -> dict:
    """一次遍历同时拿到**文件集**（增删/重命名）与**最新 mtime**（内容改动）。"""
    names: list = []
    newest = 0.0
    for src in _domain_src_dirs(workspace):
        for dirpath, dirnames, filenames in os.walk(src):
            dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__", "node_modules")]
            for fn in filenames:
                if not fn.endswith(".py"):
                    continue
                fp = os.path.join(dirpath, fn)
                try:
                    st = os.stat(fp)
                except OSError:
                    continue
                names.append(os.path.relpath(fp, workspace))
                newest = max(newest, st.st_mtime)
    blob = "\n".join(sorted(names))
    return {
        "files": len(names),
        "names_sha1": hashlib.sha1(blob.encode("utf-8", "surrogatepass")).hexdigest(),
        "newest_mtime": newest,
    }


def write_index_meta(workspace: Path) -> None:
    """索引写成后落签名（与索引同处刷新，避免"索引新、签名旧"的假陈旧）。"""
    meta = index_meta_path(workspace)
    try:
        meta.parent.mkdir(parents=True, exist_ok=True)
        meta.write_text(json.dumps(_tree_signature(workspace), sort_keys=True) + "\n",
                        encoding="utf-8")
    except OSError:
        pass


def _is_stale_cheaply(workspace: Path, index: Path) -> bool:
    """廉价陈旧判定：树签名与索引签名不符、或任一 src 文件比索引新 ⇒ 重建。

    权威判据是 `check` 的 `SYMBOL_INDEX_STALE`（重建后逐字比）；这里只是让 `k3dge where`
    **不要**拿旧索引给出错的 file:line（旧行为只在文件缺失时重建 ⇒ 代码写完没跑 `k3dge index`
    就会静默返回过期位置）。

    删除/重命名不会让**残留** .py 的 mtime 变新 ⇒ 旧实现判"不陈旧"，`where` 继续返回已不存在
    的 `file:line`（幽灵坐标，315）；故判定加**文件集签名**（`.k3dge/` 侧车，gitignored 本地缓存）。
    一趟 `os.walk` 同时得名与 mtime，不再 `rglob`+逐文件 `stat()` 两趟。
    """
    try:
        idx_st = index.stat()
    except OSError:
        return True
    sig = _tree_signature(workspace)          # 一趟：文件集 + 最新 mtime（缓存Freshness判定不安全：内容编辑不改索引 mtime）
    try:
        meta = json.loads(index_meta_path(workspace).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True          # 无签名 ⇒ 重建（重建即补签名），不猜"应该不陈旧"
    if (meta.get("names_sha1") != sig["names_sha1"]
            or meta.get("files") != sig["files"]):
        return True          # 有文件被删/改名/新增
    return sig["newest_mtime"] > idx_st.st_mtime


class IndexUnavailable(RuntimeError):
    """索引**不可用**（损坏/读不出/形状不对），与"这个符号不存在"是两件事。

    旧实现降级成 `return {}` ⇒ CLI 统一喊 `no symbol …(run 'k3dge index')`：坏索引被读成
    "该公开符号不存在"，Agent 据此判"没有这个东西"（317）。
    """


def _load_index(workspace: Path) -> Dict[str, List[dict]]:
    p = index_path(workspace)
    if not p.is_file() or _is_stale_cheaply(workspace, p):
        write_symbol_index(workspace)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IndexUnavailable(f"符号索引读不出（{p}：{type(exc).__name__}: {exc}）") from exc
    if not isinstance(data, dict):
        raise IndexUnavailable(f"符号索引顶层不是对象（{p}）")
    return data


def where(workspace: Path, symbol: str) -> List[Location]:
    """Deterministic name -> file:line. No grep discovery, no model judgment.

    Raises `IndexUnavailable` when the index itself is broken（区别于"查无此符号"）。
    """
    index = _load_index(workspace)
    hits = index.get(symbol) or []
    out: List[Location] = []
    for h in hits:
        if isinstance(h, dict) and h.get("file"):
            out.append(Location(file=str(h["file"]), line=h.get("line")))
    return out


def _snippet_window(path: Path, line_no: int, context: int, cap: int = _MAX_CONTEXT) -> str:
    context = max(0, min(context, cap))
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    lo = max(0, line_no - 1 - context)
    hi = min(len(lines), line_no + context)
    window = lines[lo:hi]
    text = "\n".join(window)
    if len(text) > 240:
        text = text[:240].rstrip() + "…"
    return text


def _run_ripgrep(workspace: Path, query: str) -> Optional[List[str]]:
    try:
        res = subprocess.run(
            ["rg", "-n", "--with-filename", "--no-heading", "--hidden",
             # `--hidden` 会把 `.git` 也拉进来，而兜底路径明确跳 `.git` ⇒ 装不装 rg 命中集不同（319）
             "--glob", "!docs/generated/**", "--glob", "!.git/**", "-e", query],
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
    # 兜底**没有** rg 那条 30s 超时（`_run_ripgrep` 超时也回 None ⇒ 立刻接一次无截止的全仓扫描，
    # `re` 也没有回溯保险）⇒ 加遍历预算：到点就停并出声，宁可少给也不挂死（320）。
    deadline = time.monotonic() + _FALLBACK_BUDGET_SEC
    skip_dirs = {".git", ".venv", "venv", "node_modules", "__pycache__"}
    ignored = _gitignored_prefixes(workspace)
    truncated = False
    for path in workspace.rglob("*"):
        if time.monotonic() > deadline:
            truncated = True
            break
        rel_parts = path.relative_to(workspace).parts
        if path.is_symlink():
            # rg 默认不跟随符号链接（需 `--follow`）：`link -> /etc/passwd` 在兜底路径会被整读，
            # 既与 rg 语义相反又能越界读仓外（318）
            continue
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
            probe = line if len(line) <= _FALLBACK_LINE_CAP else line[:_FALLBACK_LINE_CAP]
            if (rx.search(probe) if rx is not None else query in probe):
                out.append(f"{rel}:{i}:{line}")
    if truncated:
        print(f"[SEARCH] WARN: 兜底扫描到 {_FALLBACK_BUDGET_SEC}s 预算上限即停 ⇒ 结果可能不完整",
              file=sys.stderr)
    return out


def search(
    workspace: Path,
    query: str,
    *,
    snippet: bool = True,
    context: int = 2,
    max_snippet: int = 240,
) -> List[Location]:
    """Controlled search. Returns path:line[: snippet].

    窗口上限来自 `gates.get(workspace, "search", "context_max")`（`.agent/pipeline.toml` 可覆盖），
    `_MAX_CONTEXT` 只是**那张表的缺省**，不是硬钳（463 的文档漂移）。
    """
    raw = _run_ripgrep(workspace, query)
    if raw is None:
        raw = _python_search(workspace, query)
    cap = int(gates.get(workspace, "search", "context_max"))
    parsed = _split_hit_line
    context = max(0, min(context, cap))  # 单源 context_max；_snippet_window 按同一 cap 钳（不硬编 3）
    locs: List[Location] = []
    for ln in raw:
        # format: file:line:content —— POSIX 文件名合法可含 `:` ⇒ 按 `:` 硬切会把路径截到
        # **第一个**冒号并丢行号（静默给错坐标）。用贪婪正则锚定"最后一段数字"即行号（321）。
        head, line_no = parsed(ln)
        if line_no is None:
            locs.append(Location(file=head or ln))
            continue
        snippet_text: Optional[str] = None
        if snippet:
            snip = _snippet_window(workspace / head, line_no, context, cap=cap)
            snippet_text = snip[:max_snippet]
        locs.append(Location(file=head, line=line_no, snippet=snippet_text))
    return locs


def _split_hit_line(line: str) -> Tuple[str, Optional[int]]:
    """`file:line:content` → `(file, line)`；无行号 → `(整串, None)`。

    取**第一个** `:<digits>:`（非贪婪）：行号是生产方紧跟文件名的第二个字段，内容里
    的 `:数字:`（如 `ratio = 4:2:1`、时间 `12:30`）不得参与。贪婪取最后一个会把内容
    里的数字当行号、把路径切断（ocr2-004）。Windows 盘符（`C:\…`）不受影响：`C` 后
    跟的不是数字，仍会推进到真正的行号段（321 的初衷仍成立）。
    """
    m = re.match(r"^(?P<f>.+?):(?P<l>\d+):", line)
    if m:
        return m.group("f").replace("\\", "/"), int(m.group("l"))
    m2 = re.match(r"^(?P<f>.+?):(?P<l>\d+)$", line)
    if m2:
        return m2.group("f").replace("\\", "/"), int(m2.group("l"))
    return line, None
    return locs
