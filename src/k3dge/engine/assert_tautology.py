"""测试断言的真值已经写在表达式里。

产品代码的改动失败不了这种断言：字面 `assert True`，或不含调用的同一表达式
（`x == x`、`1 == 1`），或一层别名替换之后比较两边才变成同一表达式
（`==` / `is` / `<=` / `>=`）。归一前已经相同、且里面有调用的
（`digest(b) == digest(b)`）是确定性测试，两次调用可以不同，不报。
`assert False`、`x != x`、`x < x` 是恒失败，不在这里。
调用之间的别名作废：中间有调用，就不再把赋值左边当成右边的别名。
判断类：只报，不改写断言。
"""

from __future__ import annotations

import ast
import copy
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from k3dge.engine.models import Violation

_TEST_PARTS = frozenset({"tests", "test"})
_SAME_OPS = (ast.Eq, ast.Is, ast.LtE, ast.GtE)
_TRUE_METHODS = frozenset({"assertTrue", "assert_", "failUnless"})
_FALSE_METHODS = frozenset({"assertFalse", "failIf"})
_SAME_METHODS = frozenset({
    "assertEqual",
    "assertEquals",
    "failUnlessEqual",
    "assertIs",
    "assertLessEqual",
    "assertGreaterEqual",
})
_KEEP_ALIASES = (ast.Pass, ast.Break, ast.Continue, ast.Global, ast.Nonlocal)


def _norm_rel(rel: str) -> str:
    rel = str(rel).replace("\\", "/").strip()
    while rel.startswith("./"):
        rel = rel[2:]
    return rel


def is_test_path(rel: str) -> bool:
    """路径段含 `tests` 或 `test` 的 Python 文件。`src/**/test_surface.py` 不算。"""
    rel = _norm_rel(rel)
    if not rel.endswith(".py"):
        return False
    parts = rel.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return False
    return any(part in _TEST_PARTS for part in parts)


def _is_pure(node: ast.AST) -> bool:
    """名字、属性、下标、常量，以及它们的容器。调用不算。"""
    if isinstance(node, (ast.Name, ast.Constant)):
        return True
    if isinstance(node, ast.Attribute):
        return _is_pure(node.value)
    if isinstance(node, ast.Subscript):
        return _is_pure(node.value) and _is_pure(node.slice)
    if isinstance(node, ast.Slice):
        return all(part is None or _is_pure(part) for part in (node.lower, node.upper, node.step))
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return all(_is_pure(elt) for elt in node.elts)
    if isinstance(node, ast.Dict):
        return all(
            (key is None or _is_pure(key)) and _is_pure(value)
            for key, value in zip(node.keys, node.values)
        )
    return False


def _simple_pure(stmt: ast.Assign) -> bool:
    return (
        len(stmt.targets) == 1
        and isinstance(stmt.targets[0], ast.Name)
        and _is_pure(stmt.value)
    )


def _mutates(node: ast.AST) -> bool:
    return any(isinstance(child, (ast.Call, ast.NamedExpr)) for child in ast.walk(node))


def _bound_names(target: ast.AST) -> Optional[Set[str]]:
    """赋值目标绑住的名字。目标不是纯名字模式时返回 None（别名不再可信）。"""
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        names: Set[str] = set()
        for elt in target.elts:
            sub = _bound_names(elt)
            if sub is None:
                return None
            names |= sub
        return names
    if isinstance(target, ast.Starred):
        return _bound_names(target.value)
    return None


def _child(
    aliases: Dict[str, ast.AST], drop: Optional[Set[str]] = None, *, mutated: bool = False,
) -> Dict[str, ast.AST]:
    if mutated:
        return {}
    child = dict(aliases)
    for name in drop or ():
        child.pop(name, None)
    return child


def _dump(node: ast.AST) -> str:
    return ast.dump(node, include_attributes=False)


def _subst(node: ast.AST, aliases: Dict[str, ast.AST]) -> ast.AST:
    """一层替换：命中的名字换成别名表达式，别名内部不再展开。"""
    if not aliases:
        return node
    copied = copy.deepcopy(node)

    class _Replace(ast.NodeTransformer):
        def visit_Name(self, name: ast.Name):
            hit = aliases.get(name.id)
            if hit is None:
                return name
            return copy.deepcopy(hit)

    return _Replace().visit(copied)


def _literal_bool(node: ast.AST, value: bool) -> bool:
    return isinstance(node, ast.Constant) and node.value is value


def _has_call(node: ast.AST) -> bool:
    return any(isinstance(child, ast.Call) for child in ast.walk(node))


