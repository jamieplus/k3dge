"""L1 contract drift detection: public interface -> content hash."""

from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path
from typing import List, Optional, Tuple

INTERFACE_START = "<!-- k3dge:interfaces-start -->"
INTERFACE_END = "<!-- k3dge:interfaces-end -->"


class _ExtractError(RuntimeError):
    """A domain source file could not be parsed for its public interface."""


def _ann(node: Optional[ast.AST]) -> str:
    text = ast.unparse(node) if node is not None else ""
    # 接口分隔符转义放在**公共渲染处**：注释/默认值/返回类型/装饰器里若含字面量标记
    # （如 `Literal["<!-- k3dge:interfaces-start -->"]`）也会截断 spec 接口块（ocr-058）。
    for marker in (INTERFACE_START, INTERFACE_END):
        if marker in text:
            text = text.replace(marker, marker.replace("-", "\\x2d"))
    return text


def _fmt_value(node: Optional[ast.AST]) -> str:
    """Rendered constant value with interface delimiters escaped（转义现由 `_ann` 统一负责）。"""
    return _ann(node)


def _fmt_arg(arg: ast.arg) -> str:
    ann = f": {_ann(arg.annotation)}" if arg.annotation else ""
    return f"{arg.arg}{ann}"


def _fmt_args(args: ast.arguments) -> str:
    parts: List[str] = []
    # posonlyargs + args share defaults (last N of all_pos)
    posonly = list(args.posonlyargs)
    all_pos = posonly + list(args.args)
    defaults = list(args.defaults)
    num_no_default = len(all_pos) - len(defaults)
    for i, arg in enumerate(all_pos):
        s = _fmt_arg(arg)
        if i >= num_no_default:
            s += f"={_ann(defaults[i - num_no_default])}"
        parts.append(s)
        if posonly and i == len(posonly) - 1:
            parts.append("/")
    if args.vararg is not None:
        parts.append(f"*{_fmt_arg(args.vararg)}")
    elif args.kwonlyargs:
        # bare * to separate pos-only/positional from kwonly when no *args
        parts.append("*")
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        s = _fmt_arg(arg)
        if default is not None:
            s += f"={_ann(default)}"
        parts.append(s)
    if args.kwarg is not None:
        parts.append(f"**{_fmt_arg(args.kwarg)}")
    return ", ".join(parts)


_SIGNIFICANT_DECORATORS = {
    "property",
    "classmethod",
    "staticmethod",
    "abstractmethod",
    "final",
    "cached_property",
}


def _fmt_decorators(node: ast.FunctionDef | ast.AsyncFunctionDef, indent: str = "") -> str:
    lines = []
    for dec in node.decorator_list:
        name = _ann(dec)
        base_name = name.split("(")[0].split(".")[-1]
        if base_name in _SIGNIFICANT_DECORATORS:
            lines.append(f"{indent}@{name}")
    return "\n".join(lines) + ("\n" if lines else "")


def _doc_first_line(node: ast.AST) -> Optional[str]:
    """First line of a docstring, or None. Used only for display docs (never for hashing)."""
    doc = ast.get_docstring(node)
    if not doc:
        return None
    lines = doc.strip().splitlines()
    return lines[0] if lines else None


def _fmt_func(
    node: ast.FunctionDef | ast.AsyncFunctionDef, indent: str = "", include_doc: bool = False
) -> str:
    decs = _fmt_decorators(node, indent=indent)
    args = _fmt_args(node.args)
    ret = f" -> {_ann(node.returns)}" if node.returns else ""
    # 保留 `async` 前缀：否则 `async def` ↔ `def` 的接口漂移在 L1 哈希上不可见（ocr-059）。
    prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
    func_line = f"{decs}{indent}{prefix}{node.name}({args}){ret}"
    if include_doc:
        first = _doc_first_line(node)
        if first:
            return f"{func_line}\n{indent}    # doc: {first}"
    return func_line


def _class_member(child: ast.AST, include_doc: bool) -> Optional[str]:
    """一个 class body child → 签名行（公开才出）。"""
    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and not child.name.startswith("_"):
        return _fmt_func(child, indent="    ", include_doc=include_doc)
    if isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name) and not child.target.id.startswith("_"):
        ann = _ann(child.annotation)
        suffix = f": {ann}" if ann else ""
        val = f" = {_fmt_value(child.value)}" if child.value is not None else ""
        return f"    {child.target.id}{suffix}{val}"
    if isinstance(child, ast.Assign):
        parts = [f"    {t.id} = {_fmt_value(child.value)}" for t in child.targets
                 if isinstance(t, ast.Name) and not t.id.startswith("_")]
        return "\n".join(parts) if parts else None
    return None


