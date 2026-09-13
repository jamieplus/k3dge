"""归档契约：增量去向提醒（ADR-0023 §2.2）+ CLI --include-archive 低权威头。"""
from __future__ import annotations

import io
import json
import subprocess
from contextlib import redirect_stdout
from pathlib import Path

from k3dge.cli.main import main
from k3dge.engine.milestone import _new_archive_without_note

_ENV = {"PATH": "/usr/bin:/bin", "HOME": "/tmp", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def _git(ws: Path, *a: str) -> None:
    subprocess.run(["git", "-C", str(ws), *a], check=True, capture_output=True, env=_ENV)


def test_new_archive_without_note_only_incremental(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-qb", "main", str(tmp_path)], check=True, capture_output=True, env=_ENV)
    d = tmp_path / "docs" / "memo" / "archive"
    d.mkdir(parents=True)
    (d / "x.md").write_text("# x\n", encoding="utf-8")               # 新进档，无去向标记
    (d / "y.md").write_text("# y\nSuperseded-by: z\n", encoding="utf-8")  # 有标记
    _git(tmp_path, "add", "-A")
    res = _new_archive_without_note(tmp_path)
    assert any(p.endswith("archive/x.md") for p in res)
    assert not any(p.endswith("archive/y.md") for p in res)


def test_doc_list_archive_prints_low_authority_header(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".agent").mkdir()
    (tmp_path / ".git").mkdir()
    d = tmp_path / "docs" / "reviews" / "archive"
    d.mkdir(parents=True)
    (d / "old.md").write_text("# old\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(["doc", "list", "--type", "reviews", "--include-archive"])
    out = buf.getvalue()
    assert rc == 0
    assert "低权威层" in out and "archive/old.md" in out
