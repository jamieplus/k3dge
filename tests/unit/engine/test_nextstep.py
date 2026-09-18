"""Tests for the single-source [NEXT] hints and the audit-first lifecycle wiring."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import TestCase, mock

from k3dge.engine import audit_trigger, nextstep


class TestNextStepRender(TestCase):
    def test_seal_ready_shape(self) -> None:
        cli = nextstep.NextStep.from_state("seal_ready", "M7").render_cli()
        self.assertTrue(cli.startswith("[NEXT] state=seal_ready milestone=M7"))
        self.assertIn("封板？", cli)
        self.assertNotIn("y/N", cli)   # [NEXT] 无应答通道：不得写 y/N（见 memo S7）
        self.assertIn("if y: k3dge milestone seal M7", cli)
        self.assertNotIn("<id>", cli)

    def test_audit_suggested_shape_with_reasons(self) -> None:
        cli = nextstep.NextStep.from_state(
            "audit_suggested", "M7", reasons=["账齐：本里程碑 3 个任务全 done，建议过一遍透镜"]
        ).render_cli()
        self.assertIn("[NEXT] state=audit_suggested milestone=M7", cli)
        self.assertIn("reason: 账齐", cli)
        self.assertIn("ask: 要审吗？", cli)
        self.assertNotIn("y/N", cli)
        self.assertIn("if y: k3dge milestone audit M7", cli)

    def test_audit_open_includes_pending(self) -> None:
        cli = nextstep.NextStep.from_state("audit_open", "M7", pending=3).render_cli()
        self.assertIn("pending=3", cli)
        self.assertIn("ask: agent 修？", cli)
        self.assertNotIn("倒计时", cli)   # [NEXT] 无倒计时在跑

    def test_seal_declined_is_note_only(self) -> None:
        cli = nextstep.NextStep.from_state("seal_declined", "M7").render_cli()
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
        # 单报告（ADR-0025）：no quality peer -> audit clean is enough
        self.assertTrue(audit_trigger.audit_closed(ws, "M7"))

    def test_milestone_less_report_does_not_close(self) -> None:
        """C-new：无里程碑归属的 12 列报告（如 doc-audit 通稿）不得冒充某里程碑审计闭环。"""
        ws = _base_ws()
        _clean = (
            "| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
            "| A1 | x | s | p | t | d | l | 已修 | - | - | - | - |\n"
        )
        (ws / "docs" / "reviews" / "2026-09-10-doc-audit-docs.md").write_text(_clean, encoding="utf-8")
        self.assertFalse(audit_trigger.audit_closed(ws, "M7"))


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


class TestIncompleteReport(TestCase):
    def test_incomplete_report_never_closes(self) -> None:
        """未尽项报告（`<!-- k3dge:incomplete -->`）即便 待修=0 也不构成闭环。"""
        from k3dge.engine import audit_trigger

        ws = _base_ws()
        _clean = (
            "| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
            "| A1 | x | s | p | t | d | l | 已修 | - | - | - | - |\n"
        )
        p = ws / "docs" / "reviews" / "2026-09-01-M7-audit.md"
        p.write_text("<!-- k3dge:incomplete -->\n" + _clean, encoding="utf-8")
        self.assertFalse(audit_trigger.audit_closed(ws, "M7"))


class TestNextStepPointers(TestCase):
    def test_pointers_surface_depth_not_prose(self) -> None:
        ns = nextstep.NextStep.from_state("seal_ready", "M7")
        cli = ns.render_cli()
        self.assertIn("pointers:", cli)
        # 自限定：下游不自带 k3dge 的 ADR，裸引会指错靶（见 test_reference_portability）
        self.assertIn("k3dge ADR-0004 §2.1.4", cli)
        d = ns.render_mcp()
        self.assertIn("pointers", d)
        self.assertIn("k3dge ADR-0004 §2.1.4", d["pointers"])

    def test_pointers_fill_id(self) -> None:
        d = nextstep.NextStep.from_state("audit_suggested", "M7").render_mcp()
        self.assertIn("k3dge milestone audit M7", d["pointers"])
        self.assertNotIn("<id>", " ".join(d["pointers"]))

    def test_all_states_have_pointers(self) -> None:
        for state in nextstep.STATE_OPTIONS:
            ns = nextstep.NextStep.from_state(state, "M7")
            self.assertTrue(ns.pointers, f"state {state} 缺 pointers")

    def test_no_channel_vocabulary_in_next_display(self) -> None:
        """[NEXT] 无应答通道：显示串不得含 prompt 通道的词汇。

        y/N 与倒计时真实存在于 `prompt.ask`（它读 stdin）；[NEXT] 只是打印，
        写了就是虚假承诺（曾误植三处，见 memo S7）。
        """
        for state, opt in nextstep.STATE_OPTIONS.items():
            for field in ("ask", "if_y", "if_n", "note"):
                val = opt.get(field)
                items = val if isinstance(val, list) else ([val] if val else [])
                for s in items:
                    for bad in ("y/N", "倒计时"):
                        self.assertNotIn(bad, s, f"{state}.{field} 含通道词汇 {bad}：{s}")

    def test_no_state_name_collides_with_task_status(self) -> None:
        """术语守卫：next-step 态名不得与 task status 撞名。

        两者都是用户可见字符串，都在封板/任务流程里出现。曾发生过：
        里程碑域的 `deferred`（放弃封板）与任务域 `deferred`（任务推迟）同字不同义。
        改名后交集应为空。
        """
        from k3dge.engine.task_index import _ALLOWED_STATUS

        overlap = set(nextstep.STATE_OPTIONS) & set(_ALLOWED_STATUS)
        self.assertEqual(
            overlap, set(),
            f"next-step 态名与 task status 撞名：{sorted(overlap)}；"
            "请改名（参考 seal_declined 的处理）",
        )
