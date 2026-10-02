"""Tests for the single-source [NEXT] hints and the audit-first lifecycle wiring."""


import tempfile
from pathlib import Path
from unittest import TestCase, mock

from k3dge.engine import audit_trigger, gates, nextstep
import shutil
import atexit

REPO = Path(__file__).resolve().parents[3]


class TestNextStepRender(TestCase):
    def test_seal_ready_shape(self) -> None:
        cli = nextstep.NextStep.from_state("seal_ready", "M7").render_cli()
        self.assertTrue(cli.startswith("[NEXT] state=seal_ready milestone=M7"))
        # 陈述式事实 + 成对选项；[NEXT] 无应答通道 ⇒ 不出疑问句、不出 y/N
        self.assertIn("fact: 里程碑 M7 形式闸与票已齐；是否收这一章由你决定"
                      "（seal 会跑：预审 → 审计 → 收摊）", cli)
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
        self.assertIn("是否收这一章由你决定", d["fact"])
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
        # `audit_closed` 已退休（ADR-0004 §2.1.3：报告降为可选产物、审计由 seal 自己跑）
        # ⇒ 派发表里不得留它的项（留着就是永不出现的野生键）
        self.assertNotIn("audit_closed", nextstep.GATE_NEXT)
        for gone in ("audit_closed", "evidence_chain", "audit_fresh"):
            self.assertNotIn(gone, nextstep.GATE_NEXT, gone)
        n2 = nextstep.NextStep.from_state("seal_ready", "M7")
        # 命令在 options（成对选项），不再塞进 fact；占位符在渲染时填（filled_options）
        self.assertGreaterEqual(len(n2.options or []), 2)
        self.assertIn("k3dge milestone seal M7", n2.filled_options()[0])
        self.assertIn("option: k3dge milestone seal M7", n2.render_cli())
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
        """无 question 的态（不交互）回落 fact；未知态返回空串。

        用**真的没有 question** 的态（ocr t-210）：`audit_open` 声明了 question 且
        恰好也含"待修"，拿它测回落＝fallback 分支从不被走。等值对账声明表，不测子串。
        """
        opt = nextstep.STATE_OPTIONS["sealed"]
        self.assertNotIn("question", opt)
        self.assertEqual(nextstep.question_text("sealed", "M7"), opt["fact"])
        self.assertEqual(nextstep.question_text("no_such_state", "M7"), "")

    def test_no_hardcoded_ask_literals_in_src(self) -> None:
        """结构守卫：`prompt.ask(...)` 的问句不得是硬编码字面量（否则又长出第二源）。

        收口三处（ocr t-208）：①关键字形状也要查——`ask` 声明为
        `ask(self, question, *, countdown, default_yes)`，写 `ask(question="…")`
        时 `node.args` 为空，旧守卫直接跳过；②只认**名为 `prompt` 的接收者**上的
        `ask`（裸名匹配会把无关 helper `ask(...)` 也卷进来）；③正向控制——
        真的扫到了调用点才谈"没有违例"，守卫不能对着白墙绿。
        """
        import ast

        root = Path(__file__).resolve().parents[3] / "src" / "k3dge"
        offenders = []
        sites = 0
        for py in sorted(root.rglob("*.py")):
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                    continue
                if node.func.attr != "ask" or not isinstance(node.func.value, ast.Name):
                    continue
                if node.func.value.id != "prompt":
                    continue
                sites += 1
                first = node.args[0] if node.args else next(
                    (kw.value for kw in node.keywords if kw.arg in (None, "question")), None)
                if first is None:
                    continue          # 没传问句＝运行期另有来源，不是本守卫的靶面
                if isinstance(first, (ast.Constant, ast.JoinedStr, ast.BinOp)):
                    offenders.append(f"{py.relative_to(root)}:{node.lineno}")
        self.assertGreaterEqual(sites, 2, f"守卫白扫：src/ 里 prompt.ask 调用点只剩 {sites} 处")
        self.assertEqual(offenders, [], "问句必须走 nextstep.question_text（单源 STATE_OPTIONS）")


