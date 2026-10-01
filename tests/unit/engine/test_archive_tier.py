"""归档契约：增量去向提醒（ADR-0023 §2.2）+ CLI --include-archive 低权威头。"""

import io
import subprocess
from contextlib import redirect_stdout
from pathlib import Path

from k3dge.cli.main import main
from k3dge.engine.pure_refs import find_unguarded_archives

_ENV = {"PATH": "/usr/bin:/bin", "HOME": "/tmp", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def _git(ws: Path, *a: str) -> None:
    subprocess.run(["git", "-C", str(ws), *a], check=True, capture_output=True, env=_ENV)


def test_unguarded_archive_detected(tmp_path: Path) -> None:
    """归档去向标记（ADR-0023 §2.2）：本轮增量里进 `archive/` 但缺标记的报出来。

    迁自 `doc_audit._new_archive_without_note`（doc-audit 路径已退休）；口径改为
    **显式传入本轮改动集**（调用方是 pre-commit 的 staged 列表），不再自己跑 diff。
    """
    d = tmp_path / "docs" / "memo" / "archive"
    d.mkdir(parents=True)
    (d / "x.md").write_text("# x\n", encoding="utf-8")                # 无去向标记
    (d / "y.md").write_text("# y\nSuperseded-by: z\n", encoding="utf-8")  # 有标记
    (tmp_path / "docs" / "memo" / "live.md").write_text("# live\n", encoding="utf-8")
    res = find_unguarded_archives(
        tmp_path, ["docs/memo/archive/x.md", "docs/memo/archive/y.md", "docs/memo/live.md"])
    assert [c for c, _ in res] == ["ARCHIVE_NO_DEST"]
    assert "archive/x.md" in res[0][1]


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
