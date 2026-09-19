"""Tests for the single-source [NEXT] hints and the audit-first lifecycle wiring."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import TestCase, mock

from k3dge.engine import audit_trigger, gates, nextstep


class TestNextStepRender(TestCase):
    def test_seal_ready_shape(self) -> None:
        cli = nextstep.NextStep.from_state("seal_ready", "M7").render_cli()
        self.assertTrue(cli.startswith("[NEXT] state=seal_ready milestone=M7"))
        # 陈述式事实 + 成对选项；[NEXT] 无应答通道 ⇒ 不出疑问句、不出 y/N
        self.assertIn("fact: 里程碑 M7 审计已闭环（待修=0）；封板与否由你决定", cli)
        self.assertIn("option: k3dge milestone seal M7", cli)
        self.assertIn("option: 不封", cli)
        self.assertNotIn("？", cli)
        self.assertNotIn("y/N", cli)
        self.assertNotIn("ask:", cli)
        self.assertNotIn("<id>", cli)

    def test_audit_suggested_shape_with_reasons(self) -> None:
        cli = nextstep.NextStep.from_state(
            "audit_suggested", "M7", reasons=["账齐：本里程碑 3 个任务全 done，建议过一遍透镜"]
        ).render_cli()
        self.assertIn("[NEXT] state=audit_suggested milestone=M7", cli)
        self.assertIn("reason: 账齐", cli)
        self.assertIn("fact: 里程碑 M7 命中审计触发条件", cli)
        self.assertIn("option: k3dge milestone audit M7", cli)
        self.assertIn("option: 不审", cli)
        self.assertNotIn("？", cli)
        self.assertNotIn("y/N", cli)

    def test_audit_open_includes_pending(self) -> None:
        cli = nextstep.NextStep.from_state("audit_open", "M7", pending=3).render_cli()
        self.assertIn("pending=3", cli)
        self.assertIn("fact: 里程碑 M7 审计发现 3 项待修", cli)
        self.assertNotIn("<n>", cli)   # 占位符已填
        self.assertNotIn("？", cli)     # 疑问句只走 prompt（有 stdin）
        self.assertNotIn("倒计时", cli)   # [NEXT] 无倒计时在跑

    def test_seal_declined_is_broadcast_only(self) -> None:
        """播报态：只陈述事实，不给分支（无 options / 无 question）。"""
        cli = nextstep.NextStep.from_state("seal_declined", "M7").render_cli()
        self.assertIn("fact: 已放弃封板", cli)
        self.assertNotIn("option:", cli)
        ns = nextstep.NextStep.from_state("seal_declined", "M7")
        self.assertIsNone(ns.options)
        self.assertIsNone(ns.question)

    def test_mcp_isomorphic(self) -> None:
        d = nextstep.NextStep.from_state("seal_ready", "M7").render_mcp()
        self.assertEqual(d["state"], "seal_ready")
        self.assertIn("封板与否由你决定", d["fact"])
        self.assertNotIn("？", d["fact"])
        self.assertIn("k3dge milestone seal M7", d["options"][0])
        self.assertGreaterEqual(len(d["options"]), 2)
        # question 只给有应答通道的消费者；旧 ask/if_y/if_n 字段已退役
        self.assertIn("封板？", d["question"])
        for gone in ("ask", "if_y", "if_n", "note"):
            self.assertNotIn(gone, d)

    def test_rejection_maps_to_action(self) -> None:
        """闭集派发：gate_id → state/fact/options（不看文案）。"""
        n = nextstep.next_for_rejection(
            "M7", gates.Rejection("audit_report_missing", "no 12-col audit report found"))
        self.assertIn("k3dge milestone audit-submit M7", n.fact)
        n2 = nextstep.next_for_rejection(
            "M7", gates.Rejection("audit_closed", "audit not closed"))
        self.assertEqual(n2.state, "audit_needed")
        self.assertIn("未审计", n2.fact)
        # 命令在 options（成对选项），不再塞进 fact；占位符在渲染时填（filled_options）
        self.assertGreaterEqual(len(n2.options or []), 2)
        self.assertIn("k3dge milestone audit M7", n2.filled_options()[0])
        self.assertIn("option: k3dge milestone audit M7", n2.render_cli())
        self.assertNotIn("<id>", n2.render_cli())

    def test_rejection_without_gate_id_does_not_guess(self) -> None:
        """裸 str（无 gate_id）即使写满「未审计」也只能兑底为 rejected。

        锁死旧病：改前靠 `"未审计" in msg` 子串匹配，文案一改分支静默失效（A-01 同形）。
        """
        for prose in ("未审计不可封板", "no 12-col audit report", "audit_needed", "audit-submit"):
            n = nextstep.next_for_rejection("M7", prose)
            self.assertEqual(n.state, "rejected", prose)
            self.assertIn(prose, n.fact)   # 原文照登，不丢信息

    def test_explicit_gate_id_kwarg_wins(self) -> None:
        n = nextstep.next_for_rejection("M7", "任意文案", gate_id="tasks_all_done")
        self.assertEqual(n.state, "rejected")
        self.assertIn("票据未全 done", n.fact)

    def test_unknown_gate_id_falls_back(self) -> None:
        n = nextstep.next_for_rejection("M7", gates.Rejection("some_future_gate", "boom"))
        self.assertEqual(n.state, "rejected")
        self.assertIn("boom", n.fact)

    def test_gate_next_vocabulary_is_closed(self) -> None:
        """派发表的 key 必须是已声明的闸/动作 id 或内部 id——不得长出野生词汇。"""
        declared = set()
        for kind in gates.DEFAULTS["checks"]:
            unit = gates.DEFAULTS["checks"][kind]
            declared.update(unit.get("preconditions") or [])   # audit 单元只有 stages_*
            declared.update(unit.get("actions") or [])
        declared.update(gates.INTERNAL_GATE_IDS)
        self.assertEqual(set(nextstep.GATE_NEXT) - declared, set())
        for _gid, (state, fact_key) in nextstep.GATE_NEXT.items():
            self.assertIn(state, nextstep.STATE_OPTIONS)
            if fact_key:
                self.assertIn(fact_key, nextstep.REJECTION_FACTS)


class TestDecisionSingleSource(TestCase):
    """判定文案单源：prompt 与 [NEXT] 共用 STATE_OPTIONS（票 decision_single_source）。"""

    def test_question_text_fills_placeholders(self) -> None:
        self.assertEqual(nextstep.question_text("seal_ready", "M7"), "里程碑 M7：封板？")
        self.assertEqual(
            nextstep.question_text("audit_open", "M7", n=3), "里程碑 M7：3 项待修，agent 修？")

    def test_two_projections_of_one_declaration(self) -> None:
        """同一判定两个投影：`[NEXT]` 出陈述式 fact，prompt 出疑问式 question。

        两者同源于 STATE_OPTIONS 的同一条声明（不是两份文案）；各自的形状由
        ADR-0026 §2.2 语法维决定（有无应答通道）。
        """
        for state, n in (("seal_ready", None), ("audit_open", 5)):
            opt = nextstep.STATE_OPTIONS[state]
            self.assertTrue(opt.get("fact") and opt.get("question"), state)
            ns = nextstep.NextStep.from_state(state, "M7", pending=n)
            cli = ns.render_cli()
            self.assertIn(ns._fill(opt["fact"]), cli)          # fact 进 [NEXT]
            self.assertNotIn(opt["question"].split("：")[-1], cli)  # question 不进 [NEXT]
            self.assertEqual(nextstep.question_text(state, "M7", n=n), ns._fill(opt["question"]))

    def test_question_text_falls_back_to_fact(self) -> None:
        """无 question 的态（不交互）回落 fact；未知态返回空串。"""
        self.assertIn("不可封板", nextstep.question_text("audit_needed", "M7"))
        self.assertEqual(nextstep.question_text("no_such_state", "M7"), "")

    def test_no_hardcoded_ask_literals_in_src(self) -> None:
        """结构守卫：`prompt.ask(...)` 的首参不得是硬编码字面量（否则又长出第二源）。"""
        import ast

        root = Path(__file__).resolve().parents[3] / "src" / "k3dge"
        offenders = []
        for py in sorted(root.rglob("*.py")):
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                if name != "ask" or not node.args:
                    continue
                if isinstance(node.args[0], (ast.Constant, ast.JoinedStr, ast.BinOp)):
                    offenders.append(f"{py.relative_to(root)}:{node.lineno}")
        self.assertEqual(offenders, [])


class TestPersistedProjection(TestCase):
    def test_roundtrip(self) -> None:
        ws = Path(tempfile.mkdtemp())
        nextstep.persist(ws, nextstep.NextStep.from_state("audit_needed", "M7"))
        self.assertEqual(nextstep.load_persisted(ws)["state"], "audit_needed")

    def test_missing_or_corrupt_is_none(self) -> None:
        ws = Path(tempfile.mkdtemp())
        self.assertIsNone(nextstep.load_persisted(ws))
        p = ws / ".k3dge" / "next.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{not json", encoding="utf-8")
        self.assertIsNone(nextstep.load_persisted(ws))
        p.write_text('{"milestone": "M7"}', encoding="utf-8")   # 无 state ⇒ 不可投影
        self.assertIsNone(nextstep.load_persisted(ws))

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


class TestProjectionInvariants(TestCase):
    """ADR-0026 §2.2 语法维/目标维的可执行版（memo S7 四条不变量，本轮落地）。"""

    def test_fact_never_ends_with_question_mark(self) -> None:
        bad = [s for s, o in nextstep.STATE_OPTIONS.items()
               if (o.get("fact") or "").rstrip().endswith(("？", "?"))]
        self.assertEqual(bad, [])

    def test_rendered_next_has_no_interrogative(self) -> None:
        """`[NEXT]` 是纯打印面：渲染结果不得出现疑问句/应答通道词汇。"""
        for state in nextstep.STATE_OPTIONS:
            cli = nextstep.NextStep.from_state(state, "M7", pending=2).render_cli()
            self.assertNotIn("？", cli, state)
            self.assertNotIn("?", cli.split("pointers:")[0], state)
            for word in ("y/N", "Y/n", "倒计时", "ask:", "if y:", "if n:"):
                self.assertNotIn(word, cli, f"{state}: {word}")

    def test_options_come_in_pairs(self) -> None:
        """有 options 的态必须 ≥2 个（只给一条路＝下令，不是给判断主体）。"""
        bad = [s for s, o in nextstep.STATE_OPTIONS.items()
               if o.get("options") and len(o["options"]) < 2]
        self.assertEqual(bad, [])

    def test_broadcast_states_have_no_branch(self) -> None:
        """播报态（无 options）不得带 question——没有分支就没有可问的判定。"""
        bad = [s for s, o in nextstep.STATE_OPTIONS.items()
               if not o.get("options") and o.get("question")]
        self.assertEqual(bad, [])

    def test_question_implies_interactive_state(self) -> None:
        """question 只允许出现在真有 prompt 的态（seal_ready / audit_open）。"""
        prompted = {"seal_ready", "audit_open"}
        with_q = {s for s, o in nextstep.STATE_OPTIONS.items() if o.get("question")}
        self.assertEqual(with_q, prompted)

    def test_every_state_projects_a_fact(self) -> None:
        self.assertEqual([s for s, o in nextstep.STATE_OPTIONS.items() if not o.get("fact")], [])
