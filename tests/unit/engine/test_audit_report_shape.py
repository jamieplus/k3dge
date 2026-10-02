"""审计报告表形不变量：每条 finding 行必须正好 12 格、状态在闭集内。

竖线破表是这类报告的真实故障模式：描述或处置里混进一根裸 `|`，那行就多出格，
左数索引（含 `状态`）全部落进描述文本 —— 回填会写错列，统计会少算待修。
单元格内的竖线一律写全角 `｜`，本守卫保证这条约定不被悄悄破坏。
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
# `ID_RE`（仅小写前缀）已删：它曾把大写 ID（如 `D-1`）的行在 `_rows` 里预过滤掉，
# 调用方再查"坏行"永空（ocr2-111）。现在 `_rows` 不过滤 ID，大小写全覆盖。
STATUSES = {"待修", "已修", "有意留", "待验证", "待裁", "部分修"}


def _rows(text: str) -> list[tuple[int, list[str]]]:
    # 不在这里过滤短行/数据 ID：调用方要**看见**畸形行才能断言（ocr2-111/112）。
    # 旧写法先丢弃 `len<12` 与大写 ID（如 `D-1`），再让调用方查"有没有坏行" ⇒ 永空，测了寂寞。
    # 只跳过表头与分隔行（`ID`/`---` 字面），数据行无论 ID 形状全留。
    out = []
    for no, ln in enumerate(text.splitlines(), 1):
        if not ln.startswith("| "):
            continue
        cells = [x.strip() for x in ln.split("|")[1:-1]]
        if cells and cells[0] in ("ID", "---"):
            continue
        if cells and all(set(c) <= set("-: ") for c in cells):
            continue
        out.append((no, cells))
    return out


@pytest.mark.parametrize("path", sorted((REPO / "docs" / "reviews").glob("*.md")), ids=lambda p: p.name)
def test_finding_rows_have_exactly_twelve_cells(path: Path) -> None:
    if path.name == "LEFTOVERS.md":
        pytest.skip("留账本不是 finding 表")
    broken = [(no, len(c), c[0] if c else "") for no, c in _rows(path.read_text(encoding="utf-8")) if len(c) != 12]
    assert not broken, f"{path.name}: 竖线破表的行（行号, 格数, ID）: {broken[:5]}"


@pytest.mark.parametrize("path", sorted((REPO / "docs" / "reviews").glob("*.md")), ids=lambda p: p.name)
def test_status_column_is_in_closed_set(path: Path) -> None:
    if path.name == "LEFTOVERS.md":
        pytest.skip("留账本不是 finding 表")
    # 短行（<8 格）取不到状态槽：它们归 `broken` 管，这里只查够格的行（ocr2-112 同源）。
    bad = [(no, c[0], c[7]) for no, c in _rows(path.read_text(encoding="utf-8"))
           if len(c) >= 8 and c[7] and c[7] not in STATUSES]
    assert not bad, f"{path.name}: 状态列不在闭集 {sorted(STATUSES)}（行号, ID, 落进状态槽的文本）: {bad[:5]}"


@pytest.mark.parametrize("path", sorted((REPO / "docs" / "reviews").glob("*.md")), ids=lambda p: p.name)
def test_finding_table_is_contiguous(path: Path) -> None:
    """表头/分隔行/数据行必须**相邻且连续**——GFM 认表的形状条件。

    真实故障模式（2026-09-30 测试扫描报告）：一张 350 行的 finding 表，表头之后插进
    一节"续作口径"再回来分隔行——表头与 `| --- |` 不相邻 ⇒ 整表不渲染成表，读者看到的
    就是一堆裸竖线。格数/闭集两个守卫对此**全绿**（它们只看单行）。这里补上跨行不变量：
    ①每个 `| ID |` 表头的下一行必须是分隔行；②数据段被非表行打断之后，不得再出现
    形如数据行的管道行（那是被打断的第二张"影子表"）。
    """
    if path.name == "LEFTOVERS.md":
        pytest.skip("留账本的表是分节台账，本就不许单张连续")
    lines = path.read_text(encoding="utf-8").splitlines()
    heads = [i for i, l in enumerate(lines) if l.startswith("| ID |")]
    if not heads:
        pytest.skip("没有 finding 表")
    for h in heads:
        assert h + 1 < len(lines) and lines[h + 1].startswith("| ---"), \
            f"{path.name}:{h + 2} 不是分隔行（表头被打断，整表不渲染）：{lines[h + 1][:60]!r}"
        i = h + 2
        while i < len(lines) and lines[i].startswith("| "):
            i += 1
        shadow = [j + 1 for j in range(i, len(lines)) if re.match(r"^\| [a-z]+-\d+ \|", lines[j])]
        assert not shadow, f"{path.name}: 表被非表行打断后仍有数据行 {shadow[:5]}——把说明节挪到表外"


def test_report_kind_prefers_suffix_and_head_only_marker() -> None:
    """ocr2-214：文件名后缀权威；marker 只在文件首部查，正文表格里的引用示例不得翻桶。"""
    from k3dge.engine.audit_report import _report_kind

    # 后缀优先：正文里引用了 quality 示例也不得把 `-scan.md` 翻成 quality
    body = "# 报告\n\n" + "\n".join(f"行 {i}" for i in range(10))
    body += "\n<!-- k3dge:kind: quality -->\n"
    assert _report_kind("2026-09-29-M11-ocr-scan.md", body) == "scan"
    # 无后缀时，marker 落在首部（前 5 行）才认
    assert _report_kind("foo.md", "<!-- k3dge:kind: quality -->\n正文") == "quality"
    assert _report_kind("foo.md", body) == "audit"
    # 默认是审计类
    assert _report_kind("2026-x-audit.md", "正文") == "audit"

