"""测试面的 `read_text`/`write_text` 必须显式 `encoding="utf-8"`（M12 票 `tests_explicit_encoding` 的推进闸）。

**范围**（ocr2-556）：只管 `Path.read_text`/`Path.write_text` 两个属性调用；裸
`open()`/`io.open()` 不在本闸面（若要把它们纳入，需另立票并给存量债）。
"""

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
# 深度写死：文件挪层/扁平拷贝时 `parents[3]` 指错地方，测试扫错目录还绿（ocr2-130）。
# 启动即验锚点（`src/k3dge` + `tests/` + `.agent/` 三件齐），不对就大声失败，不静默。
for _anchor in ("src/k3dge", "tests", ".agent"):
    assert (REPO / _anchor).exists(), f"REPO 锚点缺失（{REPO}）：文件被移动后 parents[3] 已漂移"

#: 债已清空 ⇒ **零容忍**：任何隐式编码的 read_text/write_text 都红。
#: （2026-09-30：75 处全部收口，AST 定位调用自身右括号后插 encoding，含 `read_text()` 无参
#: 与撞尾逗号两种形状。）
DEBT: dict[str, int] = {}


def _encoding_node(call: ast.Call):
    """取编码实参节点：`read_text(encoding=None, errors=None)` 的位置参是第 1 个；
    `write_text(data, encoding=None, errors=None)` 的位置参是第 2 个；关键字形式取
    `encoding=`。缺省 ⇒ None。"""
    if call.func.attr == "read_text":
        if call.args:
            return call.args[0]
    elif call.func.attr == "write_text":
        if len(call.args) >= 2:
            return call.args[1]
    for kw in call.keywords:
        if kw.arg == "encoding":
            return kw.value
    return None


def _encoding_is_explicit_utf8(node) -> bool:
    """ocr2-557：显式且是 utf-8 才算合格。`encoding=None`（隐式 locale）与非 utf-8
    字面量都算债；运行期值不属字面量，无法证伪 ⇒ 不误伤。位置参 `read_text("utf-8")` 合格。"""
    if node is None:
        return False
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str) and node.value.lower().replace("-", "") == "utf8"
    return True


def _offenders(path: Path) -> list:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        # 单个坏/不可解码的 .py 不得让闸裸崩（ocr2-557）：记成一个 offender，交给调用方。
        return [f"<unparseable: {type(exc).__name__}>"]
    out = []
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr in ("read_text", "write_text")):
            if not _encoding_is_explicit_utf8(_encoding_node(n)):
                out.append(n.lineno)
    return out


def test_no_new_implicit_encoding_reads_writes() -> None:
    debt = dict(DEBT)
    offenders = {}
    for p in sorted((REPO / "tests").rglob("*.py")):
        rel = str(p.relative_to(REPO))
        if rel == "tests/unit/templates/test_test_explicit_encoding.py":
            continue
        got = _offenders(p)
        if got:
            offenders[rel] = len(got)
    grown = {k: v for k, v in offenders.items() if v > debt.get(k, 0)}
    assert not grown, "新增/变多的隐式编码读写（补 encoding=\"utf-8\" 或登记进 DEBT 并说明理由）：" + str(grown)


def test_debt_list_is_not_stale() -> None:
    """ocr2-558：从 `DEBT` 的键集重算（文件已删/改名 ⇒ 计 0），这样移除也会被报成 stale，
    而不是只在现存文件上走一圈（非零旧条目会永远留着）。"""
    stale = {}
    for rel, budget in DEBT.items():
        p = REPO / rel
        n = len(_offenders(p)) if p.is_file() else 0
        if n < budget:
            stale[rel] = {"budget": budget, "actual": n}
    assert not stale, "债已降/条目所指文件已删改，请同步 DEBT：" + str(stale)


def test_encoding_value_and_positional_are_checked() -> None:
    """ocr2-557：`encoding=None`/非 utf-8 字面量要算债；位置参 utf-8 要放行。"""
    import tempfile

    cases = {
        'p.read_text("utf-8")': 0,
        'p.read_text(encoding="utf-8")': 0,
        'p.read_text(encoding=None)': 1,
        'p.read_text(encoding="latin-1")': 1,
        'p.read_text()': 1,
        'p.write_text("x", "utf-8")': 0,
        'p.write_text("x")': 1,
    }
    for src, expected in cases.items():
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "m.py"
            f.write_text(src + "\n", encoding="utf-8")
            n = len(_offenders(f))
            assert n == expected, (src, n, expected)
