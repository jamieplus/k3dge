"""`k3dge milestone seal-check <id>`：只读全量封板前置清单（#3）。

判据：全绿 ⇒ 退 0；有未过项 ⇒ 退 1（供 CI/脚本问"现在能封吗"）。不执行任何动作。
"""
from __future__ import annotations

import io
import os
from contextlib import redirect_stdout
from pathlib import Path

from k3dge.cli.main import main


def _ws(tmp_path: Path, preconditions: str) -> Path:
    (tmp_path / ".agent").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".agent" / "milestone").write_text("M10\n", encoding="utf-8")
    (tmp_path / ".agent" / "pipeline.toml").write_text(
        f"[checks.seal]\npreconditions = [{preconditions}]\n", encoding="utf-8")
    return tmp_path


def test_all_green_exits_zero(tmp_path, monkeypatch):
    ws = _ws(tmp_path, "")
    monkeypatch.chdir(ws)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(["milestone", "seal-check", "M10"])
    assert rc == 0
    assert "封板前置清单（M10）" in buf.getvalue()
    assert "✅" not in buf.getvalue() or "❌" not in buf.getvalue()   # 无失败项


def test_unmet_exits_one_and_lists_reason(tmp_path, monkeypatch):
    ws = _ws(tmp_path, '"audit_closed"')   # 空仓必失败：无 12 列报告
    monkeypatch.chdir(ws)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(["milestone", "seal-check", "M10"])
    out = buf.getvalue()
    assert rc == 1
    assert "❌ audit_closed" in out
    assert "先清 1 项" in out


def test_read_only_does_not_touch_state(tmp_path, monkeypatch):
    """只读：不得写侧车、不得改票/报告。"""
    ws = _ws(tmp_path, "")
    monkeypatch.chdir(ws)
    before = {p.relative_to(ws).as_posix() for p in ws.rglob("*")}
    with redirect_stdout(io.StringIO()):
        main(["milestone", "seal-check", "M10"])
    after = {p.relative_to(ws).as_posix() for p in ws.rglob("*")}
    # 只许出现命令日志（logs/ 是设计内的操作留痕）；**不得**产侧车 `.k3dge/next.json`
    new_paths = after - before
    assert all(pp.startswith("logs") for pp in new_paths), new_paths
