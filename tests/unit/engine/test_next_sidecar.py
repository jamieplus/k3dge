"""next-step sidecar：单判定 `persist`（替换）/ 本轮多处理点 `emit`/`emit_all`（upsert+排序）。

形状：`{"next": [card...], "primary": <state>}`（旧单条形状读侧兼容，见 load_persisted）。
"""
import json
import tempfile
from pathlib import Path

from k3dge.engine.nextstep import (
    NextStep,
    begin_run,
    emit,
    emit_all,
    load_all,
    load_persisted,
    persist,
)


def _ns(state="seal_ready", mid="M10"):
    return NextStep.from_state(state, mid)


def _raw(ws) -> dict:
    return json.loads((ws / ".k3dge" / "next.json").read_text(encoding="utf-8"))


def test_persist_writes_sidecar():
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        persist(ws, _ns())
        data = _raw(ws)
        assert data["primary"] == "seal_ready"
        card = data["next"][0]
        assert card["state"] == "seal_ready"
        assert card["milestone"] == "M10"
        # 陈述式事实 + 成对选项（ADR-0026 §2.2）；question 只给有应答通道的消费者
        assert "封板与否由你决定" in card["fact"]
        assert not card["fact"].rstrip().endswith(("？", "?"))
        assert len(card["options"]) >= 2
        assert "封板？" in card["question"]
        assert "ask" not in card and "if_y" not in card and "note" not in card


def test_persist_replaces():
    """`persist` 是单判定流程用的**替换**语义（seal_flow / milestone_audit 各只判一个）。"""
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        persist(ws, NextStep.from_state("audit_suggested", "M5"))
        persist(ws, NextStep.from_state("sealed", "M5"))
        data = _raw(ws)
        assert data["primary"] == "sealed"
        assert [c["state"] for c in data["next"]] == ["sealed"]


def test_persist_never_raises():
    persist(Path("/dev/null/fake"), _ns())  # should not raise


def test_emit_upserts_and_orders_by_priority():
    """一轮内多处理点：同 state 去重、按 priority 排、primary＝最小 priority。"""
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        begin_run(ws)
        emit(ws, _ns("seal_ready"))                 # priority 4
        emit(ws, _ns("ratchet_open"))                  # priority 5
        emit(ws, NextStep.from_state("pending_findings", "M10", pending=2))   # priority 1
        data = _raw(ws)
        assert [c["state"] for c in data["next"]] == ["pending_findings", "seal_ready", "ratchet_open"]
        assert data["primary"] == "pending_findings"
        assert [c["priority"] for c in data["next"]] == [1, 4, 5]


def test_emit_same_state_dedupes():
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        begin_run(ws)
        emit(ws, _ns("seal_ready"))
        emit(ws, _ns("seal_ready"))
        assert len(_raw(ws)["next"]) == 1


def test_begin_run_clears_previous_run():
    """一轮开始的边界：上一条命令的处理点不得留到这一轮。"""
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        emit(ws, _ns("seal_ready"))
        assert load_all(ws)
        begin_run(ws)
        assert load_all(ws) == []
        assert load_persisted(ws) is None


def test_emit_all_orders_and_writes_all():
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        begin_run(ws)
        emit_all(ws, [_ns("seal_ready"), _ns("ratchet_open"),
                      NextStep.from_state("audit_open", "M10", pending=3)])
        data = _raw(ws)
        assert [c["state"] for c in data["next"]] == ["audit_open", "seal_ready", "ratchet_open"]
        assert data["primary"] == "audit_open"


def test_emit_all_prints_in_priority_order(capsys):
    import sys

    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        begin_run(ws)
        emit_all(ws, [_ns("seal_ready"), NextStep.from_state("pending_findings", "M10", pending=1)],
                 stream=sys.stdout)
        out = capsys.readouterr().out
        assert out.index("pending_findings") < out.index("seal_ready")


def test_load_persisted_accepts_legacy_single_shape():
    """向后兼容：旧侧车是单条 `{"state": ...}` ⇒ 仍能读出主处理点。"""
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        (ws / ".k3dge").mkdir(parents=True)
        (ws / ".k3dge" / "next.json").write_text(
            json.dumps({"state": "sealed", "milestone": "M5", "fact": "旧形状"}), encoding="utf-8")
        assert load_persisted(ws)["state"] == "sealed"
        assert [c["state"] for c in load_all(ws)] == ["sealed"]


def test_emit_writes_sidecar_and_returns_text():
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        text = emit(ws, _ns())
        assert "[NEXT]" in text and "seal_ready" in text
        assert (ws / ".k3dge" / "next.json").is_file()


def test_emit_with_stream_prints(capsys):
    import sys

    with tempfile.TemporaryDirectory() as d:
        emit(Path(d), _ns(), stream=sys.stdout)
        assert "[NEXT]" in capsys.readouterr().out


def test_emit_without_stream_no_print(capsys):
    with tempfile.TemporaryDirectory() as d:
        emit(Path(d), _ns())
        assert capsys.readouterr().out == ""
