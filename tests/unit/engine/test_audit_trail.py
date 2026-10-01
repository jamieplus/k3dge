"""审计痕迹只可追加（AUDIT_TRAIL_APPEND_ONLY）静态闸。"""

from pathlib import Path

from k3dge.engine.evaluator import ConsistencyEngine


def _ws(tmp_path: Path, body: str) -> Path:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "a.py").write_text(body, encoding="utf-8")
    return tmp_path


def test_flags_logs_write_text(tmp_path: Path) -> None:
    ws = _ws(tmp_path, 'from pathlib import Path\n\n\ndef f(p):\n    (p / "logs" / "x.log").write_text("z")\n')
    v = ConsistencyEngine(ws)._check_audit_trail()
    assert any(x.rule_id == "AUDIT_TRAIL_APPEND_ONLY" for x in v), v


def test_flags_logs_open_write_mode(tmp_path: Path) -> None:
    ws = _ws(tmp_path, 'def f(p):\n    open(p / "logs" / "x.log", "w").write("z")\n')
    v = ConsistencyEngine(ws)._check_audit_trail()
    assert any(x.rule_id == "AUDIT_TRAIL_APPEND_ONLY" for x in v), v


def test_allows_append_open(tmp_path: Path) -> None:
    ws = _ws(tmp_path, 'def f(p):\n    open(p / "logs" / "x.log", "a").write("z")\n')
    assert ConsistencyEngine(ws)._check_audit_trail() == []
