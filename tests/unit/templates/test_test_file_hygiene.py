"""测试件自身的两条不变量（OCR 测试扫描 t-247/265/292/318 的防退化）。

ocr2-559..565：判据全部走 AST，不再靠行正则/子串——
- 守卫识别等价拼写（单/双引号、无空格、反向比较）而非只认字节精确的一种；
- 守卫必须是**文件 body 的最后一个节点**（非 def 语句、多个守卫都拦）；
- 重复导入走函数**子树**（try/if 里嵌的也算）；
- `mkdtemp` 站点认 `Attribute`/`Name`/别名三种形状；
- 清理判据是 AST 里对**同一绑定变量**的引用，而非函数源码子串。

`hygiene:keep-no-cleanup` 是有意的逐函数豁免（少数测试验的是被测代码自己清理）。
"""

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TESTS = REPO / "tests"


def _test_files() -> list:
    """语料收集 + **非空断言**（ocr2-559）：`REPO` 漂了或 `tests/` 改名，
    `rglob` 回空会让下面三条闸全绿地什么都不查。"""
    if not TESTS.is_dir():
        raise AssertionError(f"tests/ 目录不在（REPO 锚点漂了？）：{TESTS}")
    files = sorted(TESTS.rglob("*.py"))
    if not files:
        raise AssertionError(f"tests/ 下没扫到任何 .py：{TESTS}")
    return files


def _parse_file(path: Path):
    """ocr2-815：单文件读/解析失败记成调用方的 offender，不让整闸裸崩。

    语料 glob 是 `tests/**/*.py`（非 `test_*.py`）：一件非 UTF-8/不可 parse 的
    `.py`（含他测中途落盘的）会把整条闸炸成 UnicodeDecodeError/SyntaxError，
    而不是 hygiene 报告。返回 Module 或异常，由调用方归位。
    """
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        return exc


# ---------------------------------------------------------------- main guard


def _name_of(node):
    return node.id if isinstance(node, ast.Name) else None


def _const_of(node):
    return node.value if isinstance(node, ast.Constant) else None


def _is_main_guard(test: ast.AST) -> bool:
    if not (isinstance(test, ast.Compare) and len(test.ops) == 1
            and isinstance(test.ops[0], ast.Eq) and len(test.comparators) == 1):
        return False
    lhs, rhs = test.left, test.comparators[0]
    return ((_name_of(lhs) == "__name__" and _const_of(rhs) == "__main__")
            or (_name_of(rhs) == "__name__" and _const_of(lhs) == "__main__"))


def _main_guard(tree: ast.Module):
    for node in tree.body:
        if isinstance(node, ast.If) and _is_main_guard(node.test):
            return node
    return None


def test_main_guard_is_last_statement_in_every_test_file() -> None:
    """守卫必须落在文件末尾（AST 判定）。

    放在中间时 `unittest.main()` 会 `sys.exit()`：它**之后**的类/函数连定义都没发生，
    直跑该文件的命令仍然报 `OK`（退出码 0）⇒ 半套测试静默消失，比红更糟。
    ocr2-560/561：识别等价拼写；`async def`/非 def 语句/多个守卫都由"最后一个节点"覆盖。
    """
    offenders = []
    for p in _test_files():
        tree = _parse_file(p)
        if isinstance(tree, Exception):
            offenders.append(f"{p.relative_to(REPO)}: 读/解析失败（{type(tree).__name__}）")
            continue
        g = _main_guard(tree)
        if g is None:
            continue
        if tree.body[-1] is not g:
            after = [type(n).__name__ for n in tree.body[tree.body.index(g) + 1:]]
            offenders.append(f"{p.relative_to(REPO)}: __main__ 守卫之后还有 {after}")
    assert not offenders, "测试文件的 __main__ 守卫不在末尾：" + "; ".join(offenders)


# ------------------------------------------------------- dead / dup imports


def _bound(node) -> list:
    if isinstance(node, ast.ImportFrom) and node.module == "__future__":
        return []          # 编译器特性，不是可使用的名字
    out = []
    for a in node.names:
        if isinstance(node, ast.Import):
            out.append(a.asname or a.name.split(".")[0])
        else:
            out.append(a.asname or a.name)
    return out