def _same_after_subst(nodes: List[ast.AST], aliases: Dict[str, ast.AST]) -> bool:
    """两边归一后是同一表达式。

    归一前已经相同、且表达式里有调用：两次调用可以返回不同值
    （哈希、摘要这种确定性测试）。那种不报。
    别名替换之后才变相同的（`ax = ck["axes"]` 再 `set(ax) <= set(ck["axes"])`）要报。
    """
    if len({_dump(_subst(node, aliases)) for node in nodes}) != 1:
        return False
    already = len({_dump(node) for node in nodes}) == 1
    if already and _has_call(_subst(nodes[0], aliases)):
        return False
    return True


def _self_compare(node: ast.AST, aliases: Dict[str, ast.AST]) -> bool:
    if not isinstance(node, ast.Compare) or not node.ops:
        return False
    if not all(isinstance(op, _SAME_OPS) for op in node.ops):
        return False
    return _same_after_subst([node.left, *node.comparators], aliases)


def _assert_shape(test: ast.AST, aliases: Dict[str, ast.AST]) -> Optional[str]:
    if _literal_bool(test, True):
        return "literal_true"
    if _self_compare(test, aliases):
        return "self_compare"
    return None


def _call_arg(call: ast.Call, index: int, keyword: str) -> Optional[ast.AST]:
    if any(isinstance(arg, ast.Starred) for arg in call.args):
        return None
    if index < len(call.args):
        return call.args[index]
    for kw in call.keywords:
        if kw.arg == keyword:
            return kw.value
    return None


def _unittest_shape(node: ast.AST, aliases: Dict[str, ast.AST]) -> Optional[str]:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return None
    name = node.func.attr
    if name in _TRUE_METHODS:
        arg = _call_arg(node, 0, "expr")
        if arg is None:
            return None
        if _literal_bool(_subst(arg, aliases), True):
            return "literal_true"
        if _self_compare(arg, aliases):
            return "self_compare"
        return None
    if name in _FALSE_METHODS:
        arg = _call_arg(node, 0, "expr")
        if arg is not None and _literal_bool(_subst(arg, aliases), False):
            return "literal_false"
        return None
    if name in _SAME_METHODS:
        left = _call_arg(node, 0, "first")
        right = _call_arg(node, 1, "second")
        if left is None or right is None:
            return None
        if _same_after_subst([left, right], aliases):
            return "self_compare"
        return None
    return None


def _is_assertion_call(node: ast.AST) -> bool:
    """unittest 风格的断言调用。参数里的调用不算「赋值和断言之间的调用」。"""
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return False
    name = node.func.attr
    return name.startswith("assert") or name in _TRUE_METHODS or name in _FALSE_METHODS or name in _SAME_METHODS


def _block_mutates(stmts: List[ast.stmt]) -> bool:
    for stmt in stmts:
        if isinstance(stmt, ast.Assert):
            continue
        if isinstance(stmt, ast.Expr) and _is_assertion_call(stmt.value):
            continue
        if _mutates(stmt):
            return True
    return False


def _if(stmt: ast.If, aliases: Dict[str, ast.AST], found: List[Tuple[int, str]]) -> None:
    mutated = _mutates(stmt.test)
    _block(stmt.body, _child(aliases, mutated=mutated), found)
    orelse = stmt.orelse
    if len(orelse) == 1 and isinstance(orelse[0], ast.If):
        _if(orelse[0], _child(aliases, mutated=mutated), found)
    else:
        _block(orelse, _child(aliases, mutated=mutated), found)


def _try(stmt: ast.stmt, aliases: Dict[str, ast.AST], found: List[Tuple[int, str]]) -> None:
    body = list(getattr(stmt, "body", []))
    _block(body, dict(aliases), found)
    mutated = _block_mutates(body)
    base = {} if mutated else dict(aliases)
    for handler in getattr(stmt, "handlers", []):
        drop: Set[str] = set()
        name = getattr(handler, "name", None)
        if isinstance(name, str):
            drop.add(name)
        elif isinstance(name, ast.Name):
            drop.add(name.id)
        handler_mut = mutated or (
            getattr(handler, "type", None) is not None and _mutates(handler.type)
        )
        _block(handler.body, _child(base, drop, mutated=handler_mut), found)
    _block(list(getattr(stmt, "orelse", [])), dict(base), found)
    _block(list(getattr(stmt, "finalbody", [])), dict(base), found)


