"""审计痕迹只可追加（AUDIT_TRAIL_APPEND_ONLY）静态闸。"""

from pathlib import Path

from k3dge.engine.evaluator import ConsistencyEngine


def _ws(tmp_path: Path, body: str) -> Path:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "a.py").write_text(body, encoding="utf-8")
    return tmp_path


def _codes(ws: Path) -> list:
    """私有 seam 只在这**一行**耦合（t-078）：helper 改名/并闸时修一处，而不是每个测；
    返回**类型无关**（list()），哪天检查器改回 tuple/generator 也不绑架判据。
    空表还要防 vacuous：`_positive_control()` 证明本夹具确实会被分析到。
    """
    return [v.rule_id for v in list(ConsistencyEngine(ws)._check_audit_trail())]


def _positive_control() -> None:
    """自造一个**含必报代码**的工作区，确认本闸在该路径约定下真的会响（t-077b）。
    不往被测目录塞东西（那会污染负测的空断言），只证"分析确实发生"。"""
    import tempfile
    from pathlib import Path as _P
    with tempfile.TemporaryDirectory() as d:
        ctl = _P(d)
        (ctl / "src" / "pkg").mkdir(parents=True)
        (ctl / "src" / "pkg" / "ctl.py").write_text(
            'def f(p):\n    open(p / "logs" / "x.log", "w").write("z")\n', encoding="utf-8")
        assert _codes(ctl) == ["AUDIT_TRAIL_APPEND_ONLY"], "正对照失效：本闸不再分析 src/pkg/*.py"


def test_flags_logs_write_text(tmp_path: Path) -> None:
    ws = _ws(tmp_path, 'from pathlib import Path\n\n\ndef f(p):\n    (p / "logs" / "x.log").write_text("z")\n')
    assert _codes(ws) == ["AUDIT_TRAIL_APPEND_ONLY"]


def test_flags_logs_open_write_mode(tmp_path: Path) -> None:
    ws = _ws(tmp_path, 'def f(p):\n    open(p / "logs" / "x.log", "w").write("z")\n')
    assert _codes(ws) == ["AUDIT_TRAIL_APPEND_ONLY"]


def test_allows_append_open(tmp_path: Path) -> None:
    _positive_control()                      # 先证本闸会分析该路径约定（t-077b），否则空断言 vacuous
    ws = _ws(tmp_path, 'def f(p):\n    open(p / "logs" / "x.log", "a").write("z")\n')
    assert _codes(ws) == []


def test_flags_logs_exclusive_mode_x(tmp_path: Path) -> None:
    """`"x"`（create-only）同样毁已有行——判据闭集含 wx 两位，此前只测过 w（t-076）。"""
    ws = _ws(tmp_path, 'def f(p):\n    open(p / "logs" / "x.log", "x").write("z")\n')
    assert _codes(ws) == ["AUDIT_TRAIL_APPEND_ONLY"]


def test_flags_logs_keyword_mode(tmp_path: Path) -> None:
    """关键字形状 `open(..., mode="w")`：回填说明（M9 票 code-4）点名支持，却没测钉（t-076）。"""
    ws = _ws(tmp_path, 'def f(p):\n    open(p / "logs" / "x.log", mode="w").write("z")\n')
    assert _codes(ws) == ["AUDIT_TRAIL_APPEND_ONLY"]


def test_allows_default_read_open(tmp_path: Path) -> None:
    """负空间：无 mode 的 `open()` 默认 `r` 只读——不得误伤（t-076）。"""
    _positive_control()
    ws = _ws(tmp_path, 'def f(p):\n    return open(p / "logs" / "x.log").read()\n')
    assert _codes(ws) == []