def test_no_dead_or_duplicate_imports_in_tests() -> None:
    """`tests/**` 不留死导入，也不在函数里重复导入模块作用域已有的名字。

    ocr2-562：重复导入走**函数子树**（`ast.walk`），`try/if/with` 里嵌的也算——
    旧形状只看函数 body 的直接子节点，本仓 `test_main.py` 就有一批嵌在 `try` 里的漏网。
    """
    bad: list[str] = []
    for path in _test_files():
        tree = _parse_file(path)
        if isinstance(tree, Exception):
            bad.append(f"{path}:{0} 读/解析失败（{type(tree).__name__}）")
            continue
        used: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used.add(node.id)
            # ocr2-817：旧 `elif Attribute` 分支是冗余的——`ast.walk` 产出所有
            # 节点，属性链最内层的 Name（如 `os.path.join` 的 `os`）已被上一支
            # 收录，used 集逐文件一致。删掉它，去掉"属性处理是刻意为之"的误导。

        module_bound = {n for node in tree.body
                        if isinstance(node, (ast.Import, ast.ImportFrom))
                        for n in _bound(node)}
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for name in _bound(node):
                    if name not in used:
                        bad.append(f"{path}:{node.lineno} 死导入 {name}")

        # 最近函数祖先（子树判定）
        parents: dict = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            cur = parents.get(node)
            while cur is not None and not isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
                cur = parents.get(cur)
            if cur is None:
                continue
            for name in _bound(node):
                if name in module_bound:
                    bad.append(f"{path}:{node.lineno} 函数 {cur.name} 内重复导入 {name}")
    assert not bad, "tests/ 里的死导入或重复局部导入：" + "; ".join(bad)


# ------------------------------------------------- mkdtemp cleanup handle


def _callee(node) -> str:
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _mkdtemp_aliases(tree: ast.Module) -> set:
    """绑定到 `tempfile.mkdtemp` 的名字（ocr2-563）：`from tempfile import mkdtemp`
    与 `alias = tempfile.mkdtemp` 都要被当成站点来源。"""
    aliases: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "tempfile":
            for a in node.names:
                if a.name == "mkdtemp":
                    aliases.add(a.asname or a.name)
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if (isinstance(t, ast.Name) and isinstance(node.value, ast.Attribute)
                        and node.value.attr == "mkdtemp"):
                    aliases.add(t.id)
    return aliases


def _owner_of(site: ast.AST, parents: dict):
    """站点结果绑到哪个名字/属性（含 walrus，ocr2-563）。"""
    cur = site
    while cur is not None:
        if isinstance(cur, ast.NamedExpr) and isinstance(cur.target, ast.Name):
            return cur.target.id
        if isinstance(cur, (ast.Assign, ast.AnnAssign)):
            tgts = cur.targets if isinstance(cur, ast.Assign) else [cur.target]
            for t in tgts:
                if isinstance(t, ast.Name):
                    return t.id
                if isinstance(t, ast.Attribute):
                    return ast.unparse(t)
            return None
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Return, ast.Expr)):
            return None
        cur = parents.get(cur)
    return None


def test_every_mkdtemp_site_has_a_cleanup_handle() -> None:
    """每个 `mkdtemp` 站点，所在函数里必须有引用**同一绑定**的清理调用（rmtree/addCleanup/atexit）。

    ocr2-563/564/565：站点认 Attribute/Name/别名；函数链含 `async def`；
    清理判据是 AST 里对同一变量的引用，而非函数源码里出现 `rmtree` 字样（文档串/注释
    里的词、或别的临时目录的清理都不算）。
    """
    offenders: list[str] = []
    for path in _test_files():
        tree = _parse_file(path)
        if isinstance(tree, Exception):
            offenders.append(f"{path}:{0} 读/解析失败（{type(tree).__name__}）")
            continue
        src = path.read_text(encoding="utf-8")
        aliases = _mkdtemp_aliases(tree)
        parents: dict = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node
        for site in ast.walk(tree):
            if not isinstance(site, ast.Call):
                continue
            f = site.func
            is_site = ((isinstance(f, ast.Attribute) and f.attr == "mkdtemp")
                       or (isinstance(f, ast.Name) and f.id in aliases))
            if not is_site:
                continue
            chain = []
            cur = parents.get(site)
            while cur is not None:
                if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    chain.append(cur)
                cur = parents.get(cur)
            # 有意的逐函数豁免
            if any("hygiene:keep-no-cleanup" in (ast.get_source_segment(src, fn) or "")
                   for fn in chain):
                continue
            owner = _owner_of(site, parents)
            scope = chain[0] if chain else tree
            found = False
            for call in ast.walk(scope):
                if not isinstance(call, ast.Call) or _callee(call.func) not in (
                        "addCleanup", "register", "rmtree", "cleanup"):
                    continue
                refs = {n.id for n in ast.walk(call) if isinstance(n, ast.Name)}
                refs |= {ast.unparse(n) for n in ast.walk(call) if isinstance(n, ast.Attribute)}
                if owner and owner in refs:
                    found = True
            if not found:
                where = chain[0] if chain else None
                offenders.append(
                    f"{path}:{site.lineno} {where.name if where else '<module>'}（绑定 {owner!r} 未清理）")
    assert not offenders, "裸 mkdtemp（无清理句柄）的函数：" + "; ".join(offenders)