def _fmt_class(node: ast.ClassDef, indent: str = "", include_doc: bool = False) -> str:
    bases = ", ".join(_ann(b) for b in node.bases) if node.bases else ""
    header = f"class {node.name}({bases})" if bases else f"class {node.name}"
    lines: List[str] = []
    if include_doc:
        first = _doc_first_line(node)
        if first:
            lines.append(f"{indent}# doc: {first}")
    for child in node.body:
        m = _class_member(child, include_doc)
        if m:
            lines.extend(m.split("\n"))
    if not lines:
        return header
    return header + "\n" + "\n".join(lines)


class ContractExtractor:
    """Abstract contract extractor — register per-language implementations."""

    def can_handle(self, path: Path) -> bool:  # pragma: no cover
        raise NotImplementedError

    def extract(self, path: Path, include_doc: bool = False) -> str:  # pragma: no cover
        raise NotImplementedError


_IGNORED_DIRS = {".git", "__pycache__", "build", "dist", ".venv", "venv", ".pytest_cache", ".mypy_cache"}


class PythonExtractor(ContractExtractor):
    def can_handle(self, path: Path) -> bool:
        return path.suffix == ".py" and path.name != "__init__.py" and not _IGNORED_DIRS.intersection(path.parts)

    def extract(self, path: Path, include_doc: bool = False) -> str:
        return extract_python_interface(path.read_text(encoding="utf-8"), include_doc=include_doc)


_EXTRACTORS: list[ContractExtractor] = []
# drop-in 插件的进程内幂等缓存（绝对路径）；显式模块级，测试可直接清。
_PLUGIN_ATTEMPTED: set[str] = set()


def register_extractor(ext: ContractExtractor, *, override: bool = False) -> None:
    """Register a language extractor (plugin interface).

    Built-ins call this at import; downstream harnesses call it for their own
    languages without touching core. First match wins in `collect_domain_interface`:
    `override=True` inserts at front (takes precedence for overlapping suffixes).
    Must be a `ContractExtractor` (`can_handle` + `extract`); otherwise TypeError.
    Discovery (no command needed): declare modules in manifest `extractors`, or
    drop a `.py` file calling this into `<workspace>/.agent/extractors/` —
    in-process calls alone do not survive across `k3dge` invocations.
    """
    if not isinstance(ext, ContractExtractor):
        raise TypeError(f"register_extractor expects ContractExtractor, got {type(ext).__name__}")
    if override:
        _EXTRACTORS.insert(0, ext)
    else:
        _EXTRACTORS.append(ext)


# 幂等缓存从函数属性挪到模块级 `_PLUGIN_ATTEMPTED`（可测、可清），单函数不再混装三件事。
def _load_manifest_extractors(specs: object) -> None:
    """Source 1: `extractors: ["mod" | "mod:attr", ...]` — explicit, out-of-repo/pip."""
    import importlib
    import sys

    if not isinstance(specs, list):
        specs = []
    for spec in specs:
        if not isinstance(spec, str) or not spec.strip():
            continue
        mod_name, _, attr = spec.strip().partition(":")
        try:
            mod = importlib.import_module(mod_name)
            if attr:
                ext = getattr(mod, attr)
                if isinstance(ext, ContractExtractor) and ext not in _EXTRACTORS:
                    register_extractor(ext)
        except Exception as exc:  # noqa: BLE001 — plugin must not break the gate
            print(f"[WARN][EXTRACTOR] skipping '{spec}': {exc}", file=sys.stderr)


