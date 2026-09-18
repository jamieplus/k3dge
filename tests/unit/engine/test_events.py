"""events: append-only JSONL + rotate + read_events."""
import json
import tempfile
from pathlib import Path

from k3dge.engine import events


def test_emit_writes_jsonl():
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        events.emit(ws, "gate_pass", violations=0)
        f = ws / ".k3dge" / "events.jsonl"
        assert f.is_file()
        entry = json.loads(f.read_text(encoding="utf-8").strip())
        assert entry["evt"] == "gate_pass"
        assert entry["violations"] == 0
        assert "ts" in entry


def test_emit_appends():
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        events.emit(ws, "gate_pass")
        events.emit(ws, "audit_submit", job_id="abc")
        lines = (ws / ".k3dge" / "events.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        assert json.loads(lines[1])["job_id"] == "abc"


def test_emit_never_raises():
    events.emit(Path("/dev/null/fake"), "gate_pass")  # should not raise


def test_rotate_keeps_tail():
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        for i in range(1100):
            events.emit(ws, "evt", i=i)
        lines = (ws / ".k3dge" / "events.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(lines) <= 1000
        # tail kept: last entry is i=1099
        assert json.loads(lines[-1])["i"] == 1099
        # head truncated: first entry is well past i=0
        assert json.loads(lines[0])["i"] > 0


def test_read_events():
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        assert events.read_events(ws) == []
        for i in range(5):
            events.emit(ws, "evt", i=i)
        got = events.read_events(ws, last=3)
        assert len(got) == 3
        assert [e["i"] for e in got] == [2, 3, 4]


def test_next_persist_emits_next_event():
    """nextstep.persist() 内部复用 events.emit → events.jsonl 有 next 行。"""
    from k3dge.engine.nextstep import NextStep, persist
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        persist(ws, NextStep.from_state("seal_ready", "M10"))
        got = events.read_events(ws)
        assert len(got) == 1
        assert got[0]["evt"] == "next"
        assert got[0]["state"] == "seal_ready"