class TestPersistedProjection(TestCase):
    def test_roundtrip(self) -> None:
        ws = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, ws, ignore_errors=True)
        nextstep.persist(ws, nextstep.NextStep.from_state("audit_open", "M7"))
        self.assertEqual(nextstep.load_persisted(ws)["state"], "audit_open")

    def test_missing_or_corrupt_is_none(self) -> None:
        ws = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, ws, ignore_errors=True)
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
    atexit.register(shutil.rmtree, ws, True)
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
    """喂**真格式**（`-z`＝NUL 分隔）＋正向控制（ocr t-211）。

    旧 mock 给的是换行分隔的 stdout：整串落进**一条**记录"碰巧"解析出想要的路径——
    `-z` 判据若回归（split 改回 `\n`、`R`/`C` 双记录跳过被破坏）这些测不红；
    且 `_workspace_hints` 外面包着 `except Exception: return []`，纯负断言分不清
    "确实没提示"与"整个炸了早退"。⇒ 每条负测都先验 git 真被调用（含 `-z` 与 cwd）。
    """

    def _run_git(self, stdout_z: str):
        from k3dge.cli import main as cli_main

        ws = _base_ws()
        with mock.patch("subprocess.run") as run:
            run.return_value = mock.MagicMock(stdout=stdout_z, returncode=0)
            hints = cli_main._workspace_hints(ws)
        run.assert_called_once()
        self.assertIn("-z", run.call_args[0][0])            # 判据＝NUL 分隔格式
        self.assertEqual(run.call_args.kwargs.get("cwd"), ws)
        return ws, hints

    def test_new_domain_detected(self) -> None:
        _ws, hints = self._run_git("?? src/newdom/bar.py\0")
        self.assertIn("new_domain", [h.state for h in hints])

    def test_known_domain_not_new(self) -> None:
        _ws, hints = self._run_git(" M src/k3dge/engine/foo.py\0")
        # overview staleness is no longer a standalone hint (folded into audit_suggested)
        self.assertEqual(hints, [])

    def test_bare_untracked_tree_not_new_domain(self) -> None:
        # whole tree untracked -> git collapses to "?? src/"; that is NOT a new domain
        _ws, hints = self._run_git("?? src/\0")
        self.assertEqual([h.state for h in hints], [])

    def test_top_level_file_under_src_not_new_domain(self) -> None:
        """`src/__main__.py` 是 zipapp 入口**文件**，不是域——曾被 new_domain 误报，
        逼操作者去 manifest 注册一个不存在的域（启发式：域＝`src/<dir>/…`，≥3 段）。"""
        _ws, hints = self._run_git("?? src/__main__.py\0")
        self.assertEqual([h.state for h in hints], [])
        # 对照：真的新域（目录级）仍要报
        _ws, hints = self._run_git("?? src/newdom/mod.py\0")
        self.assertIn("new_domain", [h.state for h in hints])

    def test_porcelain_paths_splits_nul_and_consumes_rename_origin(self) -> None:
        """重命名记录正是 `-z` 解析器存在的理由（381），此前零覆盖。"""
        from k3dge.cli import main as cli_main

        out = (" M src/k3dge/engine/foo.py\0"
               "R  src/k3dge/engine/new.py\0src/k3dge/engine/old.py\0"
               "?? docs/specs/engine/spec.md\0\0")
        self.assertEqual(cli_main._porcelain_paths(out),
                         ["src/k3dge/engine/foo.py", "src/k3dge/engine/new.py",
                          "docs/specs/engine/spec.md"])

    def test_rename_inside_known_domain_not_new(self) -> None:
        """`R` 的原始路径必须被消费：若双记录跳过被破坏，`src/ghostdom/old.py` 会漏进
        改动面 ⇒ 假报 new_domain。这条测对旧解析（整行当一个路径）也可红。"""
        _ws, hints = self._run_git("R  src/k3dge/engine/new.py\0src/ghostdom/old.py\0")
        self.assertEqual([h.state for h in hints], [])


