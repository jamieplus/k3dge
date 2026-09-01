import pathlib
import tempfile
import unittest

from k3dge.engine.milestone import (
    MilestoneTask,
    create_task,
    list_tasks,
    mark_task_done,
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


def _write_one_domain(ws: pathlib.Path) -> None:
    """Minimal domain so align's Full Matrix is not NO_DOMAINS."""
    import json

    from k3dge.engine.contract import collect_domain_interface, compute_hash

    src = ws / "src" / "core"
    src.mkdir(parents=True, exist_ok=True)
    h = compute_hash(collect_domain_interface(src))
    spec = ws / "docs" / "specs" / "core" / "spec.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text(
        "# Domain Specification: core\n"
        "- **Status**: Active\n"
        "- **Module Path**: `src/core`\n"
        f"- **Contract Hash**: `sha256:{h}`\n"
        "- **Last Updated**: 2026-08-25\n"
        "## 1. Domain Boundary & Responsibilities\n"
        "## 2. Public Interfaces & Type Contracts\n"
        "<!-- k3dge:interfaces-start -->\n```python\n```\n<!-- k3dge:interfaces-end -->\n"
        "## 3. State Machine & Invariants\n"
        "## 4. Verification Matrix\n",
        encoding="utf-8",
    )
    (ws / ".agent").mkdir(exist_ok=True)
    (ws / ".agent" / "manifest.json").write_text(
        json.dumps(
            {
                "package_root": "src",
                "domains": {
                    "core": {
                        "src": "src/core",
                        "spec": "docs/specs/core/spec.md",
                        "tests": "tests/unit/core",
                    }
                },
            }
        ),
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

    def test_list_tasks_index_skips_archive_and_readme(self) -> None:
        _write_task(self.ws / "docs/tasks/open.md", "idea", "M2")
        (self.ws / "docs/tasks/README.md").write_text("# Tasks\n", encoding="utf-8")
        archived = self.ws / "docs/tasks/archive/M0"
        archived.mkdir(parents=True)
        _write_task(archived / "old.done.md", "done", "M0")
        rows = list_tasks(self.ws)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].title, "Task")
        self.assertEqual(rows[0].status, "idea")
        self.assertEqual(rows[0].milestone, "M2")
        idea_only = list_tasks(self.ws, status="idea")
        self.assertEqual(len(idea_only), 1)
        self.assertEqual(len(list_tasks(self.ws, status="done")), 0)
        self.assertEqual(len(list_tasks(self.ws, milestone_id="M0")), 0)

    def test_mark_task_done_prefers_exact_path(self) -> None:
        _write_task(self.ws / "docs/tasks/alpha.md", "idea", "M2")
        _write_task(self.ws / "docs/tasks/alphabet.md", "idea", "M2")
        rel = "docs/tasks/alpha.md"
        ok, msg, path = mark_task_done(self.ws, rel)
        self.assertTrue(ok, msg)
        self.assertIsNotNone(path)
        self.assertTrue(path.name.endswith(".done.md"))
        self.assertTrue((self.ws / "docs/tasks/alphabet.md").exists())
        ok2, msg2, _ = create_task(self.ws, "New item", typ="fix", milestone="M2")
        self.assertTrue(ok2, msg2)

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
        (self.ws / "docs/reviews").mkdir(parents=True)
        (self.ws / "docs/reviews/2026-08-23-M9-align.md").write_text(
            f"# Review M9\n{_align_pass_marker('M9')}\n- Regression: PASS\n- [x] `2026-08-22-a.md`\n- [x] `2026-08-22-b.md`\n",
            encoding="utf-8",
        )
        (self.ws / "docs/reviews/2026-08-23-M8-align.md").write_text(
            "# Review M8 stays living\n", encoding="utf-8"
        )
        (self.ws / "docs/reviews/2026-08-23-untagged.md").write_text(
            "# untagged no pass mark\n", encoding="utf-8"
        )
        (self.ws / "docs/reviews/LEFTOVERS.md").write_text(
            "| ID | 报告 |\n| --- | --- |\n"
            "| X | [2026-08-23-M9-align.md](2026-08-23-M9-align.md) |\n"
            "| Y | [rel](./2026-08-23-M9-align.md) |\n",
            encoding="utf-8",
        )
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
        self.assertTrue((self.ws / "docs/reviews/archive/M9/2026-08-23-M9-align.md").exists())
        self.assertFalse((self.ws / "docs/reviews/2026-08-23-M9-align.md").exists())
        self.assertTrue((self.ws / "docs/reviews/2026-08-23-M8-align.md").exists())
        self.assertTrue((self.ws / "docs/reviews/2026-08-23-untagged.md").exists())
        leftovers = (self.ws / "docs/reviews/LEFTOVERS.md").read_text(encoding="utf-8")
        self.assertIn("](archive/M9/2026-08-23-M9-align.md)", leftovers)
        self.assertNotIn("](2026-08-23-M9-align.md)", leftovers)
        self.assertNotIn("](./2026-08-23-M9-align.md)", leftovers)
        self.assertIn("reviews to docs/reviews/archive/M9/", msg)

    def test_seal_rejects_missing_review(self) -> None:
        _write_task(self.ws / "docs/tasks/x.md", "done", "M10")
        ok, msg = seal_milestone(self.ws, "M10")
        self.assertFalse(ok)
        self.assertIn("SEAL REJECTED", msg)
        self.assertIn("audit review", msg)
        # nothing archived
        self.assertTrue((self.ws / "docs/tasks/x.md").exists())

    def test_seal_rejects_substring_milestone_id(self) -> None:
        _write_task(self.ws / "docs/tasks/x.md", "done", "M1")
        (self.ws / "docs/reviews").mkdir(parents=True)
        (self.ws / "docs/reviews/2026-08-23-M10-align.md").write_text("# Review M10\n", encoding="utf-8")
        ok, msg = seal_milestone(self.ws, "M1")
        self.assertFalse(ok)
        self.assertIn("SEAL REJECTED", msg)
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

        _write_one_domain(self.ws)
        _write_task(self.ws / "docs/tasks/x.md", "done", "M21")
        ok, msg, _ = run_milestone_alignment(self.ws, "M21")
        self.assertTrue(ok, msg)
        reviews = list((self.ws / "docs/reviews").glob("*M21*"))
        self.assertTrue(reviews)
        self.assertIn(_ALIGN_STUB_MARKER, reviews[0].read_text(encoding="utf-8"))
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
            f"# Review M22\n{_align_pass_marker('M22')}\n- [x] `a.md`\n- [x] `b.md`\n", encoding="utf-8"
        )

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
        ok, msg = seal_milestone(self.ws, "M13")
        self.assertFalse(ok)
        self.assertIn("align-pass", msg)

    def test_seal_rejects_unfilled_guides(self) -> None:
        _write_task(self.ws / "docs/tasks/x.md", "done", "M12")
        (self.ws / "docs/reviews").mkdir(parents=True)
        (self.ws / "docs/reviews/2026-08-23-M12-align.md").write_text(
            f"# Review M12\n{_align_pass_marker('M12')}\n- [x] `x.md`\n", encoding="utf-8"
        )
        (self.ws / "docs/guides").mkdir(parents=True)
        (self.ws / "docs/guides/user_guide.md").write_text(
            "# User Guide\n<!-- k3dge:guide-stub -->\n", encoding="utf-8"
        )
        ok, msg = seal_milestone(self.ws, "M12")
        self.assertFalse(ok)
        self.assertIn("docs/guides/", msg)
        self.assertIn("user_guide.md", msg)

    def test_seal_archives_untagged_review_with_pass_mark(self) -> None:
        _write_task(self.ws / "docs/tasks/x.md", "done", "M14")
        reviews = self.ws / "docs/reviews"
        reviews.mkdir(parents=True)
        (reviews / "2026-08-24-M14-align.md").write_text(
            f"# Review M14\n{_align_pass_marker('M14')}\n- [x] `x.md`\n", encoding="utf-8"
        )
        (reviews / "extra-5pass.md").write_text(
            f"# Extra\n{_align_pass_marker('M14')}\n", encoding="utf-8"
        )
        (reviews / "AUTHORING.md").write_text("# Authoring\n", encoding="utf-8")
        (reviews / "LEFTOVERS.md").write_text("# Intentional leftovers\n", encoding="utf-8")
        ok, msg = seal_milestone(self.ws, "M14")
        self.assertTrue(ok, msg)
        self.assertTrue((self.ws / "docs/reviews/archive/M14/extra-5pass.md").exists())
        self.assertTrue((self.ws / "docs/reviews/archive/M14/2026-08-24-M14-align.md").exists())
        self.assertTrue((reviews / "AUTHORING.md").exists())
        self.assertTrue((reviews / "LEFTOVERS.md").exists())
        self.assertFalse((reviews / "extra-5pass.md").exists())

    def test_seal_rollback_restores_leftovers(self) -> None:
        from unittest import mock

        _write_task(self.ws / "docs/tasks/a.md", "done", "M15")
        reviews = self.ws / "docs/reviews"
        reviews.mkdir(parents=True)
        (reviews / "2026-08-24-M15-align.md").write_text(
            f"# Review M15\n{_align_pass_marker('M15')}\n- [x] `a.md`\n", encoding="utf-8"
        )
        leftover = (
            "| ID | 报告 |\n| --- | --- |\n"
            "| X | [2026-08-24-M15-align.md](2026-08-24-M15-align.md) |\n"
        )
        (reviews / "LEFTOVERS.md").write_text(leftover, encoding="utf-8")

        real_move = __import__("shutil").move
        calls = {"n": 0}

        def flaky_move(src, dst):
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("disk full")
            return real_move(src, dst)

        with mock.patch("k3dge.engine.milestone.shutil.move", side_effect=flaky_move):
            ok, msg = seal_milestone(self.ws, "M15")
        self.assertFalse(ok)
        self.assertTrue((self.ws / "docs/tasks/a.md").exists())
        self.assertTrue((reviews / "2026-08-24-M15-align.md").exists())
        self.assertEqual((reviews / "LEFTOVERS.md").read_text(encoding="utf-8"), leftover)

    def test_seal_rejects_existing_archive_target(self) -> None:
        _write_task(self.ws / "docs/tasks/a.md", "done", "M16")
        reviews = self.ws / "docs/reviews"
        reviews.mkdir(parents=True)
        (reviews / "2026-08-24-M16-align.md").write_text(
            f"# Review M16\n{_align_pass_marker('M16')}\n- [x] `a.md`\n", encoding="utf-8"
        )
        dest = self.ws / "docs/reviews/archive/M16"
        dest.mkdir(parents=True)
        (dest / "2026-08-24-M16-align.md").write_text("already archived\n", encoding="utf-8")
        ok, msg = seal_milestone(self.ws, "M16")
        self.assertFalse(ok)
        self.assertIn("already exists", msg)
        self.assertTrue((self.ws / "docs/tasks/a.md").exists())
        self.assertTrue((reviews / "2026-08-24-M16-align.md").exists())


if __name__ == "__main__":
    unittest.main()
