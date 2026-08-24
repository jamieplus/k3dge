"""Best-effort TypeScript interface extraction via tree-sitter (optional dependency)."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

_FN_CLASS = ("function_declaration", "class_declaration", "method_definition")
_TYPE_KINDS = ("interface_declaration", "type_alias_declaration", "enum_declaration")


def _slice(source: bytes, node) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", "replace").strip()


def _strip_impl_body(text: str) -> str:
    """Drop the first `{ ... }` implementation body; keep signature / type members."""
    brace = text.find("{")
    if brace == -1:
        return text.rstrip()
    return text[:brace].rstrip()


def _class_signature(source: bytes, node) -> str:
    header = _strip_impl_body(_slice(source, node))
    methods: List[str] = []
    for child in node.children:
        if child.type != "class_body":
            continue
        for member in child.children:
            if member.type in ("method_definition", "public_field_definition", "field_definition"):
                sig = _strip_impl_body(_slice(source, member))
                if sig:
                    methods.append("  " + sig)
    if not methods:
        return header
    return header + "\n" + "\n".join(methods)


def _decl_signature(source: bytes, node, exported: bool = False) -> Optional[str]:
    if node.type == "export_statement":
        inner = None
        for child in node.children:
            if child.type in _FN_CLASS + _TYPE_KINDS + ("lexical_declaration",):
                inner = child
                break
        if inner is None:
            return _slice(source, node)
        return _decl_signature(source, inner, exported=True)
    if node.type == "class_declaration":
        text = _class_signature(source, node)
    elif node.type in ("function_declaration", "method_definition"):
        text = _strip_impl_body(_slice(source, node))
    elif node.type in _TYPE_KINDS:
        text = _slice(source, node)
    elif node.type == "lexical_declaration":
        if not exported:
            return None
        text = _slice(source, node)
        if "=>" in text or "function" in text:
            text = _strip_impl_body(text)
    else:
        return None
    if exported and not text.startswith("export"):
        text = "export " + text
    return text


def extract_ts_interface(path: Path) -> str:
    try:
        from tree_sitter import Language, Parser
        import tree_sitter_typescript
    except ImportError as exc:  # pragma: no cover - optional dep missing
        raise ImportError("tree-sitter not installed") from exc

    # 0.21+ API: Language(tree_sitter_typescript.language_typescript())
    # 0.20 API: Language("path.so", "typescript") — handled via fallback
    try:
        language = Language(tree_sitter_typescript.language_typescript())
    except Exception:
        language = Language(tree_sitter_typescript.language_typescript(), "typescript")  # type: ignore[call-arg]

    try:
        parser = Parser(language)  # 0.21+
    except TypeError:
        parser = Parser()  # pragma: no cover - legacy fallback
        parser.language = language  # type: ignore[attr-defined]

    source = path.read_bytes()
    tree = parser.parse(source)

    lines = []
    for node in tree.root_node.children:
        text = _decl_signature(source, node)
        if text:
            lines.append(text)
    return "\n".join(lines)
