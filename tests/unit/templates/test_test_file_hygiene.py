"""测试件自身的两条不变量（OCR 测试扫描 t-247/265/292/318 的防退化）。"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
GUARD_RE = re.compile(r'^if __name__ == "__main__":', re.M)


def _defs(text: str) -> list:
    return [(m.start(), m.group(0)) for m in re.finditer(r"^(?:def |class )\w+", text, re.M)]


def test_main_guard_is_last_statement_in_every_test_file() -> None:
    """守卫必须落在文件末尾。

    放在中间时 `unittest.main()` 会 `sys.exit()`：它**之后**的类/函数连定义都没发生，
    直跑该文件的命令仍然报 `OK`（退出码 0）⇒ 半套测试静默消失，比红更糟。
    """
    offenders = []
    for p in sorted((REPO / "tests").rglob("*.py")):
        text = p.read_text(encoding="utf-8")
        m = GUARD_RE.search(text)
        if not m:
            continue
        tail = text[m.end():]
        late = [d for pos, d in _defs(tail)]
        if late:
            offenders.append(f"{p.relative_to(REPO)}: 守卫之后还有 {len(late)} 个定义（首个＝{late[0]}）")
    assert not offenders, "测试文件的 __main__ 守卫不在末尾：" + "; ".join(offenders)
def test_no_dead_or_duplicate_imports_in_tests() -> None:
    """`tests/**` 不留死导入，也不在函数里重复导入模块作用域已有的名字。

    判据用 AST（按行正则会把多行 `from X import (` 的续行误当独立语句）。
    `from __future__ import annotations` 是编译器特性，不算未使用。
    """
    import ast as _ast

    bad: list[str] = []
    for path in sorted((REPO / "tests").rglob("*.py")):
        tree = _ast.parse(path.read_text(encoding="utf-8"))
        used: set[str] = set()
        for node in _ast.walk(tree):
            if isinstance(node, _ast.Name):
                used.add(node.id)
            elif isinstance(node, _ast.Attribute):
                base = node
                while isinstance(base, _ast.Attribute):
                    base = base.value
                if isinstance(base, _ast.Name):
                    used.add(base.id)

        def _bound(node) -> list[str]:
            if isinstance(node, _ast.ImportFrom) and node.module == "__future__":
                return []          # 编译器特性，不是可使用的名字
            out = []
            for a in node.names:
                if isinstance(node, _ast.Import):
                    out.append(a.asname or a.name.split(".")[0])
                else:
                    out.append(a.asname or a.name)
            return out

        module_bound = {n for node in tree.body if isinstance(node, (_ast.Import, _ast.ImportFrom)) for n in _bound(node)}
        for node in tree.body:
            if isinstance(node, (_ast.Import, _ast.ImportFrom)):
                for name in _bound(node):
                    if name not in used:
                        bad.append(f"{path}:{node.lineno} 死导入 {name}")
        for fn in [n for n in _ast.walk(tree) if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef))]:
            for stmt in fn.body:
                if isinstance(stmt, (_ast.Import, _ast.ImportFrom)):
                    for name in _bound(stmt):
                        if name in module_bound:
                            bad.append(f"{path}:{stmt.lineno} 函数内重复导入 {name}")
    assert not bad, "tests/ 里的死导入或重复局部导入：" + "; ".join(bad)


def test_every_mkdtemp_site_has_a_cleanup_handle() -> None:
    """`tempfile.mkdtemp()` 的每个站点，所在函数里必须有清理句柄（rmtree/addCleanup/atexit）。

    裸 mkdtemp 的临时目录活到进程结束，CI 上就是磁盘泄漏。
    """
    import ast as _ast

    offenders: list[str] = []
    for path in sorted((REPO / "tests").rglob("*.py")):
        src = path.read_text(encoding="utf-8")
        if "mkdtemp" not in src:
            continue
        tree = _ast.parse(src)
        parent: dict = {}
        for node in _ast.walk(tree):
            for child in _ast.iter_child_nodes(node):
                parent[child] = node
        sites = [
            n for n in _ast.walk(tree)
            if isinstance(n, _ast.Call) and isinstance(n.func, _ast.Attribute) and n.func.attr == "mkdtemp"
        ]
        for site in sites:
            chain = []
            node = site
            while node is not None:
                if isinstance(node, _ast.FunctionDef):
                    chain.append(node)
                node = parent.get(node)
            bodies = [_ast.get_source_segment(src, fn) or "" for fn in chain]
            if any(any(h in b for h in ("addCleanup", "rmtree", "atexit")) or "hygiene:keep-no-cleanup" in b
                   for b in bodies):
                continue
            where = chain[0] if chain else None
            offenders.append(f"{path}:{site.lineno} {where.name if where else '<module>'}")
    assert not offenders, "裸 mkdtemp（无清理句柄）的函数：" + "; ".join(offenders)
