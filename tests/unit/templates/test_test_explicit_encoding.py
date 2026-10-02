"""测试面的读写必须显式 `encoding="utf-8"`（M12 票 `tests_explicit_encoding` 的推进闸）。"""

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


def _offenders(path: Path) -> list:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr in ("read_text", "write_text")
                and not any(k.arg == "encoding" for k in n.keywords)):
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
    stale = {k: v for k, v in DEBT.items()}
    for p in sorted((REPO / "tests").rglob("*.py")):
        rel = str(p.relative_to(REPO))
        n = len(_offenders(p)) if rel in stale else 0
        if rel in stale and n < stale[rel]:
            stale[rel] = n
    lowered = {k: v for k, v in stale.items() if v < DEBT[k]}
    assert not lowered, "债已降，请把 tests/unit/templates/test_test_explicit_encoding.py 的 DEBT 一起改小：" + str(lowered)