def _compound(stmt: ast.stmt, aliases: Dict[str, ast.AST], found: List[Tuple[int, str]]) -> None:
    if isinstance(stmt, ast.If):
        _if(stmt, aliases, found)
        return
    if isinstance(stmt, (ast.For, ast.AsyncFor)):
        bound = _bound_names(stmt.target)
        mutated = _mutates(stmt.iter) or bound is None
        child = _child(aliases, bound, mutated=mutated)
        _block(stmt.body, child, found)
        _block(stmt.orelse, _child(aliases, bound, mutated=mutated), found)
        return
    if isinstance(stmt, ast.While):
        mutated = _mutates(stmt.test)
        _block(stmt.body, _child(aliases, mutated=mutated), found)
        _block(stmt.orelse, _child(aliases, mutated=mutated), found)
        return
    if isinstance(stmt, (ast.With, ast.AsyncWith)):
        drop: Set[str] = set()
        mutated = False
        for item in stmt.items:
            if _mutates(item.context_expr):
                mutated = True
            if item.optional_vars is not None:
                bound = _bound_names(item.optional_vars)
                if bound is None:
                    mutated = True
                else:
                    drop |= bound
        _block(stmt.body, _child(aliases, drop, mutated=mutated), found)
        return
    try_star = getattr(ast, "TryStar", None)
    if isinstance(stmt, ast.Try) or (try_star is not None and isinstance(stmt, try_star)):
        _try(stmt, aliases, found)
        return
    match = getattr(ast, "Match", None)
    if match is not None and isinstance(stmt, match):
        for case in stmt.cases:
            _block(case.body, {}, found)
        return
    body = getattr(stmt, "body", None)
    if isinstance(body, list):
        _block(body, {}, found)


def _statement(stmt: ast.stmt, aliases: Dict[str, ast.AST], found: List[Tuple[int, str]]) -> None:
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        aliases.pop(stmt.name, None)
        _block(stmt.body, {}, found)
        if any(_mutates(dec) for dec in stmt.decorator_list):
            aliases.clear()
        return
    if isinstance(stmt, ast.Assign) and _simple_pure(stmt):
        aliases[stmt.targets[0].id] = stmt.value
        return
    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
        if stmt.value is not None and _is_pure(stmt.value):
            aliases[stmt.target.id] = stmt.value
        elif stmt.value is not None:
            aliases.clear()
        return
    if isinstance(stmt, ast.Assert):
        shape = _assert_shape(stmt.test, aliases)
        if shape:
            found.append((stmt.lineno, shape))
        return
    if isinstance(stmt, _KEEP_ALIASES):
        return
    if isinstance(stmt, ast.Expr):
        shape = _unittest_shape(stmt.value, aliases)
        if shape:
            found.append((stmt.lineno, shape))
        if not _is_assertion_call(stmt.value) and _mutates(stmt.value):
            aliases.clear()
        return
    if isinstance(stmt, _compound_types()):
        _compound(stmt, aliases, found)
        aliases.clear()
        return
    aliases.clear()


def _compound_types() -> Tuple[type, ...]:
    types: List[type] = [
        ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try,
    ]
    for name in ("Match", "TryStar"):
        node = getattr(ast, name, None)
        if node is not None:
            types.append(node)
    return tuple(types)


def _block(stmts: List[ast.stmt], aliases: Dict[str, ast.AST], found: List[Tuple[int, str]]) -> None:
    for stmt in stmts:
        _statement(stmt, aliases, found)


def scan_source(source: str) -> List[Tuple[int, str]]:
    """表达式内已定真值的断言。返回 (行号, literal_true|literal_false|self_compare)。语法错误返回空。"""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    found: List[Tuple[int, str]] = []
    _block(tree.body, {}, found)
    return found


def violations_for(rel: str, source: str) -> List[Violation]:
    """`rel` 不是测试路径时返回空。"""
    rel = _norm_rel(rel)
    if not is_test_path(rel):
        return []
    out: List[Violation] = []
    for line, shape in scan_source(source):
        out.append(Violation(
            "ASSERT_TAUTOLOGY",
            f"line {line} {shape}",
            file_path=rel,
            detail={"line": line, "shape": shape},
        ))
    return out


def test_files(workspace: Path) -> List[str]:
    """工作区 `tests/` 下的 Python 文件，供全量检查用。"""
    root = workspace / "tests"
    if not root.is_dir():
        return []
    base = workspace.resolve()
    rels: List[str] = []
    for path in sorted(root.rglob("*.py")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        try:
            path.resolve().relative_to(base)
        except (OSError, ValueError):
            continue
        rels.append(str(path.relative_to(workspace)).replace("\\", "/"))
    return rels


def check(workspace: Path, rels: List[str]) -> List[Violation]:
    """只检查 `rels` 里的测试路径。文件读不出或越出工作区则跳过。"""
    base = workspace.resolve()
    out: List[Violation] = []
    for raw in rels:
        rel = _norm_rel(raw)
        if not is_test_path(rel):
            continue
        path = workspace / rel
        try:
            resolved = path.resolve()
            resolved.relative_to(base)
            text = resolved.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        out.extend(violations_for(rel, text))
    return out
