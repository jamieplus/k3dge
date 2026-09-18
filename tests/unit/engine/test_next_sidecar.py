"""next-step sidecar: persist() 写 .k3dge/next.json, emit() 写 + 打印。"""
import json
import tempfile
from pathlib import Path

from k3dge.engine.nextstep import NextStep, emit, persist


def _ns():
    return NextStep.from_state("seal_ready", "M10")


def test_persist_writes_sidecar():
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        ns = _ns()
        persist(ws, ns)
        sidecar = ws / ".k3dge" / "next.json"
        assert sidecar.is_file()
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        assert data["state"] == "seal_ready"
        assert data["milestone"] == "M10"
        assert "ask" in data


def test_persist_is_idempotent():
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        persist(ws, NextStep.from_state("audit_suggested", "M5"))
        persist(ws, NextStep.from_state("sealed", "M5"))
        data = json.loads((ws / ".k3dge" / "next.json").read_text(encoding="utf-8"))
        assert data["state"] == "sealed"


def test_persist_never_raises():
    """persist on a path that can't be written should not raise."""
    ns = _ns()
    persist(Path("/dev/null/fake"), ns)  # should not raise


def test_emit_writes_sidecar_and_returns_text():
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        ns = _ns()
        text = emit(ws, ns)
        assert "[NEXT]" in text
        assert "seal_ready" in text
        sidecar = ws / ".k3dge" / "next.json"
        assert sidecar.is_file()


def test_emit_with_stream_prints(capsys):
    import sys
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        ns = _ns()
        emit(ws, ns, stream=sys.stdout)
        captured = capsys.readouterr()
        assert "[NEXT]" in captured.out


def test_emit_without_stream_no_print(capsys):
    import sys
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        ns = _ns()
        emit(ws, ns)  # no stream
        captured = capsys.readouterr()
        assert captured.out == ""
