import pathlib
import tempfile
import unittest

from k3dge.engine.align import (
    _ALIGN_STUB_MARKER,
    _align_pass_marker,
    run_milestone_alignment,
)
from k3dge.engine.seal import seal_milestone, seal_preconditions_error
from k3dge.engine.task_index import MilestoneTask, list_tasks, scan_milestone_tasks
from k3dge.engine.task_write import create_task, mark_task_done


def _write_task(path: pathlib.Path, status: str, milestone: str) -> None:
    path.write_text(
        f"# Task\n- **Status**: {status}\n- **Milestone**: {milestone}\n",
        encoding="utf-8",
    )


def _set_seal_gates(ws: pathlib.Path, *gate_ids: str) -> None:
    """测试用：把契约 `[checks.seal].preconditions` 收窄到指定闸，隔离被测闸。"""
    (ws / ".agent").mkdir(parents=True, exist_ok=True)
    body = ", ".join(f'"{g}"' for g in gate_ids)
    (ws / ".agent" / "pipeline.toml").write_text(
        f"[checks.seal]\npreconditions = [{body}]\n", encoding="utf-8"
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

    def test_list_tasks_skips_doc_aux_structural_files(self) -> None:
        """docs/tasks/{README,AUTHORING,_template}.md are authoring rules, never tasks.

        Regression: `list_tasks` and `cli.status` each kept their own exclusion tuple
        and `AUTHORING.md` leaked into `k3dge task list` / `status` as a ghost task.
        """
        _write_task(self.ws / "docs/tasks/open.md", "idea", "M2")
        for name in ("README.md", "AUTHORING.md", "_template.md", ".hidden.md"):
            (self.ws / "docs" / "tasks" / name).write_text("# aux\n", encoding="utf-8")
        self.assertEqual(sorted(p.name for p in (self.ws / "docs/tasks").glob("*.md")), 
                         [".hidden.md", "AUTHORING.md", "README.md", "_template.md", "open.md"])
        rows = list_tasks(self.ws)
        self.assertEqual([r.path.name for r in rows], ["open.md"])
        # `task done` must refuse to archive an authoring file too
        ok, msg, done_path = mark_task_done(self.ws, "docs/tasks/AUTHORING.md")
        self.assertFalse(ok)
        self.assertIsNone(done_path)
        ok2, _, _ = mark_task_done(self.ws, "AUTHORING")
        self.assertFalse(ok2)

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
        _set_seal_gates(self.ws, "align_pass")
        err = seal_preconditions_error(self.ws, "M10")
        self.assertIsNotNone(err)
        self.assertIn("SEAL REJECTED", err)
        self.assertIn("audit review", err)
        # nothing archived
        self.assertTrue((self.ws / "docs/tasks/x.md").exists())

    def test_seal_rejects_substring_milestone_id(self) -> None:
        _write_task(self.ws / "docs/tasks/x.md", "done", "M1")
        (self.ws / "docs/reviews").mkdir(parents=True)
        (self.ws / "docs/reviews/2026-08-23-M10-align.md").write_text("# Review M10\n", encoding="utf-8")
        _set_seal_gates(self.ws, "align_pass")
        err = seal_preconditions_error(self.ws, "M1")
        self.assertIsNotNone(err)
        self.assertIn("SEAL REJECTED", err)
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
        _set_seal_gates(self.ws, "align_pass")
        err = seal_preconditions_error(self.ws, "M21")
        self.assertIsNotNone(err)
        self.assertIn("align stub", err)
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

        with mock.patch("k3dge.engine.seal.shutil.move", side_effect=flaky_move):
            ok, msg = seal_milestone(self.ws, "M22")
        self.assertFalse(ok)
        self.assertIn("rollback incomplete", msg)

    def test_seal_rejects_review_without_align_pass(self) -> None:
        _write_task(self.ws / "docs/tasks/x.md", "done", "M13")
        (self.ws / "docs/reviews").mkdir(parents=True)
        (self.ws / "docs/reviews/2026-08-24-M13-align.md").write_text(
            "# Handmade M13\nfilled but not from align\n", encoding="utf-8"
        )
        _set_seal_gates(self.ws, "align_pass")
        err = seal_preconditions_error(self.ws, "M13")
        self.assertIsNotNone(err)
        self.assertIn("align-pass", err)

    def test_report_presence_is_never_a_seal_precondition(self) -> None:
        """ADR-0004 §2.1.3/§2.1.10：报告＝**可选产物** ⇒ 报告存在性/新鲜度（`audit_closed` /
        `evidence_chain` / `audit_fresh`）不得出现在任何 `[checks.*]` 的 preconditions 里
        （缺省面与仓内声明面都验）——否则又会退回"有旧报告就能封"的旧模型。"""
        from k3dge.engine import gates

        banned = {"audit_closed", "evidence_chain", "audit_fresh"}
        repo = pathlib.Path(__file__).resolve().parents[3]
        for ws in (pathlib.Path(tempfile.mkdtemp()), repo):
            declared = gates.DEFAULTS if ws != repo else gates.load(ws)
            for kind, unit in (declared.get("checks") or {}).items():
                hit = banned & set(unit.get("preconditions") or [])
                self.assertEqual(hit, set(), f"{ws} [checks.{kind}] preconditions 含 {hit}")

    def test_seal_gate_audit_closed_is_retired(self) -> None:
        """`audit_closed` 已退休（ADR-0004 §2.1.3/§2.1.9）：报告降为可选产物、审计由 seal
        相位 2 自己跑 ⇒ 声明里再写它就是**配置错**（闸不静默空转）。"""
        _write_task(self.ws / "docs/tasks/x.md", "done", "M17")
        _set_seal_gates(self.ws, "audit_closed")
        err = seal_preconditions_error(self.ws, "M17")
        self.assertIsNotNone(err)
        self.assertEqual(getattr(err, "gate_id", None), "unknown_gate_id")

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
        _set_seal_gates(self.ws, "guides_filled")
        err = seal_preconditions_error(self.ws, "M12")
        self.assertIsNotNone(err)
        self.assertIn("docs/guides/", err)
        self.assertIn("user_guide.md", err)

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

        with mock.patch("k3dge.engine.seal.shutil.move", side_effect=flaky_move):
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




def test_backfill_into_third_level_stub_creates_section() -> None:
    """报告只写了 `### 回填`：子串判据以为"已有回填段"，插入函数找不到锚行 ⇒ 静默漏回填（332）。"""
    import contextlib
    import io

    from k3dge.engine.task_write import _ensure_backfill_section

    lines: list = []
    text = "# 报告\n\n### 回填（上一轮的）\n\n> | 旧票 | 已修 | x |\n"
    _ensure_backfill_section(lines, text, "2026-09-01-M9-feat-a.md", "A-1")
    assert any("2026-09-01-M9-feat-a.md" in ln for ln in lines), lines


def test_report_pointer_outside_workspace_is_ignored() -> None:
    """`report:` 是票里可控文本：绝对路径/`..` 不得让引擎去读仓外文件（333）。"""
    import contextlib
    import io
    import tempfile as _tf
    from pathlib import Path as _P

    from k3dge.engine.task_write import _report_open_findings

    ws = _P(_tf.mkdtemp())
    outside = ws.parent / "leak.md"
    outside.write_text("# x\n\n| ID | 状态 |\n| A-1 | 待修 |\n", encoding="utf-8")
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        got = _report_open_findings(ws, str(outside))
    assert got is None
    assert "越出本仓" in buf.getvalue()


def test_closure_has_tsv_trail(tmp_path):
    """show-me-your-work 吸收回归：封板清单带 TSV 决策轨迹（证据=指针）。"""
    from k3dge.engine.seal_flow import _write_closure_note

    (tmp_path / "docs" / "reviews").mkdir(parents=True)
    (tmp_path / "docs" / "reviews" / "2026-09-04-M9-audit.md").write_text("x", encoding="utf-8")
    p = _write_closure_note(tmp_path, "M9")
    txt = p.read_text(encoding="utf-8")
    assert "ts\tphase\tdecision\twhy\tevidence\tresult" in txt
    assert "2026-09-04-M9-audit.md" in txt


class TestDocsNormalizedGate(unittest.TestCase):
    """`docs_normalized` 前置闸（ADR-0022 §2.2 🅰1.4：耐久＝闸）。

    为何是前置闸而不是 seal 的动作：规约化若在审计闭环**之后**改文档，刚闭环的审计证据
    （审的是旧文档）就失效了 ⇒ 必须在封板前做完，由 `k3dge doc fix` 完成，seal 只验"做没做"。
    """

    def setUp(self) -> None:
        self.ws = pathlib.Path(tempfile.mkdtemp())
        (self.ws / ".agent").mkdir(parents=True, exist_ok=True)
        (self.ws / "docs" / "tasks").mkdir(parents=True, exist_ok=True)
        (self.ws / "docs" / "reviews").mkdir(parents=True, exist_ok=True)

    def test_blocks_when_fixable_deviation_exists(self) -> None:
        from k3dge.engine import doc_fix

        ws = self.ws
        _write_task(ws / "docs/tasks/x.md", "done", "M10")
        (ws / "docs" / "memo").mkdir(parents=True, exist_ok=True)
        (ws / "docs" / "memo" / "a.md").write_text("# t\n\n正文   \n", encoding="utf-8")
        _set_seal_gates(ws, "docs_normalized")
        err = seal_preconditions_error(ws, "M10")
        self.assertIsNotNone(err)
        self.assertEqual(getattr(err, "gate_id", None), "docs_normalized")
        self.assertIn("k3dge doc fix", str(err))
        # 修完 ⇒ 过闸
        doc_fix.apply(ws)
        self.assertIsNone(seal_preconditions_error(ws, "M10"))

    def test_passes_when_clean(self) -> None:
        ws = self.ws
        _write_task(ws / "docs/tasks/x.md", "done", "M10")
        _set_seal_gates(ws, "docs_normalized")
        self.assertIsNone(seal_preconditions_error(ws, "M10"))


def _no_prompt():
    """非交互 prompter（回答 y）：seal 流程里"要不要封"的提示不该挡测试。"""
    from k3dge.engine.prompt import Prompt

    return Prompt(answers=["y"])


class TestSealChecklist(unittest.TestCase):
    """封板前置清单：全量投影（#3）。

    为何：`seal_preconditions_error` 只报**首个**失败（闸的语义是"停"），操作者实际是
    "跑 seal → 修一个 → 再跑 → 又发现一个"的试错。清单让"封板前必须做的事"一次看清，
    且 `[NEXT]` blockers / seal 拒绝信息 / `seal-check` 三处同源。
    """

    def setUp(self) -> None:
        self.ws = pathlib.Path(tempfile.mkdtemp())
        (self.ws / ".agent").mkdir(parents=True, exist_ok=True)
        (self.ws / "docs" / "tasks").mkdir(parents=True, exist_ok=True)
        (self.ws / "docs" / "reviews").mkdir(parents=True, exist_ok=True)

    def test_lists_every_declared_gate_in_order(self) -> None:
        from k3dge.engine import gates
        from k3dge.engine.seal import seal_checklist

        rows = seal_checklist(self.ws, "M10")
        self.assertEqual([r[0] for r in rows], gates.preconditions(self.ws, "seal"))
        self.assertTrue(all(isinstance(r[1], bool) and isinstance(r[3], bool) for r in rows))

    def test_unmet_is_derived_from_checklist(self) -> None:
        from k3dge.engine.seal import seal_checklist, unmet_seal_preconditions

        rows = seal_checklist(self.ws, "M10")
        unmet = unmet_seal_preconditions(self.ws, "M10")
        # unmet ＝ 未过 **且不是 seal 自己会跑** 的（`align_pass` 属后者 ⇒ 不进 unmet）
        self.assertEqual(unmet, [(r[0], r[2]) for r in rows if not r[1] and not r[3]])

    def test_render_marks_pass_and_fail(self) -> None:
        from k3dge.engine.seal import render_checklist

        _write_task(self.ws / "docs/tasks/x.md", "done", "M10")
        (self.ws / "docs" / "guides").mkdir(parents=True, exist_ok=True)
        (self.ws / "docs" / "guides" / "g.md").write_text(
            "# G\n<!-- k3dge:guide-stub -->\n", encoding="utf-8")
        _set_seal_gates(self.ws, "tasks_all_done", "guides_filled")
        text = render_checklist(self.ws, "M10")
        self.assertIn("✅ tasks_all_done", text)
        self.assertIn("❌ guides_filled", text)
        self.assertIn("1/2 通过", text)
        self.assertIn("需你先办 1 项", text)

    def test_missing_provenance_baseline_blocks_evidence_chain(self) -> None:
        """#1：`基线` 进必填署名/来源项 ⇒ 缺它时 evidence_chain 不过（清单里可见 ❌）。"""
        from k3dge.engine.seal import render_checklist

        _write_task(self.ws / "docs/tasks/x.md", "done", "M10")
        (self.ws / "docs" / "reviews" / "2026-09-13-M10-audit.md").write_text(
            "| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
            "- **审计人**: k3dit\n- **透镜来源**: k3dit\n", encoding="utf-8")
        _set_seal_gates(self.ws, "evidence_chain")
        self.assertIn("❌ evidence_chain", render_checklist(self.ws, "M10"))

    def test_seal_rejection_carries_the_whole_checklist(self) -> None:
        """seal 拒绝时给全量清单，而不是只给首个失败。"""
        from k3dge.engine.seal_flow import run_seal_flow

        _write_task(self.ws / "docs/tasks/x.md", "done", "M10")
        # 非审计类的失败（走 _archive 的拒绝路径）：guides 有 stub（❌ 需人办，非 ⚙️）
        _write_task(self.ws / "docs/tasks/x.md", "done", "M10")
        (self.ws / "docs" / "guides").mkdir(parents=True, exist_ok=True)
        (self.ws / "docs" / "guides" / "g.md").write_text(
            "# G\n<!-- k3dge:guide-stub -->\n", encoding="utf-8")
        _set_seal_gates(self.ws, "tasks_all_done", "guides_filled")
        status, msg = run_seal_flow(self.ws, "M10", prompter=_no_prompt())
        self.assertEqual(status, "rejected")
        self.assertIn("封板前置清单（M10）", msg)
        self.assertIn("❌ guides_filled", msg)
        self.assertIn("✅ tasks_all_done", msg)

    def test_align_pass_is_marked_auto_not_todo(self) -> None:
        """`align_pass` 由 seal 自己的第一个动作（`full_matrix`→跑 align+写 marker）满足
        ⇒ 清单里是 ⚙️（auto），**不算"需你先办"**（否则误导操作者去手跑 align）。"""
        from k3dge.engine import nodes
        from k3dge.engine.seal import render_checklist, unmet_seal_preconditions

        _write_task(self.ws / "docs/tasks/x.md", "done", "M10")
        _set_seal_gates(self.ws, "align_pass")
        text = render_checklist(self.ws, "M10")
        self.assertIn("⚙️ align_pass", text)
        self.assertNotIn("❌ align_pass", text)
        self.assertIn("align_pass", nodes.satisfied_ids(self.ws, "seal"))
        self.assertEqual(unmet_seal_preconditions(self.ws, "M10"), [])   # 无需人先办

    def test_audit_refusal_also_carries_the_checklist(self) -> None:
        """相位 2 审计被拒（refused）的路径同样给全量清单——否则操作者修完审计才发现
        预审那边还有别的未过闸（本会话的真实体验：一次看清 > 试错）。"""
        from unittest import mock

        from k3dge.engine.seal_flow import run_seal_flow

        _write_task(self.ws / "docs/tasks/x.md", "done", "M10")
        _set_seal_gates(self.ws, "tasks_all_done", "align_pass")
        with mock.patch("k3dge.engine.milestone_audit.run_audit_flow",
                        return_value=("refused", "跳被跳过")):
            status, msg = run_seal_flow(self.ws, "M10", prompter=_no_prompt())
        self.assertEqual(status, "rejected")
        self.assertIn("封板前置清单（M10）", msg)
        self.assertIn("✅ tasks_all_done", msg)


if __name__ == "__main__":
    unittest.main()