def _load_dropin_extractors(root: Path) -> None:
    """Source 2: `<workspace>/.agent/extractors/*.py` — drop-in, no manifest edit.

    Files starting with `_` are skipped; each file is isolated (one bad file warns and
    the rest still load). `_PLUGIN_ATTEMPTED` keeps re-invocations from re-executing.
    """
    import importlib.util
    import sys

    plug_dir = Path(root) / ".agent" / "extractors"
    if not plug_dir.is_dir():
        return
    for plug_file in sorted(plug_dir.glob("*.py")):
        if plug_file.name.startswith("_"):
            continue
        mod_name = f"k3dge_plugin_{plug_file.stem}"
        if mod_name in sys.modules or str(plug_file) in _PLUGIN_ATTEMPTED:
            continue
        _PLUGIN_ATTEMPTED.add(str(plug_file))
        # import 时 `register_extractor()` 先执行、后半模块再抛 ⇒ 半注册的 extractor
        # 留在 `_EXTRACTORS` 里认领文件却抽不出接口（ocr2-225）。失败即回滚本文件加进去的。
        # 快照整表（而非只记长度）：`register_extractor(..., override=True)` 是公开 API，
        # 会 `insert(0, ext)` 而非 append ⇒ `del _EXTRACTORS[len_before:]` 会把内置抽取器从尾部
        # 删掉、留下插进来的半成品。失败即整表还原。
        _snapshot = list(_EXTRACTORS)
        try:
            spec_obj = importlib.util.spec_from_file_location(mod_name, plug_file)
            if spec_obj is None or spec_obj.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec_obj)
            sys.modules[mod_name] = mod
            spec_obj.loader.exec_module(mod)
        except Exception as exc:  # noqa: BLE001 — one bad file must not block the rest
            _EXTRACTORS[:] = _snapshot
            sys.modules.pop(mod_name, None)
            print(f"[WARN][EXTRACTOR] skipping '{plug_file.name}': {exc}", file=sys.stderr)


def _load_plugin_extractors(manifest, workspace_root=None) -> None:
    """Load third-party extractors from two sources (both feed `register_extractor`).

    1. Manifest key: `extractors: ["mod" / "mod:attr", ...]` — explicit, for
       out-of-repo modules and pip packages（`_load_manifest_extractors`）.
    2. Convention directory: `<workspace>/.agent/extractors/*.py` — drop a file
       that calls `register_extractor()` at import; no manifest edit, no command
       （`_load_dropin_extractors`）.

    Best-effort throughout: a broken plugin warns to stderr and is skipped —
    a broken plugin must not red the gate (same policy as missing tree-sitter).
    Idempotent per process: already-imported modules are not re-executed
    (`_PLUGIN_ATTEMPTED`).
    """
    specs = (manifest.data.get("extractors") or []) if manifest is not None else []
    _load_manifest_extractors(specs)

    root = workspace_root
    if root is None and manifest is not None:
        root = getattr(manifest, "workspace_root", None) or getattr(manifest, "workspace", None)
    if root is None:
        return
    _load_dropin_extractors(Path(root))


register_extractor(PythonExtractor())


def _str_elts(value: Optional[ast.AST]) -> set:
    """从 List/Tuple 字面量收集字符串常量集（`__all__` 用）。"""
    names = set()
    if isinstance(value, (ast.List, ast.Tuple)):
        for elt in value.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                names.add(elt.value)
    return names


def _get_all_names(tree: ast.Module) -> Optional[set[str]]:
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "__all__" and isinstance(node.value, (ast.List, ast.Tuple)):
                    return _str_elts(node.value)
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "__all__"
            and isinstance(node.value, (ast.List, ast.Tuple))
        ):
            return _str_elts(node.value)
    return None


def _is_public(name: str) -> bool:
    return bool(name) and not name.startswith("_")


def _wanted(allow: Optional[set], name: str) -> bool:
    return (name in allow) if allow is not None else _is_public(name)


def _iface_module_const(node, allow: Optional[set]) -> List[str]:
    """模块级 `Assign/AnnAssign` → 公开常量行（含 `__all__`）。"""
    out: List[str] = []
    value = node.value
    ann_suffix = f": {_ann(node.annotation)}" if isinstance(node, ast.AnnAssign) and node.annotation is not None else ""
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    for t in targets:
        if not isinstance(t, ast.Name):
            continue
        if t.id == "__all__":
            if allow is not None:
                out.append(f"__all__ = {sorted(allow)}")
            continue
        if not _is_public(t.id) or not _wanted(allow, t.id):
            continue
        val = f" = {_fmt_value(value)}" if value is not None else ""
        out.append(f"{t.id}{ann_suffix}{val}")
    return out


