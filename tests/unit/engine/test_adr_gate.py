"""封版 ADR 硬闸：全 Accepted + 可解析落地指针。"""
import tempfile
from pathlib import Path

from k3dge.engine import adr_gate


def _ws(d, adrs):
    root = Path(d)
    (root / "docs" / "adr").mkdir(parents=True)
    (root / "docs" / "specs" / "x").mkdir(parents=True)
    (root / "docs" / "specs" / "x" / "spec.md").write_text("# spec\n", encoding="utf-8")
    for name, body in adrs.items():
        (root / "docs" / "adr" / name).write_text(body, encoding="utf-8")
    return root


def test_no_adrs_pass():
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, {})
        assert adr_gate.adrs_all_accepted(ws) is None
        assert adr_gate.adr_landed(ws) is None


def test_all_accepted_and_landed_pass():
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, {
            "0001-a.md": "---\nStatus: Accepted\nLanded-by: docs/specs/x/spec.md §2\n---\n# ADR-0001\n",
        })
        assert adr_gate.adrs_all_accepted(ws) is None
        assert adr_gate.adr_landed(ws) is None


def test_draft_blocks():
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, {"0001-a.md": "---\nStatus: Draft\n---\n# ADR-0001\n"})
        assert "未 Accepted" in (adr_gate.adrs_all_accepted(ws) or "")


def test_missing_or_bad_pointer_blocks():
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, {"0001-a.md": "---\nStatus: Accepted\n---\n# ADR-0001\n"})
        assert "缺可解析落地指针" in (adr_gate.adr_landed(ws) or "")
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, {"0001-a.md": "---\nStatus: Accepted\nLanded-by: docs/nope.md\n---\n# ADR-0001\n"})
        assert "指针不可解析" in (adr_gate.adr_landed(ws) or "")
