import pathlib
import tempfile
import unittest

from k3dge.engine.milestone import (
    MilestoneTask,
    scan_milestone_tasks,
    run_milestone_alignment,
    seal_milestone,
    _ALIGN_STUB_MARKER,
    _align_pass_marker,
)


def _write_task(path: pathlib.Path, status: str, milestone: str) -> None:
    path.write_text(
        f"# Task\n- **Status**: {status}\n- **Milestone**: {milestone}\n",
        encoding="utf-8",
    )


class TestMilestone(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = pathlib.Path(self.tmp.name)
        (self.ws / "docs" / "tasks").mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_status_regex_in_progress(self) -> None:
        p = self.ws / "docs/tasks/2026-08-22-todo.md"
        _write_task(p, "in-progress", "M99")
        tasks = scan_milestone_tasks(self.ws, "M99")
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].status, "in-progress")

    def test_scan_filters_milestone(self) -> None:
        _write_task(self.ws / "docs/tasks/a.md", "done", "M1")
        _write_task(self.ws / "docs/tasks/b.md", "done", "M2")
        self.assertEqual(len(scan_milestone_tasks(self.ws, "M1")), 1)
        self.assertEqual(len(scan_milestone_tasks(self.ws, "M2")), 1)

    def test_seal_archives_to_archive_dir(self) -> None:
        # Use scaffold-like tasks dir with git for k3dge check to pass
        import json
        import subprocess

        (self.ws / ".agent").mkdir(exist_ok=True)
        (self.ws / ".agent" / "manifest.json").write_text(
            json.dumps({"package_root": "src", "domains": {}}), encoding="utf-8"
        )
        (self.ws / "src").mkdir(exist_ok=True)
        (_write_task(self.ws / "docs/tasks/2026-08-22-a.md", "done", "M9") if True else None)
        _write_task(self.ws / "docs/tasks/2026-08-22-b.md", "done", "M9")
        # Gate artifacts: audit review for M9 + SUMMARY.md index entry + no guide TODOs
        (self.ws / "docs/reviews").mkdir(parents=True)
        (self.ws / "docs/reviews/2026-08-23-M9-align.md").write_text(
            f"# Review M9\n{_align_pass_marker('M9')}\n- Regression: PASS\n", encoding="utf-8"
        )
        (self.ws / "docs/reviews/SUMMARY.md").write_text("## M9 audit\n- **Milestone**: M9\n", encoding="utf-8")
        # Minimal git for ConsistencyEngine
        subprocess.run(["git", "init", "-b", "main"], cwd=self.ws, capture_output=True)
        subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=self.ws, capture_output=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=self.ws, capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=self.ws, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=self.ws, capture_output=True)

        ok, msg = seal_milestone(self.ws, "M9")
        self.assertTrue(ok, msg)
        self.assertTrue((self.ws / "docs/tasks/archive/M9/2026-08-22-a.md").exists())
        self.assertTrue((self.ws / "docs/tasks/archive/M9/2026-08-22-b.md").exists())
        self.assertFalse((self.ws / "docs/tasks/2026-08-22-a.md").exists())

    def test_seal_rejects_missing_review(self) -> None:
        _write_task(self.ws / "docs/tasks/x.md", "done", "M10")
        ok, msg = seal_milestone(self.ws, "M10")
        self.assertFalse(ok)
        self.assertIn("SEAL REJECTED", msg)
        self.assertIn("audit review", msg)
        # nothing archived
        self.assertTrue((self.ws / "docs/tasks/x.md").exists())

    def test_seal_rejects_missing_summary_index(self) -> None:
        _write_task(self.ws / "docs/tasks/x.md", "done", "M11")
        (self.ws / "docs/reviews").mkdir(parents=True)
        (self.ws / "docs/reviews/2026-08-23-M11-align.md").write_text(
            f"# Review M11\n{_align_pass_marker('M11')}\n", encoding="utf-8"
        )
        ok, msg = seal_milestone(self.ws, "M11")
        self.assertFalse(ok)
        self.assertIn("SUMMARY.md", msg)

    def test_seal_rejects_substring_milestone_id(self) -> None:
        _write_task(self.ws / "docs/tasks/x.md", "done", "M1")
        (self.ws / "docs/reviews").mkdir(parents=True)
        (self.ws / "docs/reviews/2026-08-23-M10-align.md").write_text("# Review M10\n", encoding="utf-8")
        (self.ws / "docs/reviews/SUMMARY.md").write_text("## M10 audit\n", encoding="utf-8")
        ok, msg = seal_milestone(self.ws, "M1")
        self.assertFalse(ok)
        self.assertIn("SEAL REJECTED", msg)
        self.assertTrue((self.ws / "docs/tasks/x.md").exists())

    def test_seal_rejects_summary_substring(self) -> None:
        _write_task(self.ws / "docs/tasks/x.md", "done", "M1")
        (self.ws / "docs/reviews").mkdir(parents=True)
        (self.ws / "docs/reviews/2026-08-23-M1-align.md").write_text(
            f"# Review M1\n{_align_pass_marker('M1')}\n", encoding="utf-8"
        )
        (self.ws / "docs/reviews/SUMMARY.md").write_text("## M10 audit\n", encoding="utf-8")
        ok, msg = seal_milestone(self.ws, "M1")
        self.assertFalse(ok)
        self.assertIn("SUMMARY.md", msg)
        self.assertTrue((self.ws / "docs/tasks/x.md").exists())

    def test_rejects_path_like_milestone_id(self) -> None:
        ok, msg = seal_milestone(self.ws, "../evil")
        self.assertFalse(ok)
        self.assertIn("Invalid milestone id", msg)
        ok, msg, tasks = run_milestone_alignment(self.ws, "foo/bar")
        self.assertFalse(ok)
        self.assertEqual(tasks, [])
        self.assertIn("Invalid milestone id", msg)

    def test_align_rejects_unknown_status(self) -> None:
        import json

        (self.ws / ".agent").mkdir(exist_ok=True)
        (self.ws / ".agent" / "manifest.json").write_text(
            json.dumps({"package_root": "src", "domains": {}}), encoding="utf-8"
        )
        _write_task(self.ws / "docs/tasks/x.md", "shipped", "M20")
        ok, msg, _ = run_milestone_alignment(self.ws, "M20")
        self.assertFalse(ok)
        self.assertIn("Invalid Status", msg)

    def test_align_stub_blocks_seal(self) -> None:
        import json

        (self.ws / ".agent").mkdir(exist_ok=True)
        (self.ws / ".agent" / "manifest.json").write_text(
            json.dumps({"package_root": "src", "domains": {}}), encoding="utf-8"
        )
        _write_task(self.ws / "docs/tasks/x.md", "done", "M21")
        ok, msg, _ = run_milestone_alignment(self.ws, "M21")
        self.assertTrue(ok, msg)
        reviews = list((self.ws / "docs/reviews").glob("*M21*"))
        self.assertTrue(reviews)
        self.assertIn(_ALIGN_STUB_MARKER, reviews[0].read_text(encoding="utf-8"))
        (self.ws / "docs/reviews/SUMMARY.md").write_text("M21 audit\n", encoding="utf-8")
        ok, msg = seal_milestone(self.ws, "M21")
        self.assertFalse(ok)
        self.assertIn("align stub", msg)
        self.assertTrue((self.ws / "docs/tasks/x.md").exists())

    def test_seal_rollback_reports_incomplete(self) -> None:
        import json
        from unittest import mock

        (self.ws / ".agent").mkdir(exist_ok=True)
        (self.ws / ".agent" / "manifest.json").write_text(
            json.dumps({"package_root": "src", "domains": {}}), encoding="utf-8"
        )
        _write_task(self.ws / "docs/tasks/a.md", "done", "M22")
        _write_task(self.ws / "docs/tasks/b.md", "done", "M22")
        (self.ws / "docs/reviews").mkdir(parents=True)
        (self.ws / "docs/reviews/2026-08-24-M22-align.md").write_text(
            f"# Review M22\n{_align_pass_marker('M22')}\nfilled\n", encoding="utf-8"
        )
        (self.ws / "docs/reviews/SUMMARY.md").write_text("M22 audit\n", encoding="utf-8")

        real_move = __import__("shutil").move
        calls = {"n": 0}

        def flaky_move(src, dst):
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("disk full")
            if calls["n"] >= 3:
                raise OSError("rollback blocked")
            return real_move(src, dst)

        with mock.patch("k3dge.engine.milestone.shutil.move", side_effect=flaky_move):
            ok, msg = seal_milestone(self.ws, "M22")
        self.assertFalse(ok)
        self.assertIn("rollback incomplete", msg)

    def test_seal_rejects_review_without_align_pass(self) -> None:
        _write_task(self.ws / "docs/tasks/x.md", "done", "M13")
        (self.ws / "docs/reviews").mkdir(parents=True)
        (self.ws / "docs/reviews/2026-08-24-M13-align.md").write_text(
            "# Handmade M13\nfilled but not from align\n", encoding="utf-8"
        )
        (self.ws / "docs/reviews/SUMMARY.md").write_text("M13 audit\n", encoding="utf-8")
        ok, msg = seal_milestone(self.ws, "M13")
        self.assertFalse(ok)
        self.assertIn("align-pass", msg)

    def test_seal_rejects_unfilled_guides(self) -> None:
        _write_task(self.ws / "docs/tasks/x.md", "done", "M12")
        (self.ws / "docs/reviews").mkdir(parents=True)
        (self.ws / "docs/reviews/2026-08-23-M12-align.md").write_text(
            f"# Review M12\n{_align_pass_marker('M12')}\n", encoding="utf-8"
        )
        (self.ws / "docs/reviews/SUMMARY.md").write_text("M12 audit\n", encoding="utf-8")
        (self.ws / "docs/guides").mkdir(parents=True)
        (self.ws / "docs/guides/user_guide.md").write_text(
            "# User Guide\n<!-- k3dge:guide-stub -->\n", encoding="utf-8"
        )
        ok, msg = seal_milestone(self.ws, "M12")
        self.assertFalse(ok)
        self.assertIn("docs/guides/", msg)
        self.assertIn("user_guide.md", msg)


if __name__ == "__main__":
    unittest.main()