def _iface_import(node, allow: Optional[set]) -> List[str]:
    """`from … import …` → 公开 re-export 行。"""
    out: List[str] = []
    module = ("." * node.level) + (node.module or "")
    for alias in node.names:
        if alias.name == "*":
            continue
        name = alias.asname or alias.name
        if not _is_public(name) or not _wanted(allow, name):
            continue
        # 只画别名会丢 re-export 目标：`from .legacy import Api as Foo` 与
        # `from .legacy import NewImpl as Foo` 序列化成同一行，换目标不触哈希（ocr2-226）。
        # `_symbol_name` 本就按别名键（`" as "` 处理），值里保留原名不影响键。
        if alias.asname and alias.asname != alias.name:
            out.append(f"from {module} import {alias.name} as {alias.asname}")
        else:
            out.append(f"from {module} import {name}")
    return out


def extract_python_interface(source: str, include_doc: bool = False) -> str:
    """Extract normalized public interface signatures from Python source.

    `include_doc=True` also carries the first docstring line into the display
    (used by machine docs); hash computation always uses `include_doc=False`
    so comment/docstring churn never triggers contract drift.
    """
    tree = ast.parse(source)
    allow = _get_all_names(tree)
    lines: List[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _wanted(allow, node.name):
                lines.append(_fmt_func(node, include_doc=include_doc))
        elif isinstance(node, ast.ClassDef):
            if _wanted(allow, node.name):
                lines.append(_fmt_class(node, include_doc=include_doc))
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            lines.extend(_iface_module_const(node, allow))
        elif isinstance(node, ast.ImportFrom):
            lines.extend(_iface_import(node, allow))
    return "\n".join(lines)


def normalize(interface: str) -> str:
    return "\n".join(
        " ".join(line.split()) for line in interface.splitlines() if line.strip()
    )


def compute_hash(interface: str) -> str:
    return hashlib.sha256(normalize(interface).encode("utf-8")).hexdigest()


def collect_domain_interface(
    src_dir: Path,
    manifest=None,
    workspace_root: Path | None = None,
    include_doc: bool = False,
) -> str:
    """Concatenate normalized public interfaces of all source files in a domain via polymorphic extractors.

    `include_doc=True` appends first-line docstrings for display (api.md);
    hashing always calls with the default `False` so docstrings stay out of the contract.
    """
    if not src_dir.exists():
        return ""
    _load_plugin_extractors(manifest, workspace_root)
    chunks: List[str] = []
    try:
        src_resolved = src_dir.resolve()
    except OSError:
        src_resolved = src_dir
    for file_path in sorted(src_dir.rglob("*")):
        if file_path.is_symlink() or not file_path.is_file():
            continue
        try:
            file_path.resolve().relative_to(src_resolved)
        except (ValueError, OSError):
            continue
        if manifest is not None and workspace_root is not None:
            try:
                rel = str(file_path.relative_to(workspace_root)).replace("\\", "/")
            except ValueError:
                rel = str(file_path).replace("\\", "/")
            if manifest.is_ignored(rel):
                continue
        _claimed, _import_failed = False, False
        for extractor in _EXTRACTORS:
            if extractor.can_handle(file_path):
                try:
                    iface = extractor.extract(file_path, include_doc=include_doc)
                    if iface and iface.strip():
                        if include_doc:
                            chunks.append(f"# {file_path.name}\n{iface}")
                        else:
                            chunks.append(iface)
                        _claimed = True
                        break          # 只有真拿到接口才认领这个 extractor（空串不认领，
                                       # 让后面的 extractor 还有机会；ocr2-228）
                except ImportError as exc:
                    # 依赖缺失 ≠ 认领成功：`break` 会让该文件谁都没计（合同只覆盖一部分还判"一致"），
                    # 也没给别的 extractor 机会；至少出声（ocr-225）。
                    import sys as _sys

                    print(f"[contract] WARN: {file_path} 的 extractor 依赖缺失（{exc}）⇒ 尝试下一个",
                          file=_sys.stderr)
                    _import_failed = True
                    continue
                except (SyntaxError, UnicodeDecodeError, OSError) as exc:
                    raise _ExtractError(f"failed to extract interface from {file_path}: {exc}") from exc
        # 认领了该文件的 extractor 全因缺依赖失败 ⇒ 合同是"残缺"不是"一致"：只 WARN 会让降级跑过闸（ocr2-051）。
        if not _claimed and _import_failed:
            raise _ExtractError(f"no working extractor for {file_path}（依赖缺失），合同不完整")
    return "\n".join(chunks)


def verify_contract(
    src_dir: Path, spec_content: str, manifest=None, workspace_root: Path | None = None
) -> Tuple[bool, Optional[str], str]:
    """Return (ok, expected_hash_or_none, actual_hash)."""
    actual_hash = compute_hash(collect_domain_interface(src_dir, manifest, workspace_root))
    expected = _extract_hash(spec_content)
    if expected is None:
        return False, None, actual_hash
    return expected == actual_hash, expected, actual_hash


def _extract_hash(spec_content: str) -> Optional[str]:
    from k3dge.engine import spec_schema

    return spec_schema.extract_contract_hash(spec_content)


def _extract_interface_block(spec_content: str) -> str:
    start = spec_content.find(INTERFACE_START)
    end = spec_content.find(INTERFACE_END)
    if start == -1 or end == -1:
        return ""
    return spec_content[start + len(INTERFACE_START) : end].strip()


def _symbol_name(line: str) -> Optional[str]:
    """Symbol key for a generated-interface line: class / function / constant / re-export."""
    s = line.strip()
    if not s:
        return None
    if s.startswith("class "):
        # drop bases and trailing ':' so the key is the class name (bases stay in the value)
        return re.split(r"[(:]", s[len("class ") :], maxsplit=1)[0].strip() or None
    if s.startswith("from ") and " import " in s:
        tail = s.split(" import ", 1)[1]
        return tail.split(",")[0].split(" as ")[-1].strip().split(".")[0] or None
    if s.startswith("import "):
        tail = s[len("import ") :]
        return tail.split(",")[0].split(" as ")[-1].strip().split(".")[0] or None
    m = re.match(r"([A-Za-z_]\w*)\s*[:=]", s)
    if m:  # module constant / annotated constant (key = name, value = full line)
        return m.group(1)
    if s.startswith("async "):
        # `async def f(...)` / `async f(...)`：`head` 会是 `async def f`/`async f`，过不了全名校验 ⇒
        # 异步函数整条丢（ocr2-052）。`async` 开头必是定义行，去掉再按同步走。
        s = s[len("async "):].strip()
        if s.startswith("def "):
            s = s[len("def "):].strip()
    if "(" in s:
        head = s[: s.index("(")].strip()
        if re.fullmatch(r"[A-Za-z_]\w*", head):
            return head
    return None


def _parse_symbols(interface: str) -> "dict[str, str]":
    """Map each top-level public symbol -> normalized signature (class includes members).

    Takes the **raw** (indented) interface. Leading indentation is what marks a symbol
    as a class member, so it must not be collapsed beforehand (code-14): normalizing
    first made every method/property a bogus top-level symbol and mixed `def ` / base
    lists into the keys. Only intra-line whitespace is collapsed, for stable compares.
    """
    syms: dict[str, str] = {}
    current: Optional[str] = None
    pending: List[str] = []          # 顶层装饰器行：属于**下一个**符号
    for raw in interface.split("\n"):
        collapsed = " ".join(raw.split())
        if not collapsed:
            continue
        indent = len(raw) - len(raw.lstrip())
        name = _symbol_name(collapsed)
        if indent == 0 and collapsed.startswith("@") and not name:
            # `@final` / `@property` 这类行 `_symbol_name` 认不出 ⇒ 旧实现把它并到**上一个**符号的
            # 值里，改一个装饰器就假报 changed；没有上一个符号时又整行丢失（ocr-226）。
            pending.append(collapsed)
            continue
        if indent == 0 and name:
            current = name
            syms[name] = "\n".join(pending + [collapsed]) if pending else collapsed
            pending = []
        elif current is not None and not pending:
            syms[current] += "\n" + collapsed
    return syms


def symbol_diff(
    spec_content: str,
    src_dir: Path,
    manifest=None,
    workspace_root: Path | None = None,
) -> dict:
    """L1 report layer: symbol-level diff between spec-stored interface and live code.

    Returns {added, removed, changed} of public symbol names. The contract hash
    proves "you didn't sync"; this proves "you changed the contract" — so sync can
    no longer be a universal wash for abstraction churn (ADR-0001 decision 6).
    """
    spec_block = _extract_interface_block(spec_content)
    code_iface = collect_domain_interface(src_dir, manifest, workspace_root)
    spec_syms = _parse_symbols(spec_block)
    code_syms = _parse_symbols(code_iface)
    added = sorted(set(code_syms) - set(spec_syms))
    removed = sorted(set(spec_syms) - set(code_syms))
    changed = sorted(
        n for n in (set(code_syms) & set(spec_syms)) if code_syms[n] != spec_syms[n]
    )
    return {"added": added, "removed": removed, "changed": changed}
