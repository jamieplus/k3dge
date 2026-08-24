"""L1 contract drift detection: public interface -> content hash."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import List, Optional, Tuple

INTERFACE_START = "<!-- k3dge:interfaces-start -->"
INTERFACE_END = "<!-- k3dge:interfaces-end -->"


class _ExtractError(RuntimeError):
    """A domain source file could not be parsed for its public interface."""


def _ann(node: Optional[ast.AST]) -> str:
    return ast.unparse(node) if node is not None else ""


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
    func_line = f"{decs}{indent}{node.name}({args}){ret}"
    if include_doc:
        first = _doc_first_line(node)
        if first:
            return f"{func_line}\n{indent}    # doc: {first}"
    return func_line


def _fmt_class(node: ast.ClassDef, indent: str = "", include_doc: bool = False) -> str:
    bases = ", ".join(_ann(b) for b in node.bases) if node.bases else ""
    header = f"class {node.name}({bases})" if bases else f"class {node.name}"
    lines: List[str] = []
    if include_doc:
        first = _doc_first_line(node)
        if first:
            lines.append(f"{indent}# doc: {first}")
    members = []
    for child in node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and not child.name.startswith("_"):
            members.append(_fmt_func(child, indent="    ", include_doc=include_doc))
        elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name) and not child.target.id.startswith("_"):
            ann = _ann(child.annotation)
            suffix = f": {ann}" if ann else ""
            val = f" = {_ann(child.value)}" if child.value is not None else ""
            members.append(f"    {child.target.id}{suffix}{val}")
        elif isinstance(child, ast.Assign):
            for t in child.targets:
                if isinstance(t, ast.Name) and not t.id.startswith("_"):
                    members.append(f"    {t.id} = {_ann(child.value)}")
    body = lines + members
    if not body:
        return header
    return header + "\n" + "\n".join(body)


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


class TypeScriptExtractor(ContractExtractor):
    def can_handle(self, path: Path) -> bool:
        return path.suffix in (".ts", ".tsx", ".js") and not _IGNORED_DIRS.intersection(path.parts)

    def extract(self, path: Path, include_doc: bool = False) -> str:
        result = extract_typescript_interface(path)
        if result is None:
            raise ImportError("tree-sitter not available")
        return result


_EXTRACTORS: list[ContractExtractor] = [PythonExtractor(), TypeScriptExtractor()]


def _get_all_names(tree: ast.Module) -> Optional[set[str]]:
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "__all__":
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        names = set()
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                names.add(elt.value)
                        return names
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "__all__":
            if isinstance(node.value, (ast.List, ast.Tuple)):
                names = set()
                for elt in node.value.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        names.add(elt.value)
                return names
    return None


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
            name = node.name
            if allow is not None:
                if name not in allow:
                    continue
            elif name.startswith("_"):
                continue
            lines.append(_fmt_func(node, include_doc=include_doc))
        elif isinstance(node, ast.ClassDef):
            name = node.name
            if allow is not None:
                if name not in allow:
                    continue
            elif name.startswith("_"):
                continue
            lines.append(_fmt_class(node, include_doc=include_doc))
    return "\n".join(lines)


def extract_typescript_interface(path: Path) -> Optional[str]:
    """Extract TypeScript interface signatures via tree-sitter (optional dependency)."""
    try:
        from k3dge.engine._ts import extract_ts_interface
    except ImportError:
        return None
    return extract_ts_interface(path)


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
    chunks: List[str] = []
    for file_path in sorted(src_dir.rglob("*")):
        if not file_path.is_file():
            continue
        if manifest is not None and workspace_root is not None:
            try:
                rel = str(file_path.relative_to(workspace_root)).replace("\\", "/")
            except ValueError:
                rel = str(file_path).replace("\\", "/")
            if manifest.is_ignored(rel):
                continue
        for extractor in _EXTRACTORS:
            if extractor.can_handle(file_path):
                try:
                    iface = extractor.extract(file_path, include_doc=include_doc)
                    if iface and iface.strip():
                        chunks.append(f"# {file_path.name}\n{iface}")
                except ImportError:
                    pass
                except (SyntaxError, UnicodeDecodeError, OSError) as exc:
                    raise _ExtractError(f"failed to extract interface from {file_path}: {exc}") from exc
                break
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
