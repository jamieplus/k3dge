"""CHANGELOG 由**提交区间**生成（ADR-0004 §2.1.12）。

为何用真 git 仓：这一条的保证就是"区间内每个非机械提交都有条目"——桩掉 git 只剩同义反复。
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from unittest import TestCase

from k3dge.engine.changelog import build_notes_from_range, mechanical_commit


def _repo() -> Path:
    ws = Path(tempfile.mkdtemp())
    subprocess.run(["git", "init", "-q"], cwd=ws, capture_output=True)
    return ws


def _commit(ws: Path, subject: str, *, body: str = "") -> str:
    (ws / "f.txt").write_text(subject, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=ws, capture_output=True)
    msg = subject + (f"\n\n{body}" if body else "")
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "commit", "-q", "--no-verify", "-m", msg], cwd=ws, capture_output=True)
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ws, capture_output=True,
                          text=True).stdout.strip()


def _tag(ws: Path, name: str) -> None:
    r = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "tag", "-a", name, "-m", name],
        cwd=ws, capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr or r.stdout)


class TestMechanical(TestCase):
    def test_round_work_and_seal_commits_are_mechanical(self) -> None:
        self.assertTrue(mechanical_commit("a", "round work M10", ""))
        self.assertTrue(mechanical_commit("a", "chore(seal): seal milestone M10",
                                          "Seal-milestone: M10\nAudit-result: closed"))

    def test_normal_commit_is_not_mechanical(self) -> None:
        self.assertFalse(mechanical_commit("a", "feat(engine): add x", ""))
        self.assertFalse(mechanical_commit("a", "fix: correct y", ""))
        # 非 conventional **不是**机械件：它要进 `uncovered`（漏项信号），静默滤掉＝把病藏起来
        self.assertFalse(mechanical_commit("a", "some prose subject", ""))
        self.assertFalse(mechanical_commit("a", "unknown-type: x", ""))


class TestRangeNotes(TestCase):
    def test_covers_every_non_mechanical_commit_since_the_tag(self) -> None:
        ws = _repo()
        _commit(ws, "chore: seed")
        _tag(ws, "M9")
        _commit(ws, "feat(engine): add thing")
        _commit(ws, "fix(audit): repair thing")
        _commit(ws, "docs: explain thing")
        notes, uncovered = build_notes_from_range(ws)
        self.assertEqual(uncovered, [])
        for text in ("add thing", "repair thing", "explain thing"):
            self.assertIn(text, notes)
        self.assertIn("### Added", notes)
        self.assertIn("### Fixed", notes)
        self.assertIn("### Changed", notes)

    def test_filters_mechanical_commits(self) -> None:
        ws = _repo()
        _commit(ws, "chore: seed")
        _tag(ws, "M9")
        _commit(ws, "feat: real work")
        _commit(ws, "round work M10")
        _commit(ws, "chore(seal): seal milestone M10", body="Seal-milestone: M10")
        notes, _u = build_notes_from_range(ws)
        self.assertIn("real work", notes)
        self.assertNotIn("round work", notes)
        self.assertNotIn("seal milestone", notes)

    def test_no_previous_tag_yields_empty_notes(self) -> None:
        ws = _repo()
        _commit(ws, "feat: only work")
        self.assertEqual(build_notes_from_range(ws), ("", []))

    def test_untyped_subject_is_reported_not_invented(self) -> None:
        ws = _repo()
        _commit(ws, "chore: seed")
        _tag(ws, "M9")
        _commit(ws, "feat: typed work")
        _commit(ws, "unknown-type: work that cannot be filed")
        notes, uncovered = build_notes_from_range(ws)
        self.assertIn("typed work", notes)
        self.assertNotIn("work that cannot be filed", notes)   # 不猜它归哪一节
        self.assertEqual(len(uncovered), 1)   # 漏项信号（调用方告警，不静默吞掉）

    def test_previous_tag_selection_uses_highest_number(self) -> None:
        ws = _repo()
        _commit(ws, "chore: seed")
        _tag(ws, "M9")
        _commit(ws, "feat: in M10")
        _tag(ws, "M10")
        _commit(ws, "feat: in M11")
        notes, _u = build_notes_from_range(ws)
        self.assertIn("in M11", notes)
        self.assertNotIn("in M10", notes)     # 区间从最大号边界起算


class TestNoDoubleWrite(TestCase):
    """ADR-0004 §2.1.12：`task done` **不再**写 CHANGELOG（双写＝漏项与漂移的来源）。"""

    def test_mark_task_done_leaves_changelog_untouched(self) -> None:
        from k3dge.engine.task_write import mark_task_done

        ws = Path(tempfile.mkdtemp())
        (ws / "docs" / "tasks").mkdir(parents=True)
        changelog = ws / "CHANGELOG.md"
        changelog.write_text("# Changelog\n\n## [Unreleased]\n\n## [1.0.0] - 2026-01-01\n",
                             encoding="utf-8")
        before = changelog.read_text(encoding="utf-8")
        p = ws / "docs" / "tasks" / "2026-09-20-M10-feat-x.md"
        p.write_text("---\nstatus: in_progress\nmilestone: M10\npriority: P2\ndate: 2026-09-20\n---\n\n# X\n",
                     encoding="utf-8")
        ok, _msg, out = mark_task_done(ws, p.name)   # 入口收 ident（路径或其唯一子串）
        self.assertTrue(ok)
        self.assertTrue(out.name.endswith(".done.md"))
        self.assertEqual(changelog.read_text(encoding="utf-8"), before)
