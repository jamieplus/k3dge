"""硬闸契约加载器：缺省 / 覆盖 / 坏配置回落缺省。"""
import tempfile
from pathlib import Path

from k3dge.engine import gates


def _ws(d, body=None):
    p = Path(d) / ".agent"
    p.mkdir(parents=True)
    if body is not None:
        (p / "gates.toml").write_text(body, encoding="utf-8")
    return Path(d)


def test_defaults_when_absent():
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d)
        assert gates.get(ws, "audit_trigger", "c2_nesting_max") == 5
        assert gates.get(ws, "audit_trigger", "volume_max") == 8


def test_override_keeps_other_defaults():
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, "[audit_trigger]\nc2_nesting_max = 3\n")
        assert gates.get(ws, "audit_trigger", "c2_nesting_max") == 3
        assert gates.get(ws, "audit_trigger", "volume_max") == 8


def test_malformed_falls_back_to_defaults():
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, "this is not toml = = =\n")
        assert gates.get(ws, "audit_trigger", "c2_nesting_max") == 5


def test_seal_preconditions_default_and_override():
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d)
        assert gates.preconditions(ws, "seal") == ["tasks_all_done", "align_pass", "guides_filled"]
    with tempfile.TemporaryDirectory() as d:
        ws = _ws(d, "[checks.seal]\npreconditions = []\n")
        assert gates.preconditions(ws, "seal") == []
        assert gates.get(ws, "audit_trigger", "c2_nesting_max") == 5
