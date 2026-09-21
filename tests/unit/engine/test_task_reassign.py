"""里程碑重挂（ADR-0004 §2.1.9）：票的里程碑事实＝frontmatter + 文件名两处，必须同改。"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import TestCase

from k3dge.engine import pure_refs
from k3dge.engine.task_write import (
    build_task_name,
    reassign_milestone,
    reassign_task_milestone,
    split_task_name,
)


def _ws() -> Path:
    ws = Path(tempfile.mkdtemp())
    (ws / "docs" / "tasks").mkdir(parents=True)
    (ws / ".agent").mkdir()
    (ws / ".agent" / "milestone").write_text("M10\n", encoding="utf-8")
    return ws


def _task(ws: Path, name: str, milestone: str = "M10") -> Path:
    p = ws / "docs" / "tasks" / name
    p.write_text(
        f"---\nstatus: idea\nmilestone: {milestone}\npriority: P2\ndate: 2026-09-20\n---\n\n# X\n",
        encoding="utf-8",
    )
    return p


class TestNameParts(TestCase):
    def test_split_and_rebuild_roundtrip(self) -> None:
        parts = split_task_name("2026-09-20-M10-feat-x_y.done.md")
        self.assertEqual(parts["date"], "2026-09-20")
        self.assertEqual(parts["ms"], "M10")
        self.assertEqual(parts["type"], "feat")
        self.assertEqual(parts["slug"], "x_y")
        self.assertEqual(parts["done"], ".done")
        self.assertEqual(build_task_name(parts, "M11"), "2026-09-20-M11-feat-x_y.done.md")
        self.assertEqual(build_task_name(parts, None), "2026-09-20-feat-x_y.done.md")

    def test_unparsable_name_is_none(self) -> None:
        self.assertIsNone(split_task_name("random.md"))
        self.assertIsNone(split_task_name("2026-09-20-M10-unknowntype-x.md"))


class TestReassignTask(TestCase):
    def test_moves_frontmatter_and_filename_together(self) -> None:
        ws = _ws()
        p = _task(ws, "2026-09-20-M10-feat-x.md")
        ok, msg, newp = reassign_task_milestone(ws, p, "M11")
        self.assertTrue(ok, msg)
        self.assertEqual(newp.name, "2026-09-20-M11-feat-x.md")
        self.assertFalse(p.exists())
        # 闸必须绿：两处同改才算重挂成功（半吊子会被 TASK_MILESTONE_MISMATCH 拦）
        rel = newp.relative_to(ws).as_posix()
        self.assertEqual(pure_refs.check_task_consistency(rel, newp.read_text(encoding="utf-8")), [])

    def test_idempotent(self) -> None:
        ws = _ws()
        p = _task(ws, "2026-09-20-M10-feat-x.md")
        reassign_task_milestone(ws, p, "M11")
        again = ws / "docs" / "tasks" / "2026-09-20-M11-feat-x.md"
        ok, msg, newp = reassign_task_milestone(ws, again, "M11")
        self.assertTrue(ok, msg)
        self.assertIn("幂等", msg)
        self.assertEqual(newp, again)

    def test_dry_run_touches_nothing(self) -> None:
        ws = _ws()
        p = _task(ws, "2026-09-20-M10-feat-x.md")
        ok, msg, _ = reassign_task_milestone(ws, p, "M11", dry_run=True)
        self.assertTrue(ok, msg)
        self.assertIn("[dry-run]", msg)
        self.assertTrue(p.exists())
        self.assertIn("milestone: M10", p.read_text(encoding="utf-8"))

    def test_refuses_bad_id_and_bad_name(self) -> None:
        ws = _ws()
        p = _task(ws, "2026-09-20-M10-feat-x.md")
        self.assertFalse(reassign_task_milestone(ws, p, "M 11")[0])       # 非法 id
        bad = _task(ws, "2026-09-20-random.md")
        self.assertFalse(reassign_task_milestone(ws, bad, "M11")[0])      # 名字拆不出段位

    def test_removing_milestone_drops_the_segment(self) -> None:
        ws = _ws()
        p = _task(ws, "2026-09-20-M10-feat-x.md")
        ok, msg, newp = reassign_task_milestone(ws, p, None)
        self.assertTrue(ok, msg)
        self.assertEqual(newp.name, "2026-09-20-feat-x.md")
        self.assertNotIn("milestone:", newp.read_text(encoding="utf-8"))


class TestReassignBulk(TestCase):
    def test_only_matching_milestone_moves(self) -> None:
        ws = _ws()
        _task(ws, "2026-09-20-M10-feat-a.md")
        _task(ws, "2026-09-20-M10-fix-b.done.md")
        _task(ws, "2026-09-19-M9-docs-c.md", milestone="M9")
        ok, lines = reassign_milestone(ws, "M10", "M11")
        self.assertTrue(ok, lines)
        names = sorted(p.name for p in (ws / "docs" / "tasks").glob("*.md"))
        self.assertEqual(names, ["2026-09-19-M9-docs-c.md",
                                 "2026-09-20-M11-feat-a.md",
                                 "2026-09-20-M11-fix-b.done.md"])

    def test_nothing_to_do_is_ok(self) -> None:
        ws = _ws()
        _task(ws, "2026-09-20-M11-feat-a.md", milestone="M11")
        ok, lines = reassign_milestone(ws, "M10", "M11")
        self.assertTrue(ok, lines)
        self.assertIn("没有 M10 的票", lines[0])


class TestBoundaryNudge(TestCase):
    """`TASK_MILESTONE_AFTER_BOUNDARY`（advisory）：边界之后新增的票仍挂在边界那一版。"""

    def _repo(self) -> Path:
        import subprocess

        ws = Path(tempfile.mkdtemp())
        (ws / "docs" / "tasks").mkdir(parents=True)
        (ws / ".agent").mkdir()
        (ws / ".agent" / "milestone").write_text("M10\n", encoding="utf-8")

        def g(*a):
            return subprocess.run(["git", "-C", str(ws), *a], capture_output=True, text=True).stdout

        g("init", "-q")
        (ws / "seed.md").write_text("seed\n", encoding="utf-8")
        g("add", "-A")
        g("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--no-verify", "-m", "chore: seed")
        g("-c", "user.name=t", "-c", "user.email=t@t", "tag", "-a", "M10", "-m", "boundary")
        return ws

    def test_task_added_after_boundary_and_still_labelled_is_reported(self) -> None:
        from k3dge.engine import doc_catalog, milestone_files

        ws = self._repo()
        _task(ws, "2026-09-20-M10-feat-late.md")          # 边界之后新增，仍挂 M10
        rows = milestone_files.tasks_after_boundary(ws)
        self.assertEqual([r[0] for r in rows], ["docs/tasks/2026-09-20-M10-feat-late.md"])
        self.assertEqual(rows[0][1], "M10")
        codes = [v.rule_id for v in doc_catalog.validate_docs(ws, ["tasks"])
                 if v.rule_id == "TASK_MILESTONE_AFTER_BOUNDARY"]
        self.assertEqual(codes, ["TASK_MILESTONE_AFTER_BOUNDARY"])

    def test_reassigned_task_is_not_reported(self) -> None:
        from k3dge.engine import milestone_files

        ws = self._repo()
        p = _task(ws, "2026-09-20-M10-feat-late.md")
        reassign_task_milestone(ws, p, "M11")
        self.assertEqual(milestone_files.tasks_after_boundary(ws), [])

    def test_advisory_never_blocks(self) -> None:
        from k3dge.engine import doc_catalog, gate_facts
        from k3dge.engine.models import Violation

        self.assertEqual(gate_facts.severity("TASK_MILESTONE_AFTER_BOUNDARY"), "warn")
        v = Violation("TASK_MILESTONE_AFTER_BOUNDARY", "m",
                      file_path="docs/tasks/x.md", detail={"path": "docs/tasks/x.md", "milestone": "M10"})
        self.assertTrue(v.format().startswith("[GATE WARN]"))
        self.assertIn("k3dge milestone reassign M10", v.format())
