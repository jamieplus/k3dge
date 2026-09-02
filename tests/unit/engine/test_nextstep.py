"""Tests for the single-source [NEXT] hints and the audit-first lifecycle wiring."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import TestCase, mock

from k3dge.engine import audit_trigger, milestone as ms, nextstep


class TestNextStepRender(TestCase):
    def test_seal_ready_shape(self) -> None:
        cli = nextstep.NextStep.from_state("seal_ready", "M7").render_cli()
        self.assertTrue(cli.startswith("[NEXT] state=seal_ready milestone=M7"))
        self.assertIn("封板？(y/N，无倒计时)", cli)
        self.assertIn("if y: k3dge milestone seal M7", cli)
        self.assertNotIn("<id>", cli)

    def test_audit_suggested_shape_with_reasons(self) -> None:
        cli = nextstep.NextStep.from_state(
            "audit_suggested", "M7", reasons=["账齐：本里程碑 3 个任务全 done，建议过一遍透镜"]
        ).render_cli()
        self.assertIn("[NEXT] state=audit_suggested milestone=M7", cli)
        self.assertIn("reason: 账齐", cli)
        self.assertIn("ask: 要审吗？(y/N，无倒计时)", cli)
        self.assertIn("if y: k3dge milestone audit M7", cli)

    def test_audit_open_includes_pending(self) -> None:
        cli = nextstep.NextStep.from_state("audit_open", "M7", pending=3).render_cli()
        self.assertIn("pending=3", cli)
        self.assertIn("ask: agent 修？(倒计时默认修)", cli)

    def test_deferred_is_note_only(self) -> None:
        cli = nextstep.NextStep.from_state("deferred", "M7").render_cli()
        self.assertIn("note: 已放弃封板", cli)
        self.assertNotIn("if y:", cli)

    def test_mcp_isomorphic(self) -> None:
        d = nextstep.NextStep.from_state("seal_ready", "M7").render_mcp()
        self.assertEqual(d["state"], "seal_ready")
        self.assertIn("封板？", d["ask"])
        self.assertIn("k3dge milestone seal M7", d["if_y"])

    def test_rejection_maps_to_action(self) -> None:
        n = nextstep.next_for_rejection("M7", "no 12-col audit report found")
        self.assertIn("k3dge milestone audit-submit M7", n.note)
        n2 = nextstep.next_for_rejection("M7", "未审计不可封板")
        self.assertEqual(n2.state, "audit_needed")

    def test_overview_stale_removed_as_hook(self) -> None:
        # Architecture-update hook was removed (handled inside milestone closure).
        self.assertNotIn("overview_stale", nextstep.STATE_OPTIONS)

    def test_new_domain_shape(self) -> None:
        cli = nextstep.NextStep.from_state("new_domain", "M7").render_cli()
        self.assertIn("[NEXT] state=new_domain milestone=M7", cli)
        self.assertIn("manifest + spec + tests", cli)


def _base_ws(mid="M7"):
    ws = Path(tempfile.mkdtemp())
    (ws / ".agent").mkdir()
    (ws / ".agent" / "manifest.json").write_text(
        '{"package_root":"src","domains":{"engine":{"src":"src/k3dge/engine"}}}', encoding="utf-8"
    )
    (ws / ".agent" / "milestone").write_text(mid + "\n", encoding="utf-8")
    (ws / "docs" / "tasks").mkdir(parents=True)
    (ws / "docs" / "tasks" / f"2026-09-01-{mid}-feat-x.md").write_text(
        f"# X\n- **Status**: done\n- **Milestone**: {mid}\n", encoding="utf-8"
    )
    (ws / "docs" / "reviews").mkdir(parents=True)
    return ws


class TestAuditTrigger(TestCase):
    def test_all_tasks_done_suggests_audit(self) -> None:
        ws = _base_ws()
        with mock.patch.object(audit_trigger, "_git_changed_files", return_value=[]):
            suggested, reasons = audit_trigger.compute_audit_suggestion(ws)
        self.assertTrue(suggested)
        self.assertTrue(any("账齐" in r for r in reasons))

    def test_pending_task_no_suggestion(self) -> None:
        ws = _base_ws()
        (ws / "docs" / "tasks" / "2026-09-01-M7-fix-y.md").write_text(
            "# Y\n- **Status**: in-progress\n- **Milestone**: M7\n", encoding="utf-8"
        )
        with mock.patch.object(audit_trigger, "_git_changed_files", return_value=[]):
            suggested, _ = audit_trigger.compute_audit_suggestion(ws)
        self.assertFalse(suggested)

    def test_volume_signal(self) -> None:
        ws = _base_ws()
        files = [f"src/k3dge/engine/f{i}.py" for i in range(8)]
        with mock.patch.object(audit_trigger, "_git_changed_files", return_value=files):
            suggested, reasons = audit_trigger.compute_audit_suggestion(ws)
        self.assertTrue(suggested)
        self.assertTrue(any("体积" in r for r in reasons))

    def test_doc_desync_is_not_a_trigger(self) -> None:
        # overview.md staleness was removed as an audit trigger (moved to milestone closure).
        ws = _base_ws()
        with mock.patch.object(audit_trigger, "_git_changed_files", return_value=["src/k3dge/engine/f.py"]):
            _, reasons = audit_trigger.compute_audit_suggestion(ws)
        self.assertFalse(any("文档不同步" in r or "overview" in r for r in reasons))

    def test_existing_report_suppresses(self) -> None:
        ws = _base_ws()
        (ws / "docs" / "reviews" / "2026-09-01-M7-audit.md").write_text(
            "| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
            "| A1 | x | s | p | t | d | l | 待修 | - | - | - | - |\n",
            encoding="utf-8",
        )
        with mock.patch.object(audit_trigger, "_git_changed_files", return_value=[]):
            suggested, _ = audit_trigger.compute_audit_suggestion(ws)
        self.assertFalse(suggested)

    def test_audit_closed(self) -> None:
        ws = _base_ws()
        self.assertFalse(audit_trigger.audit_closed(ws, "M7"))
        _clean = (
            "| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
            "| A1 | x | s | p | t | d | l | 已修 | - | - | - | - |\n"
        )
        (ws / "docs" / "reviews" / "2026-09-01-M7-audit.md").write_text(_clean, encoding="utf-8")
        # quality report still missing -> not closed
        self.assertFalse(audit_trigger.audit_closed(ws, "M7"))
        (ws / "docs" / "reviews" / "2026-09-01-M7-quality.md").write_text(
            "<!-- k3dge:kind: quality -->\n" + _clean, encoding="utf-8"
        )
        self.assertTrue(audit_trigger.audit_closed(ws, "M7"))


class TestWorkspaceHints(TestCase):
    def test_new_domain_detected(self) -> None:
        from k3dge.cli import main as cli_main

        ws = _base_ws()
        with mock.patch("subprocess.run") as run:
            run.return_value = mock.MagicMock(stdout="?? src/newdom/bar.py\n", returncode=0)
            hints = cli_main._workspace_hints(ws)
        self.assertIn("new_domain", [h.state for h in hints])

    def test_known_domain_not_new(self) -> None:
        from k3dge.cli import main as cli_main

        ws = _base_ws()
        with mock.patch("subprocess.run") as run:
            run.return_value = mock.MagicMock(stdout=" M src/k3dge/engine/foo.py\n", returncode=0)
            hints = cli_main._workspace_hints(ws)
        # overview staleness is no longer a standalone hint (folded into audit_suggested)
        self.assertEqual(hints, [])

    def test_bare_untracked_tree_not_new_domain(self) -> None:
        # whole tree untracked -> git collapses to "?? src/"; that is NOT a new domain
        from k3dge.cli import main as cli_main

        ws = _base_ws()
        with mock.patch("subprocess.run") as run:
            run.return_value = mock.MagicMock(stdout="?? src/\n", returncode=0)
            hints = cli_main._workspace_hints(ws)
        self.assertEqual([h.state for h in hints], [])


class TestLifecycleNext(TestCase):
    def test_audit_first_then_seal(self) -> None:
        from k3dge.cli import main as cli_main

        ws = _base_ws()
        with mock.patch.object(audit_trigger, "_git_changed_files", return_value=[]):
            ns = cli_main._lifecycle_next(ws)
        self.assertEqual(ns.state, "audit_suggested")

    def test_seal_ready_when_audit_closed(self) -> None:
        from k3dge.cli import main as cli_main

        ws = _base_ws()
        _clean = (
            "| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
            "| A1 | x | s | p | t | d | l | 已修 | - | - | - | - |\n"
        )
        (ws / "docs" / "reviews" / "2026-09-01-M7-audit.md").write_text(_clean, encoding="utf-8")
        (ws / "docs" / "reviews" / "2026-09-01-M7-quality.md").write_text(
            "<!-- k3dge:kind: quality -->\n" + _clean, encoding="utf-8"
        )
        ns = cli_main._lifecycle_next(ws)
        self.assertEqual(ns.state, "seal_ready")

    def test_pending_markers_take_precedence(self) -> None:
        from k3dge.cli import main as cli_main

        ws = _base_ws()
        src = ws / "src" / "k3dge" / "engine"
        src.mkdir(parents=True)
        (src / "mod.py").write_text("def f():\n    return 1  # k3dit:pending A-11\n", encoding="utf-8")
        ns = cli_main._lifecycle_next(ws)
        self.assertEqual(ns.state, "pending_findings")
        self.assertEqual(ns.pending, 1)
        self.assertTrue(any("A-11" in r for r in ns.reasons))