class TestLifecycleNext(TestCase):
    def test_seal_ready_when_precheck_green(self) -> None:
        """ADR-0004 §2.1.9：审计**不是**封板的前置闸（seal 相位 2 自己跑）⇒ 票全 done
        且预审无"需人先办"时 `[NEXT]` 直接给 `seal_ready`，不再先要一次独立审计。"""
        from k3dge.cli import main as cli_main

        ws = _base_ws()
        ns = cli_main._lifecycle_next(ws)
        self.assertEqual(ns.state, "seal_ready")
        self.assertIn("预审待办：全绿", ns.render_cli())

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
        self.assertIn("k3dge ADR-0004 §2.1.9", cli)
        d = ns.render_mcp()
        self.assertIn("pointers", d)
        self.assertIn("k3dge ADR-0004 §2.1.9", d["pointers"])

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

        旧守卫遍历的是 `ask/if_y/if_n/note`——这些字段早已从 STATE_OPTIONS 退役
        （`test_mcp_isomorphic` 自己就断言它们不存在），内层永远取到 `None` ⇒
        恒绿空转（ocr t-207）。改为遍历**真的在声明**的显示字段，并正向控制
        "确实扫到了串"。
        """
        bad = ("y/N", "Y/n", "倒计时")
        scanned = 0
        for state, opt in nextstep.STATE_OPTIONS.items():
            for field in ("fact", "fact_blocked", "fact_with_blockers",
                          "question", "options", "pointers"):
                val = opt.get(field)
                items = val if isinstance(val, list) else ([val] if val else [])
                for s in items:
                    scanned += 1
                    for b in bad:
                        self.assertNotIn(b, s, f"{state}.{field} 含通道词汇 {b}：{s}")
        self.assertGreater(scanned, 10, f"守卫白扫：只取到 {scanned} 条显示串")

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

    def test_every_state_declares_a_priority(self) -> None:
        """`priority` 是闭集声明（同一轮多处理点的"先看哪个"）；缺它 ⇒ 排序退化。"""
        allowed = {1, 2, 3, 4, 5, 9}
        for state, opt in nextstep.STATE_OPTIONS.items():
            self.assertIn("priority", opt, state)
            self.assertIn(int(opt["priority"]), allowed, state)

    def test_priority_flows_into_both_projections(self) -> None:
        """priority 进 MCP 投影（读侧要能自己排序）；`[NEXT]` 不打印它（顺序已表达）。"""
        ns = nextstep.NextStep.from_state("pending_findings", "M7", pending=1)
        self.assertEqual(ns.priority, 1)
        self.assertEqual(ns.render_mcp()["priority"], 1)
        self.assertNotIn("priority", ns.render_cli())

    def test_every_state_projects_a_fact(self) -> None:
        self.assertEqual([s for s, o in nextstep.STATE_OPTIONS.items() if not o.get("fact")], [])


class TestSealReadyStatesItsBlockers(TestCase):
    """`[NEXT] seal_ready` 的事实必须与 `seal` 的实际判据同源。

    此前只说"审计已闭环"就让人去封板，而 seal 还要过 8 个前置闸（align marker /
    ADR 全 Accepted / docs_normalized …）⇒ 操作者跑到 seal 才发现。
    """

    def _ws(self, preconditions: list, pending_task: bool = False) -> Path:
        """空仓里大部分形式闸都"过"（无 guides/无 ADR 就是没有偏差）；要隔离"未过闸被列出"
        就得放一个**真会失败**的事实：一张未 done 的 M10 票（`tasks_all_done` 会拒）。"""
        ws = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, ws, ignore_errors=True)
        (ws / ".agent").mkdir(parents=True)
        body = ", ".join(f'"{p}"' for p in preconditions)
        (ws / ".agent" / "pipeline.toml").write_text(
            f"[checks.seal]\npreconditions = [{body}]\n", encoding="utf-8")
        if pending_task:
            (ws / "docs" / "tasks").mkdir(parents=True)
            (ws / "docs" / "tasks" / "2026-09-01-M10-feat-x.md").write_text(
                "---\nstatus: idea\nmilestone: M10\npriority: P2\ndate: 2026-09-01\n---\n\n# X\n",
                encoding="utf-8")
        return ws

    def test_lists_unmet_preconditions(self) -> None:
        # 空仓里形式闸几乎都"过"（无 guides/无 ADR ＝ 无偏差）⇒ 放一张未 done 的票，
        # 让 `tasks_all_done` 真失败，隔离"未过闸被列出"这一行为
        ws = self._ws(["tasks_all_done"], pending_task=True)
        ns = nextstep.seal_ready_for(ws, "M10")
        cli = ns.render_cli()
        self.assertIn("预审待办：tasks_all_done", cli)
        self.assertNotIn("<blockers>", cli)
        self.assertTrue(ns.reasons and "tasks_all_done" in ns.reasons[0])

    def test_says_all_green_when_clean(self) -> None:
        ws = self._ws([])
        (ws / "docs" / "tasks").mkdir(parents=True)
        (ws / "docs" / "tasks" / "2026-09-01-M10-feat-x.done.md").write_text(
            "---\nstatus: done\nmilestone: M10\npriority: P2\ndate: 2026-09-01\n---\n\n# X\n\n## 结案\n- x\n",
            encoding="utf-8")
        ns = nextstep.seal_ready_for(ws, "M10")
        self.assertEqual(ns.state, "seal_ready")
        self.assertIn("预审待办：全绿", ns.render_cli())

    def test_empty_milestone_is_not_seal_ready(self) -> None:
        ws = self._ws([])
        ns = nextstep.seal_ready_for(ws, "M10")
        self.assertEqual(ns.state, "normal")

    def test_repo_blockers_are_same_source_as_the_gate(self) -> None:
        """自举：`[NEXT]` 列的待办必须与 `seal` 的预审**同源**（同一份判据，不是各写一套）。

        断言**机制**而不是本仓此刻哪些闸红：曾写成"本仓 M10 必有 adrs_all_accepted"
        ——那是**瞬时状态**，ADR-0026 一转 Accepted 它就红（克隆操演时实测）。不变量是：
        ①`reasons` 与 `unmet_seal_preconditions` 逐条一致；②⚙️ 项（`satisfies` 声明，如
        `align_pass`）不得进"需人先办"；③退休的报告类闸不得出现。

        本仓依赖不满足时**显式 skip**，不静默早退（ocr t-212）：旧写法在浅克隆/
        已安装包装/无当前里程碑时只断一条 `state == "normal"` 就 return，CI 报绿
        但不变量从没被验——fail-open 的逃逸口。判据面（hermetic）由
        `test_lists_unmet_preconditions` 兜底，这里红/绿都真话。
        """
        from k3dge.engine.seal import unmet_seal_preconditions
        from k3dge.engine.milestone_pointer import get_current_milestone
        from k3dge.engine.task_index import scan_milestone_tasks

        hermetic = "隔离形状由 test_lists_unmet_preconditions 等用例覆盖"
        mid = get_current_milestone(REPO)
        if not mid:
            self.skipTest(f"{REPO} 无当前里程碑（浅克隆/安装态？）；{hermetic}")
        if not scan_milestone_tasks(REPO, mid):
            self.skipTest(f"{REPO} 的 {mid} 无在办票；{hermetic}")
        ns = nextstep.seal_ready_for(REPO, mid)
        unmet = [gid for gid, _msg in unmet_seal_preconditions(REPO, mid)]
        self.assertEqual([r.split("：")[0] for r in (ns.reasons or [])], unmet[:4])
        if not unmet:
            self.assertIn("预审待办：全绿", ns.render_cli())
        for gone in ("align_pass", "audit_fresh", "audit_closed", "evidence_chain"):
            self.assertNotIn(gone, ns.fact, gone)

    def test_base_fact_has_no_placeholder_leak(self) -> None:
        """`from_state("seal_ready")` 仍可单独用 ⇒ 基础 fact 不得含占位符。"""
        cli = nextstep.NextStep.from_state("seal_ready", "M7").render_cli()
        self.assertNotIn("<blockers>", cli)
        self.assertNotIn("预审待办", cli)


class TestSealReadyHasOneConstructionEntry(TestCase):
    """棘轮：生产代码里 `seal_ready` 只能用 `seal_ready_for()` 产出。

    否则某条路径会渲染出没有前置信息的 seal_ready（投影与判据分叉）。

    形状面收口（ocr t-209）：旧守卫只看**名为 `from_state` 的调用 + 首个位置参**。
    `from_state(state="seal_ready", …)`（关键字形状）与 `NextStep(state="seal_ready", …)`
    （公开再导出的数据类直接构造）都造得出同一个分叉投影，却都从指缝溜走。
    已知限度（如实登记，不装全覆盖）：守卫只认 **Constant**——经变量/字典中转
    （如 `mcp.py` 的 `nxt_state` 兜底表）解析不到字面量，那条路径的正当性靠
    `load_persisted` 优先（流程自己判过）+ `test_mcp_isomorphic` 的投影对账兜底。
    """

    def test_no_raw_construction_in_src(self) -> None:
        import ast

        root = Path(__file__).resolve().parents[3] / "src" / "k3dge"
        offenders = []
        for py in sorted(root.rglob("*.py")):
            if py.name == "nextstep.py":
                continue
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                if name not in ("from_state", "NextStep"):
                    continue
                state_arg = node.args[0] if node.args else next(
                    (kw.value for kw in node.keywords if kw.arg == "state"), None)
                if isinstance(state_arg, ast.Constant) and state_arg.value == "seal_ready":
                    offenders.append(f"{py.relative_to(root)}:{node.lineno}")
        self.assertEqual(offenders, [], f"用 seal_ready_for() 代替：{offenders}")


class TestSidecarAndRejectionShape(TestCase):
    """侧车语义、`seal_ready` 事实的声明单源、`rejected` 的 priority/pointers（ocr-275/276/277）。"""

    def test_emit_all_upserts_instead_of_overwriting(self) -> None:
        ws = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, ws, ignore_errors=True)
        nextstep.emit(ws, nextstep.NextStep.from_state("doc_fix", "M7"))
        nextstep.emit_all(ws, [nextstep.NextStep.from_state("seal_ready", "M7")])
        states = [c.get("state") for c in (nextstep.load_all(ws) or [])]
        self.assertIn("doc_fix", states, "emit_all 整片覆盖会抹掉同轮先落地的处理点")
        self.assertIn("seal_ready", states)

    def test_blocked_seal_fact_comes_from_declaration(self) -> None:
        ws = _base_ws()
        with mock.patch("k3dge.engine.seal.unmet_seal_preconditions",
                        return_value=[("tasks_all_done", "还有票未 done")]):
            ns = nextstep.seal_ready_for(ws, "M7")
        self.assertIn("形式闸未齐", ns.fact)
        self.assertNotIn("形式闸与票已齐", ns.fact)
        # 单源＝声明表：改措辞不会让"未齐"退化成"已齐"（旧实现靠散文 replace）
        self.assertTrue(ns.fact.startswith(
            nextstep.STATE_OPTIONS["seal_ready"]["fact_blocked"].replace("<id>", "M7")), ns.fact)
        self.assertTrue(any("tasks_all_done" in r for r in ns.reasons), ns.reasons)

    def test_routed_rejection_also_carries_declared_priority(self) -> None:
        """路由分支以前只带 options ⇒ priority/pointers 留在声明表里没读（t-206）。"""
        gid = next(iter(nextstep.GATE_NEXT))
        state = nextstep.GATE_NEXT[gid][0]
        opt = nextstep.STATE_OPTIONS[state]
        ns = nextstep.next_for_rejection("M7", "被拒", gate_id=gid)
        assert ns.state == state
        assert ns.priority == int(opt.get("priority", 3)), (ns.priority, opt)
        assert ns.pointers == (list(opt.get("pointers") or []) or None), ns.pointers

    def test_rejected_keeps_declared_priority_and_pointers(self) -> None:
        opt = nextstep.STATE_OPTIONS["rejected"]
        ns = nextstep.next_for_rejection("M7", "某种没登记 gate_id 的拒绝")
        self.assertEqual(ns.priority, opt["priority"])
        self.assertEqual(ns.pointers, opt["pointers"])
        self.assertEqual(ns.state, "rejected")
