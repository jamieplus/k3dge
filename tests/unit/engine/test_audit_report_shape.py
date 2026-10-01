"""审计报告表形不变量：每条 finding 行必须正好 12 格、状态在闭集内。

竖线破表是这类报告的真实故障模式：描述或处置里混进一根裸 `|`，那行就多出格，
左数索引（含 `状态`）全部落进描述文本 —— 回填会写错列，统计会少算待修。
单元格内的竖线一律写全角 `｜`，本守卫保证这条约定不被悄悄破坏。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
ID_RE = re.compile(r"[a-z]+-\d+$")
STATUSES = {"待修", "已修", "有意留", "待验证", "待裁", "部分修"}


def _rows(text: str) -> list[tuple[int, list[str]]]:
    out = []
    for no, ln in enumerate(text.splitlines(), 1):
        if not ln.startswith("| "):
            continue
        cells = [x.strip() for x in ln.split("|")[1:-1]]
        if len(cells) < 12 or not ID_RE.match(cells[0]):
            continue
        out.append((no, cells))
    return out


@pytest.mark.parametrize("path", sorted((REPO / "docs" / "reviews").glob("*.md")), ids=lambda p: p.name)
def test_finding_rows_have_exactly_twelve_cells(path: Path) -> None:
    if path.name == "LEFTOVERS.md":
        pytest.skip("留账本不是 finding 表")
    broken = [(no, len(c), c[0]) for no, c in _rows(path.read_text(encoding="utf-8")) if len(c) != 12]
    assert not broken, f"{path.name}: 竖线破表的行（行号, 格数, ID）: {broken[:5]}"


@pytest.mark.parametrize("path", sorted((REPO / "docs" / "reviews").glob("*.md")), ids=lambda p: p.name)
def test_status_column_is_in_closed_set(path: Path) -> None:
    if path.name == "LEFTOVERS.md":
        pytest.skip("留账本不是 finding 表")
    bad = [(no, c[0], c[7]) for no, c in _rows(path.read_text(encoding="utf-8")) if c[7] not in STATUSES]
    assert not bad, f"{path.name}: 状态列不在闭集（行号, ID, 落进状态槽的文本）: {bad[:5]}"


@pytest.mark.parametrize("path", sorted((REPO / "docs" / "reviews").glob("*.md")), ids=lambda p: p.name)
def test_status_column_in_closed_set(path: Path) -> None:
    if path.name == "LEFTOVERS.md":
        pytest.skip("留账本不是 finding 表")
    odd = [(no, c[0], c[7]) for no, c in _rows(path.read_text(encoding="utf-8"))
           if c[7] and c[7] not in STATUSES]
    assert not odd, f"{path.name}: 状态列不在闭集 {sorted(STATUSES)} 的行: {odd[:5]}"

