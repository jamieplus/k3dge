"""Tests for the seal-flow state machine and peer-action runner."""

from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path
from unittest import TestCase, mock

from k3dge.engine import audit_checklist as ac
from k3dge.engine.align import run_milestone_alignment
from k3dge.engine.audit_report import _find_audit_report, _parse_audit_stats
from k3dge.engine.milestone_audit import (
    _audit_mode,
    _ensure_leftovers,
    _ratchet_audit_step,
    persist_external_audit_report,
    run_audit_flow,
)
from k3dge.engine import gates
from k3dge.engine.prompt import Prompt as _Prompt
from k3dge.engine.seal_flow import run_seal_flow
from k3dge.engine.task_write import create_task, mark_task_done
from k3dge.engine.pipeline_runner import (
    TransportResult,
    load_pipeline_config,
    resolve_action,
    run_action,
)

#: 真透镜（mcp/cli）跑通：审计结果 `closed`（ADR-0004 §2.1.11）。
_OK_MCP = TransportResult(True, "mcp", "ok")
#: manual **传输**（不论降级位还是首选位）：结果 `degraded-manual`、报告须署名（🅰2）。
_OK_MANUAL = TransportResult(True, "manual", "ok")


def _record_ok():
    """相位 3 的封版记录桩：真实提交+tag 由 TestSealRecord 用真 git 仓测。"""
    return mock.patch("k3dge.engine.seal.seal_record",
                      return_value=(True, "封版提交 abc1234；边界 tag：M1 = deadbeef"))


def _audit_ok(status: str = "audited"):
    """seal 相位 2 的审计桩：`run_audit_flow` 自身的语义由 TestAuditFlow/TestAuditNoNoop 管，
    seal 这边只关心"审计返回了什么 ⇒ 封板走不走"（ADR-0004 §2.1.9/§2.1.11）。"""
    return mock.patch("k3dge.engine.milestone_audit.run_audit_flow",
                      return_value=(status, f"audit {status}"))


def _mk_task(ws, mid="M1"):
    """Create a done task so the seal checklist reports eligibility."""
    ws.joinpath("docs", "tasks").mkdir(parents=True, exist_ok=True)
    p = ws / "docs" / "tasks" / f"2026-09-01-{mid}-feat-x.md"
    p.write_text(f"# X\n- **Status**: done\n- **Milestone**: {mid}\n", encoding="utf-8")
    return p


def _ws() -> Path:
    d = Path(tempfile.mkdtemp())
    (d / ".agent").mkdir()
    (d / ".agent" / "milestone").write_text("M1\n", encoding="utf-8")
    (d / "docs" / "reviews").mkdir(parents=True)
    return d


# 审计腿形状必须显式声明：`_audit_mode` 缺省值是 "oneshot"，而本仓与模板的
# pipeline.toml 都写 `mode = "ratchet"`。靠默认值走 oneshot 的测试不声明自己
# 测的是哪条路——一旦默认值改变就静默改测另一条。故 oneshot 测试一律用本 helper。
_ONESHOT = '[roles.audit]\nbind = "k3dit"\nmode = "oneshot"\n\n[peers.k3dit]\nenabled = true\n'


def _ws_oneshot() -> Path:
    """`_ws()` + 显式 `mode = "oneshot"`（与当前默认值同效，仅把隐式变显式）。"""
    ws = _ws()
    (ws / ".agent" / "pipeline.toml").write_text(_ONESHOT, encoding="utf-8")
    return ws


_AUDIT = (
    "| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |\n"
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
    "| A1 | x | s | p | t | desc1 | loc | 待修 | - | - | 待复审 | - |\n"
    "| A2 | x | s | p | t | desc2 | loc | 有意留 | - | - | 通过 | - |\n"
    "| A3 | x | s | p | t | desc3 | loc | 已修 | - | - | 通过 | - |\n"
)


class TestAuditStats(TestCase):
    def test_parse_counts(self) -> None:
        stats = _parse_audit_stats(_AUDIT)
        self.assertEqual(stats["待修"], 1)
        self.assertEqual(stats["有意留"], 1)
        self.assertEqual(stats["已修"], 1)
        self.assertEqual(stats["total"], 3)

    def test_find_report(self) -> None:
        ws = _ws()
        p = ws / "docs" / "reviews" / "2026-09-01-M1-x.md"
        p.write_text(_AUDIT, encoding="utf-8")
        found = _find_audit_report(ws, "M1")
        self.assertIsNotNone(found)
        self.assertEqual(found[0], p)

    def test_ensure_leftovers(self) -> None:
        ws = _ws()
        p = ws / "docs" / "reviews" / "2026-09-01-M1-x.md"
        p.write_text(_AUDIT, encoding="utf-8")
        _ensure_leftovers(ws, _AUDIT, p)
        leftover = (ws / "docs" / "reviews" / "LEFTOVERS.md").read_text(encoding="utf-8")
        self.assertIn("A2", leftover)
        self.assertIn("有意留", leftover)


class TestPrompt(TestCase):
    def test_injected_answers(self) -> None:
        pr = _Prompt(answers=["y", "n"])
        self.assertTrue(pr.ask("enter?", default_yes=False))
        self.assertFalse(pr.ask("fix?", default_yes=True))

    def test_non_interactive_defaults(self) -> None:
        pr = _Prompt(in_stream=io.StringIO(""), out_stream=io.StringIO())
        self.assertFalse(pr.ask("enter?", default_yes=False))  # N
        self.assertTrue(pr.ask("fix?", default_yes=True))      # Y


class TestPipelineRunner(TestCase):
    def test_resolve_and_run_cli(self) -> None:
        ws = _ws()
        (ws / ".agent" / "pipeline.toml").write_text(
            '[peers.k3dit.actions.echo]\n'
            'transports = [ { provider = "cli", command = "echo RAN", timeout = 5 } ]\n',
            encoding="utf-8",
        )
        cfg = load_pipeline_config(ws)
        self.assertIsNotNone(resolve_action(cfg, "k3dit.actions.echo"))
        out = io.StringIO()
        res = run_action(ws, "k3dit.actions.echo", io=out)
        self.assertTrue(res.ok)
        self.assertEqual(res.provider, "cli")

    def test_skip_records_and_logs(self) -> None:
        ws = _ws()
        (ws / ".agent" / "pipeline.toml").write_text(
            '[peers.k3dit.actions.none]\n'
            'transports = [ { provider = "skip" } ]\n',
            encoding="utf-8",
        )
        res = run_action(ws, "k3dit.actions.none", io=io.StringIO())
        self.assertTrue(res.ok)
        self.assertTrue(res.skipped)
        self.assertTrue((ws / "logs" / "k3dge.log").is_file())


_AUDIT_CLEAN = _AUDIT.replace("待修", "已修").replace("有意留", "已修")

#: 报告署名/来源/锚点（ADR-0017 的 `_SIGN_KEYS`）：`degraded-manual` 的前提。
_SIGNS = "\n- **审计人**: k3dit@seat\n- **透镜来源**: k3dit\n- **基线**: deadbeef\n"


def _clean_report(ws, mid="M1"):
    """Single merged audit report (ADR-0025) with 待修=0; a stray quality file must be ignored."""
    (ws / "docs" / "reviews" / f"2026-09-01-{mid}-audit.md").write_text(_AUDIT_CLEAN, encoding="utf-8")


def _open_report(ws, mid="M1"):
    """Single audit report still has 待修>0 (audit loop not closed)."""
    (ws / "docs" / "reviews" / f"2026-09-01-{mid}-audit.md").write_text(_AUDIT, encoding="utf-8")


class TestAuditFlow(TestCase):
    def test_produce_and_verify_send_action_level_arguments(self) -> None:
        """ADR-0006 §2.3.8: k3dge asks for "audit this milestone", never for pass numbers,
        and tells the verify transport *which* report to check."""
        ws = _ws_oneshot()
        _clean_report(ws)
        calls = []

        def fake(_ws, ref, *, io=None, timeout_default=60, arguments=None):
            calls.append((ref, arguments or {}))
            return TransportResult(True, "mcp", "ok")

        with mock.patch("k3dge.engine.pipeline_runner.run_action", side_effect=fake):
            status, _ = run_audit_flow(ws, "M1", prompter=_Prompt(answers=["y"]))
        self.assertEqual(status, "audited")
        # ref 是**角色名**（audit.actions.*），由 [roles.audit] bind 解析到 peer——
        # 下游换实现不用改声明（pipeline.toml 既定口径：新流程一律走角色名）
        produce = {r: a for r, a in calls if r.endswith(("actions.audit", "actions.quality"))}
        self.assertIn("audit.actions.audit", produce)
        self.assertNotIn("pass_number", produce["audit.actions.audit"])  # never leaks k3dit internals
        self.assertIn("M1", produce["audit.actions.audit"].get("target_scope", ""))
        self.assertEqual(produce["audit.actions.audit"].get("milestone_id"), "M1")
        verify = {r: a for r, a in calls if r.endswith("actions.verify")}
        self.assertIn("audit.actions.verify", verify)
        self.assertTrue(str(verify["audit.actions.verify"].get("path", "")).endswith(".md"))

    def test_rejection_quotes_the_peer_suggested_report_path(self) -> None:
        ws = _ws_oneshot()  # no report on disk
        payload = json.dumps({"ok": True, "lens_count": 5, "report_path": "docs/reviews/2026-09-03-M1-code.md"})
        with mock.patch(
            "k3dge.engine.pipeline_runner.run_action",
            return_value=TransportResult(True, "mcp", "ok", payload=payload),
        ):
            status, msg = run_audit_flow(ws, "M1", prompter=_Prompt(answers=["y"]))
        self.assertEqual(status, "rejected")
        self.assertIn("docs/reviews/2026-09-03-M1-code.md", msg)
        self.assertIn("k3dge 不代笔正文", msg)

    def test_audited_when_clean(self) -> None:
        ws = _ws_oneshot()
        _clean_report(ws)
        with mock.patch("k3dge.engine.pipeline_runner.run_action", return_value=_OK_MCP):
            status, _ = run_audit_flow(ws, "M1", prompter=_Prompt(answers=["y"]))
        self.assertEqual(status, "audited")

    def test_rejected_when_audit_missing(self) -> None:
        ws = _ws_oneshot()  # no report
        with mock.patch("k3dge.engine.pipeline_runner.run_action", return_value=_OK_MCP):
            status, _ = run_audit_flow(ws, "M1", prompter=_Prompt(answers=["y"]))
        self.assertEqual(status, "rejected")

    def test_declined_fix_rejects(self) -> None:
        ws = _ws_oneshot()
        _open_report(ws)
        with mock.patch("k3dge.engine.pipeline_runner.run_action", return_value=_OK_MCP):
            status, _ = run_audit_flow(ws, "M1", prompter=_Prompt(answers=["n"]))
        self.assertEqual(status, "rejected")

    def test_escalates_after_max_verify_attempts(self) -> None:
        ws = _ws_oneshot()
        _open_report(ws)
        with mock.patch("k3dge.engine.pipeline_runner.run_action", return_value=_OK_MCP):
            # three fix-yes answers -> 4th loop escalates (max=3)
            status, _ = run_audit_flow(
                ws, "M1", prompter=_Prompt(answers=["y", "y", "y"]), max_verify_attempts=3
            )
        self.assertEqual(status, "escalated")


class TestSealFlow(TestCase):
    def test_seal_runs_the_audit_itself_and_refusal_stops_it(self) -> None:
        """相位 2（ADR-0004 §2.1.9）：审计由 **seal 自己**跑（不再靠外部 hook 先跑）。
        审计没正常返回（refused/escalated）⇒ 不归档、不前进版号。"""
        ws = _ws()
        _mk_task(ws)
        with mock.patch("k3dge.engine.milestone_audit.run_audit_flow",
                        return_value=("refused", "审计未成（跳被跳过）")) as audit, \
             mock.patch("k3dge.engine.seal_flow.run_milestone_alignment", return_value=(True, "ok", [])), \
             mock.patch("k3dge.engine.seal_flow.seal_milestone", return_value=(True, "sealed")) as seal:
            status, msg = run_seal_flow(ws, "M1", prompter=_Prompt(answers=["y"]))
        self.assertEqual(status, "rejected")
        self.assertIn("refused", msg)
        audit.assert_called_once()
        seal.assert_not_called()

    def test_version_advances_after_the_audit_returns(self) -> None:
        """ADR-0004 §2.1.9/§2.1.11：**版号在审计正常返回后前进**，不管有没有报告；
        `no_version_bump` 是显式逃生口（不动版本文件，其余照旧）。"""
        for bump_flag, expected in ((False, "1.2.4"), (True, "1.2.3")):
            ws2 = _ws()
            (ws2 / "docs" / "tasks").mkdir(parents=True, exist_ok=True)
            (ws2 / "docs" / "tasks" / "2026-09-01-M1-feat-x.md").write_text(
                "---\nstatus: done\nmilestone: M1\npriority: P2\ndate: 2026-09-01\n---\n\n# X\n",
                encoding="utf-8")
            (ws2 / "pyproject.toml").write_text(
                '[project]\nname = "x"\nversion = "1.2.3"\n', encoding="utf-8")
            with _audit_ok(), _record_ok(), \
                 mock.patch("k3dge.engine.seal_flow.run_milestone_alignment", return_value=(True, "ok", [])):
                with mock.patch("k3dge.engine.seal_flow.seal_preconditions_error", return_value=None):
                    with mock.patch("k3dge.engine.seal_flow.seal_milestone", return_value=(True, "sealed M1")):
                        status, msg = run_seal_flow(ws2, "M1", skip_enter_prompt=True,
                                                    prompter=_Prompt(answers=[]),
                                                    no_version_bump=bump_flag)
            self.assertEqual(status, "sealed")
            from k3dge.engine.version import get_version

            self.assertEqual(get_version(ws2), expected, msg)
            self.assertIn("跳过" if bump_flag else "1.2.4", msg)

    def test_seal_declined_when_operator_says_no(self) -> None:
        ws = _ws()
        _mk_task(ws)
        _clean_report(ws)
        with mock.patch("k3dge.engine.seal_flow.seal_milestone", return_value=(True, "sealed")) as seal:
            status, _ = run_seal_flow(ws, "M1", prompter=_Prompt(answers=["n"]))
        self.assertEqual(status, "seal_declined")
        seal.assert_not_called()

    def test_sealed_when_audit_clean(self) -> None:
        ws = _ws()
        _mk_task(ws)
        _clean_report(ws)
        with _audit_ok(), _record_ok(), \
             mock.patch("k3dge.engine.seal_flow.run_milestone_alignment", return_value=(True, "ok", [])):
            with mock.patch("k3dge.engine.seal_flow.seal_preconditions_error", return_value=None):
                with mock.patch("k3dge.engine.seal_flow.seal_milestone", return_value=(True, "sealed M1")) as seal:
                    status, msg = run_seal_flow(ws, "M1", prompter=_Prompt(answers=["y"]))
        self.assertEqual(status, "sealed")
        seal.assert_called_once()
        # closure note for context compression is written
        self.assertTrue(any(p.name.endswith("-closure.md") for p in (ws / "docs" / "reviews").iterdir()))

    def test_skip_enter_prompt_seals(self) -> None:
        ws = _ws()
        _mk_task(ws)
        _clean_report(ws)
        with _audit_ok(), _record_ok(), \
             mock.patch("k3dge.engine.seal_flow.run_milestone_alignment", return_value=(True, "ok", [])):
            with mock.patch("k3dge.engine.seal_flow.seal_preconditions_error", return_value=None):
                with mock.patch("k3dge.engine.seal_flow.seal_milestone", return_value=(True, "sealed M1")) as seal:
                    status, _ = run_seal_flow(ws, "M1", skip_enter_prompt=True, prompter=_Prompt(answers=[]))
        self.assertEqual(status, "sealed")
        seal.assert_called_once()


class TestSealReviewGate(TestCase):
    def test_audit_report_without_marker_does_not_mask_align(self) -> None:
        """12 列审计稿没有 align-pass marker，不得把「align 已写、清单缺票」误报成无 marker。"""
        from k3dge.engine.seal import _seal_review_gate
        from k3dge.engine.task_index import scan_milestone_tasks

        ws = _ws()
        (ws / "docs" / "tasks").mkdir(parents=True, exist_ok=True)
        (ws / "docs" / "tasks" / "2026-09-01-M1-feat-x.md").write_text(
            "---\nstatus: done\nmilestone: M1\npriority: P2\ndate: 2026-09-01\n---\n\n# X\n",
            encoding="utf-8")
        reviews = ws / "docs" / "reviews"
        reviews.mkdir(parents=True, exist_ok=True)
        (reviews / "2026-09-01-M1-audit.md").write_text("# 审计\n", encoding="utf-8")
        (reviews / "2026-09-01-M1-align.md").write_text(
            "# 对齐\n<!-- k3dge:align-pass:M1 -->\n- [x] `2026-09-01-M1-feat-x.md`\n",
            encoding="utf-8",
        )
        tasks = scan_milestone_tasks(ws, "M1")
        self.assertIsNone(_seal_review_gate(ws, "M1", tasks))

    def test_audit_job_ticket_is_not_work_pending(self) -> None:
        from k3dge.engine.seal import unmet_seal_preconditions
        from k3dge.engine.task_index import is_audit_job_ticket, work_pending, scan_milestone_tasks

        ws = _ws()
        td = ws / "docs" / "tasks"
        td.mkdir(parents=True)
        (td / "2026-09-01-M1-feat-x.done.md").write_text(
            "---\nstatus: done\nmilestone: M1\npriority: P2\ndate: 2026-09-01\n---\n\n# X\n\n## 结案\n- x\n",
            encoding="utf-8")
        (td / "2026-09-01-M1-audit-audit_job_abc.md").write_text(
            "---\nstatus: idea\nmilestone: M1\npriority: P2\ndate: 2026-09-01\n---\n\n# job\n",
            encoding="utf-8")
        self.assertTrue(is_audit_job_ticket("2026-09-01-M1-audit-audit_job_abc.md"))
        tasks = scan_milestone_tasks(ws, "M1")
        self.assertEqual(work_pending(tasks), [])
        unmet = unmet_seal_preconditions(ws, "M1")
        self.assertFalse(any(gid == "tasks_all_done" for gid, _ in unmet))


class TestWriteClosureNote(TestCase):
    def test_records_current_version_and_archived_report(self) -> None:
        from k3dge.engine.seal_flow import _write_closure_note

        ws = _ws()
        (ws / "pyproject.toml").write_text('[project]\nname="x"\nversion="1.2.3"\n', encoding="utf-8")
        arch = ws / "docs" / "reviews" / "archive" / "M1"
        arch.mkdir(parents=True)
        (arch / "2026-09-01-M1-audit.md").write_text("# a\n", encoding="utf-8")
        p = _write_closure_note(ws, "M1")
        text = p.read_text(encoding="utf-8")
        self.assertIn("1.2.3", text)
        self.assertNotIn("1.2.4", text)
        self.assertIn("2026-09-01-M1-audit.md", text)


class TestPrematureArchive(TestCase):
    """M9 实战：任务提前归档 ⇒ align/seal 顶扫不到；提示应可操作（batch archive at seal）。"""

    def _archived_m1(self, ws):
        arch = ws / "docs" / "tasks" / "archive" / "M1"
        arch.mkdir(parents=True)
        (arch / "2026-09-01-M1-feat-x.done.md").write_text(
            "# X\n- **Status**: done\n- **Milestone**: M1\n", encoding="utf-8")

    def test_align_hints_when_milestone_tasks_archived_early(self) -> None:
        ws = _ws()
        self._archived_m1(ws)
        ok, msg, _ = run_milestone_alignment(ws, "M1")
        self.assertFalse(ok)
        self.assertIn("提前归档", msg)
        self.assertIn("batch archive", msg)

    def test_hint_none_for_non_current_milestone(self) -> None:
        from k3dge.engine.task_index import premature_archive_hint

        ws = _ws()
        self._archived_m1(ws)
        self.assertIsNone(premature_archive_hint(ws, "M9"))  # 当前 = M1


class TestClosureNote(TestCase):
    def test_note_records_final_version_and_merged_wording(self) -> None:
        from k3dge.engine import seal_flow

        ws = _ws()
        with mock.patch("k3dge.engine.version.get_version", return_value="0.1.11"):
            p = seal_flow._write_closure_note(ws, "M1")
        text = p.read_text(encoding="utf-8")
        self.assertIn("审计闭环", text)
        self.assertNotIn("双腿", text)
        self.assertIn("0.1.11", text)      # bump 已发生，记当前终版，不再 +1


class TestAuditChecklist(TestCase):
    def test_build_snapshot_flags_suggestion(self) -> None:
        ws = _ws()
        _mk_task(ws)
        data = ac.build_checklist(ws, "M1")
        self.assertTrue(data["audit_suggested"])
        self.assertTrue(any("账齐" in r for r in data["reasons"]))
        self.assertFalse(data["closed"])  # no reports yet
        self.assertEqual(data["verify_attempts"], 0)

    def test_verify_attempt_tracking_and_reset(self) -> None:
        ws = _ws()
        _mk_task(ws)
        ac.reset_verify_attempts(ws)
        self.assertEqual(ac.get_verify_attempts(ws), 0)
        self.assertEqual(ac.bump_verify_attempt(ws), 1)
        self.assertEqual(ac.bump_verify_attempt(ws), 2)
        ac.reset_verify_attempts(ws)
        self.assertEqual(ac.get_verify_attempts(ws), 0)

    def test_reset_for_audit_clears_budget_and_stamps(self) -> None:
        ws = _ws()
        _mk_task(ws)
        ac.bump_verify_attempt(ws)
        ac.bump_verify_attempt(ws)
        self.assertEqual(ac.get_verify_attempts(ws), 2)
        data = ac.reset_for_audit(ws, "M1")
        self.assertEqual(data["verify_attempts"], 0)
        self.assertIsNotNone(data["audit_started_at"])

    def test_persists_to_audit_path(self) -> None:
        ws = _ws()
        _mk_task(ws)
        ac.build_checklist(ws, "M1")
        self.assertTrue((ws / ".agent" / "audit_checklist.json").is_file())


class TestReportTask(TestCase):
    """ADR-0022: one task per report; task-done requires the report 待修==0."""

    def _rep(self, ws, status="待修"):
        (ws / "docs" / "reviews").mkdir(parents=True, exist_ok=True)
        (ws / "docs" / "tasks").mkdir(parents=True, exist_ok=True)
        (ws / "docs" / "reviews" / "x.md").write_text(
            "| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
            f"| A1 | d | s | p | t | desc | loc | {status} | - | - | 待复审 | - |\n",
            encoding="utf-8",
        )

    def test_create_task_records_report(self) -> None:
        ws = _ws()
        self._rep(ws)
        ok, _msg, path = create_task(ws, "fix A1", typ="audit", milestone="M1", report="docs/reviews/x.md")
        self.assertTrue(ok)
        text = path.read_text(encoding="utf-8")
        self.assertIn("report: docs/reviews/x.md", text)
        # 唯一源：正文不得复写 frontmatter 元数据（TASK_BODY_META_REDUNDANT）
        self.assertNotIn("- **Report**:", text)
        self.assertNotIn("- **Status**:", text)

    def test_done_blocked_when_report_open(self) -> None:
        ws = _ws()
        self._rep(ws, "待修")
        _ok, _m, path = create_task(ws, "fix A1", typ="audit", milestone="M1", report="docs/reviews/x.md")
        ok, msg = mark_task_done(ws, path.name)[:2]
        self.assertFalse(ok)
        self.assertIn("A1", msg)

    def test_done_allowed_when_report_clean(self) -> None:
        ws = _ws()
        self._rep(ws, "已修")
        _ok, _m, path = create_task(ws, "fix A1", typ="audit", milestone="M1", report="docs/reviews/x.md")
        ok, _msg = mark_task_done(ws, path.name)[:2]
        self.assertTrue(ok)

    def test_unbound_task_not_gated(self) -> None:
        ws = _ws()
        _ok, _m, path = create_task(ws, "plain task", typ="fix", milestone="M1")
        ok, _msg = mark_task_done(ws, path.name)[:2]
        self.assertTrue(ok)


class TestExternalAuditPersist(TestCase):
    def test_persist_with_header_discoverable(self) -> None:
        ws = _ws()
        path = persist_external_audit_report(ws, "M1", _AUDIT)
        self.assertTrue(path.name.endswith("-M1-external-audit.md"))
        self.assertTrue(path.is_file())
        found = _find_audit_report(ws, "M1")
        self.assertIsNotNone(found)
        self.assertEqual(_parse_audit_stats(found[1])["待修"], 1)

    def test_persist_without_header_canonicalizes(self) -> None:
        ws = _ws()
        # Human pastes rows but no 12-col header; system must still land a parseable report.
        pasted = "| A1 | x | s | p | t | desc | loc | 待修 | - | - | 待复审 | - |"
        path = persist_external_audit_report(ws, "M1", pasted)
        text = path.read_text(encoding="utf-8")
        self.assertIn("ID | 日期", text)  # header was prepended
        found = _find_audit_report(ws, "M1")
        self.assertIsNotNone(found)
        self.assertEqual(_parse_audit_stats(found[1])["待修"], 1)

    def test_latest_submission_overwrites(self) -> None:
        ws = _ws()
        first = persist_external_audit_report(ws, "M1", _AUDIT)
        second = persist_external_audit_report(ws, "M1", _AUDIT.replace("待修", "已修"))
        self.assertEqual(first, second)
        found = _find_audit_report(ws, "M1")
        self.assertEqual(_parse_audit_stats(found[1])["待修"], 0)


class TestRatchetAuditStep(TestCase):
    """G3：审计腿换源棘轮工单（roles.audit.mode=ratchet）。"""

    _RATCHET = '[roles.audit]\nbind = "k3dit"\nmode = "ratchet"\n\n[peers.k3dit]\nenabled = true\n'

    def _ws_r(self):
        ws = _ws()
        (ws / ".agent" / "pipeline.toml").write_text(self._RATCHET, encoding="utf-8")
        return ws

    def _ws_r_git(self, *, report: str = "", baseline: str = ""):
        """真 git 仓（`_baseline_covers` 要看 git 事实）+ 可选的**带签名**报告。

        为什么要真仓：本地账里的"已闭环"不再算数（ADR-0004 §2.1.10）——接受它必须同时满足
        报告在盘上、署名齐、报告基线＝单基线、且单基线覆盖本轮 B。桩掉 git 就没法验其中两条。
        """
        import subprocess

        ws = self._ws_r()
        subprocess.run(["git", "init", "-q"], cwd=ws, capture_output=True)
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit",
                        "-q", "--no-verify", "--allow-empty", "-m", "chore: init"],
                       cwd=ws, capture_output=True)
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ws, capture_output=True,
                              text=True).stdout.strip()
        if report:
            (ws / "docs" / "reviews").mkdir(parents=True, exist_ok=True)
            (ws / "docs" / "reviews" / "M1-audit.md").write_text(
                _AUDIT_CLEAN + f"\n- **审计人**: seat\n- **透镜来源**: k3dit\n"
                f"- **基线**: {baseline or head}\n", encoding="utf-8")
        return ws, head

    def test_mode_detection(self):
        ws = self._ws_r()
        self.assertEqual(_audit_mode(ws), "ratchet")

    def test_default_mode_is_oneshot_not_ratchet(self):
        """钉住默认值：缺 `mode` 键时回落 oneshot。

        与实际配置不一致（本仓与模板都写 ratchet）——改默认值必须是有意识的决定，
        届时本测试与下方 `test_repo_and_template_declare_ratchet` 一同调整。
        """
        self.assertEqual(_audit_mode(_ws()), "oneshot")

    def test_repo_and_template_declare_ratchet(self):
        """生产配置证据：本仓与脚手架模板都显式选 ratchet（oneshot 腿无人选用）。"""
        root = Path(__file__).resolve().parents[3]
        for rel in (".agent/pipeline.toml",
                    "src/k3dge/templates/assets/pipeline.toml.template"):
            text = (root / rel).read_text(encoding="utf-8")
            self.assertIn('mode = "ratchet"', text, f"{rel} 未声明 ratchet")

    def test_ratchet_closed_invokes_zero_peer_actions(self):
        """E1 回归守卫：棘轮闭环后，遗留 oneshot 段不得触达任何 peer 动作。

        实测证据：`run_action` 调用 0 次；checklist 仅被无意义地 bump+reset 各一次。
        若将来删掉 oneshot 段，本测试应仍然通过（行为不变）。
        """
        ws = self._ws_r()
        calls = []
        with mock.patch("k3dge.engine.milestone_audit._ratchet_audit_step",
                        return_value=("closed", "棘轮已闭环")):
            with mock.patch("k3dge.engine.pipeline_runner.run_action",
                            side_effect=lambda *a, **k: calls.append(a)):
                status, _msg = run_audit_flow(ws, "M1", prompter=_Prompt(answers=["y"]))
        self.assertEqual(status, "audited")
        self.assertEqual(calls, [], "ratchet 闭环后不应再调 peer 动作")
        self.assertEqual(_audit_mode(_ws()), "oneshot")

    def test_step_submits_ticket_when_none(self):
        ws = self._ws_r()
        with mock.patch("k3dge.engine.audit_flow.submit_audit",
                        return_value={"ok": True, "job_id": "J-1", "state": "awaiting_audit"}):
            st, msg = _ratchet_audit_step(ws, "M1")
        self.assertEqual(st, "progress")
        self.assertIn("J-1", msg)

    def test_step_waits_on_inflight_and_collects_when_done(self):
        ws = self._ws_r()
        import json as _json

        (ws / ".agent" / "audit_jobs.json").parent.mkdir(exist_ok=True)
        (ws / ".agent" / "audit_jobs.json").write_text(_json.dumps(
            {"jobs": [{"job_id": "J-1", "milestone_id": "M1", "state": "awaiting"}]}), encoding="utf-8")
        with mock.patch("k3dge.engine.audit_flow.peer_status",
                        return_value={"ok": True, "state": "open", "open": ["A-1"]}):
            st, msg = _ratchet_audit_step(ws, "M1")
        assert st == "progress" and "A-1" in msg
        with mock.patch("k3dge.engine.audit_flow.peer_status", return_value={"ok": True, "state": "done"}), \
             mock.patch("k3dge.engine.audit_flow.collect_audit",
                        return_value={"ok": True, "report": "docs/reviews/x.md",
                                      "merge": {"ok": True, "mode": "ff"}, "pending": 0}):
            st, msg = _ratchet_audit_step(ws, "M1")
        assert st == "closed" and "ff" in msg

    def test_collected_incomplete_surfaces_audit_open(self):
        """未尽项报告 collect（待修>0）⇒ open，不谎报 closed。"""
        ws = self._ws_r()
        import json as _json

        (ws / ".agent" / "audit_jobs.json").parent.mkdir(exist_ok=True)
        (ws / ".agent" / "audit_jobs.json").write_text(_json.dumps(
            {"jobs": [{"job_id": "J-1", "milestone_id": "M1", "state": "awaiting"}]}), encoding="utf-8")
        with mock.patch("k3dge.engine.audit_flow.peer_status", return_value={"ok": True, "state": "done"}), \
             mock.patch("k3dge.engine.audit_flow.collect_audit",
                        return_value={"ok": True, "state": "open", "report": "docs/reviews/x.md",
                                      "pending": 2, "merge": {}}):
            st, msg = _ratchet_audit_step(ws, "M1")
        assert st == "open" and "待修 2" in msg

    def test_collected_closes_without_resubmit(self):
        """本轮的已闭环单（报告在盘上 + 署名 + 基线一致 + 覆盖本轮 B）⇒ 接受，不重复建单。"""
        import json as _json

        ws, head = self._ws_r_git(report="signed")
        (ws / ".agent" / "audit_jobs.json").write_text(_json.dumps({"jobs": [
            {"job_id": "J-9", "milestone_id": "M1", "state": "collected", "merge_ok": True,
             "baseline": head, "report": "docs/reviews/M1-audit.md",
             "counts": {"待修": 0}}]}), encoding="utf-8")
        with mock.patch("k3dge.engine.audit_flow.submit_audit", side_effect=AssertionError("不该再建单")):
            st, msg = _ratchet_audit_step(ws, "M1", fresh_baseline=head)
        assert st == "closed" and "M1-audit.md" in msg

    def test_stale_collected_job_is_not_accepted(self):
        """**实测过的洞**（2026-09-20）：本地账里 14 天前的 collected 单 + 旧报告 ⇒ 旧报告充闭环。

        本仓 M10 就是这么被封的（job 基线 `0cb1b42`、其后 60 个提交）。修法＝接受前逐条验
        磁盘+git 事实；陈旧单 ⇒ 不接受 ⇒ 去建**本轮**新单。
        """
        import json as _json

        ws, head = self._ws_r_git(report="signed", baseline="0" * 40)
        old_baseline = subprocess_head = ws  # 占位（下面用 git 造一个更早的基线）
        import subprocess

        first = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ws, capture_output=True,
                               text=True).stdout.strip()
        (ws / "new.txt").write_text("x", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=ws, capture_output=True)
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit",
                        "-q", "--no-verify", "-m", "chore: later"], cwd=ws, capture_output=True)
        fresh = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ws, capture_output=True,
                               text=True).stdout.strip()
        # 报告带旧单的基线（自洽），但旧单基线早于本轮 B ⇒ 是旧内容的审计
        (ws / "docs" / "reviews" / "M1-audit.md").write_text(
            _AUDIT_CLEAN + f"\n- **审计人**: seat\n- **透镜来源**: k3dit\n- **基线**: {first}\n",
            encoding="utf-8")
        (ws / ".agent" / "audit_jobs.json").write_text(_json.dumps({"jobs": [
            {"job_id": "J-old", "milestone_id": "M1", "state": "collected", "merge_ok": True,
             "baseline": first, "report": "docs/reviews/M1-audit.md",
             "counts": {"待修": 0}}]}), encoding="utf-8")
        with mock.patch("k3dge.engine.audit_flow.submit_audit",
                        return_value={"state": "failed", "detail": "透镜不可达"}) as sub:
            st, msg = _ratchet_audit_step(ws, "M1", fresh_baseline=fresh)
        sub.assert_called_once()             # 陈旧 ⇒ 去建新单，而不是接受
        assert st == "stalled"
        assert "旧内容" in msg or "不覆盖本轮基线" in msg or "早于本轮基线" in msg
        assert old_baseline is ws

    def test_rebased_collected_job_covers_landed_head(self):
        """合线 rebase 后 pre-rebase oid 与 HEAD 无祖先关系：有 `landed_head==B` 仍覆盖本轮。

        真跑实测：M10 collect 走 rebase 合线，seal 相位 2 把刚闭环的单判成「旧内容」
        又建新单，新票再挡 `tasks_all_done` —— 封板死锁。
        """
        import json as _json
        import subprocess

        ws, first = self._ws_r_git(report="signed")
        (ws / "later.txt").write_text("y", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=ws, capture_output=True)
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit",
                        "-q", "--no-verify", "-m", "round work M1"], cwd=ws, capture_output=True)
        landed = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ws, capture_output=True,
                                text=True).stdout.strip()
        self.assertNotEqual(first, landed)
        (ws / "docs" / "reviews" / "M1-audit.md").write_text(
            _AUDIT_CLEAN + f"\n- **审计人**: seat\n- **透镜来源**: k3dit\n- **基线**: {first}\n",
            encoding="utf-8")
        (ws / ".agent" / "audit_jobs.json").write_text(_json.dumps({"jobs": [
            {"job_id": "J-rebased", "milestone_id": "M1", "state": "collected", "merge_ok": True,
             "baseline": first, "landed_head": landed, "report": "docs/reviews/M1-audit.md",
             "counts": {"待修": 0}}]}), encoding="utf-8")
        with mock.patch("k3dge.engine.audit_flow.submit_audit",
                        side_effect=AssertionError("合线后不应再建单")):
            st, msg = _ratchet_audit_step(ws, "M1", fresh_baseline=landed)
        assert st == "closed" and "M1-audit.md" in msg
        # 主干再走一步 ⇒ landed_head 不再等于 B，仍拒（与 INC-20260920 同形）
        (ws / "after.txt").write_text("z", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=ws, capture_output=True)
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit",
                        "-q", "--no-verify", "-m", "feat: after audit"], cwd=ws, capture_output=True)
        later = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ws, capture_output=True,
                               text=True).stdout.strip()
        with mock.patch("k3dge.engine.audit_flow.submit_audit",
                        return_value={"state": "failed", "detail": "透镜不可达"}):
            st2, msg2 = _ratchet_audit_step(ws, "M1", fresh_baseline=later)
        assert st2 == "stalled"
        assert "旧内容" in msg2 or "不覆盖本轮基线" in msg2

    def test_mechanical_commits_after_landed_head_still_cover(self):
        """合线后再有 round work / k3dge-process 提交，仍覆盖；feat 则拒。"""
        import json as _json
        import subprocess

        ws, first = self._ws_r_git(report="signed")
        (ws / "docs" / "reviews" / "M1-audit.md").write_text(
            _AUDIT_CLEAN + f"\n- **审计人**: seat\n- **透镜来源**: k3dit\n- **基线**: {first}\n",
            encoding="utf-8")
        subprocess.run(["git", "-c", "user.name=k3dge-process",
                        "-c", "user.email=noreply@k3dge.local",
                        "commit", "-q", "--allow-empty", "--no-verify",
                        "-m", "round work M1"], cwd=ws, capture_output=True)
        landed = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ws,
                                capture_output=True, text=True).stdout.strip()
        subprocess.run(["git", "-c", "user.name=k3dge-process",
                        "-c", "user.email=noreply@k3dge.local",
                        "commit", "-q", "--allow-empty", "--no-verify",
                        "-m", "chore(seal): seal milestone M1"], cwd=ws, capture_output=True)
        fresh = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ws,
                               capture_output=True, text=True).stdout.strip()
        (ws / ".agent" / "audit_jobs.json").write_text(_json.dumps({"jobs": [
            {"job_id": "J-m", "milestone_id": "M1", "state": "collected", "merge_ok": True,
             "baseline": first, "landed_head": landed, "report": "docs/reviews/M1-audit.md",
             "counts": {"待修": 0}}]}), encoding="utf-8")
        with mock.patch("k3dge.engine.audit_flow.submit_audit",
                        side_effect=AssertionError("机械件之后不应再建单")):
            st, _msg = _ratchet_audit_step(ws, "M1", fresh_baseline=fresh)
        assert st == "closed"

    def test_collected_covers_even_with_inflight_false_submit(self):
        """误 submit 的 inflight 不得压过本轮 collected。"""
        import json as _json

        ws, head = self._ws_r_git(report="signed")
        (ws / ".agent" / "audit_jobs.json").write_text(_json.dumps({"jobs": [
            {"job_id": "J-done", "milestone_id": "M1", "state": "collected", "merge_ok": True,
             "baseline": head, "report": "docs/reviews/M1-audit.md", "counts": {"待修": 0}},
            {"job_id": "J-false", "milestone_id": "M1", "state": "awaiting",
             "baseline": head},
        ]}), encoding="utf-8")
        with mock.patch("k3dge.engine.audit_flow.peer_status",
                        side_effect=AssertionError("不该探误建单")):
            st, msg = _ratchet_audit_step(ws, "M1", fresh_baseline=head)
        assert st == "closed" and "M1-audit.md" in msg

    def test_missing_report_file_is_not_accepted(self):
        """账里写路径 ≠ 文件存在（报告可能已归档/删除）⇒ 不接受。"""
        import json as _json

        ws, head = self._ws_r_git()          # 有意不落报告
        (ws / ".agent" / "audit_jobs.json").write_text(_json.dumps({"jobs": [
            {"job_id": "J-9", "milestone_id": "M1", "state": "collected", "merge_ok": True,
             "baseline": head, "report": "docs/reviews/M1-audit.md",
             "counts": {"待修": 0}}]}), encoding="utf-8")
        with mock.patch("k3dge.engine.audit_flow.submit_audit",
                        return_value={"state": "failed", "detail": "透镜不可达"}):
            st, msg = _ratchet_audit_step(ws, "M1", fresh_baseline=head)
        assert st == "stalled"
        assert "不在盘上" in msg

    def test_collected_with_pending_does_not_fake_close(self):
        """collected 报告若 待修>0（未尽项 / 报告已删）⇒ 不得假闭环；应重新建单。"""
        import json as _json

        ws = self._ws_r()
        (ws / ".agent" / "audit_jobs.json").write_text(_json.dumps({"jobs": [
            {"job_id": "J-9", "milestone_id": "M1", "state": "collected", "merge_ok": True,
             "report": "docs/reviews/M1-audit.md", "counts": {"待修": 3}}]}), encoding="utf-8")
        with mock.patch("k3dge.engine.audit_flow.submit_audit",
                        return_value={"ok": True, "job_id": "J-10", "state": "awaiting_audit"}) as m:
            st, msg = _ratchet_audit_step(ws, "M1")
        assert st == "progress" and "J-10" in msg and m.called

    def test_full_flow_ratchet_then_quality(self):
        """审计腿工单闭环（本轮的、有磁盘+git 证据）⇒ audited；`fresh_baseline` 由入口自己取。"""
        import json as _json
        import subprocess

        ws, head = self._ws_r_git(report="signed")
        (ws / ".agent" / "audit_jobs.json").write_text(_json.dumps({"jobs": [
            {"job_id": "J-9", "milestone_id": "M1", "state": "collected", "merge_ok": True,
             "baseline": head, "report": "docs/reviews/M1-audit.md",
             "counts": {"待修": 0}}]}), encoding="utf-8")
        with mock.patch("k3dge.engine.pipeline_runner.run_action", return_value=_OK_MCP):
            status, msg = run_audit_flow(ws, "M1", prompter=_Prompt(answers=["y"]))
        self.assertEqual(status, "audited", msg)
        self.assertEqual(subprocess.run(["git", "rev-parse", "HEAD"], cwd=ws, capture_output=True,
                                        text=True).stdout.strip(), head)

    def test_merge_debt_retries_idempotently(self):
        import json as _j
        import os

        ws = self._ws_r()
        (ws / ".agent" / "audit_jobs.json").write_text(_j.dumps({"jobs": [
            {"job_id": "J-5", "milestone_id": "M1", "state": "collected", "merge_ok": False,
             "report": "r.md"}]}), encoding="utf-8")
        with mock.patch("k3dge.engine.worktree.merge_back", return_value={"ok": False, "mode": "dirty", "message": "m"}):
            st, msg = _ratchet_audit_step(ws, "M1")
        assert st == "stalled"
        with mock.patch("k3dge.engine.worktree.merge_back", return_value={"ok": True, "mode": "ff"}):
            st, msg = _ratchet_audit_step(ws, "M1")
        assert st == "closed" and "重试成功" in msg


class TestSingleAuditReport(TestCase):
    """ADR-0025 合并审计模块：一轮 = 一份 12 列；无独立 quality peer/leg。"""

    def test_single_audit_report_suffices_without_quality(self):
        """ADR-0025：一份 12 列报告闭环即可，无独立 quality 腿。

        走 oneshot 腿（显式声明）。原名下“ratchet_closed”与实际路径不符；
        原写 `audit_jobs.json` 在 oneshot 模式下从不被读（实测 open 次数 0），已删。
        """
        ws = _ws_oneshot()
        (ws / "docs" / "reviews" / "2026-09-01-M1-audit.md").write_text(_AUDIT_CLEAN, encoding="utf-8")
        with mock.patch("k3dge.engine.pipeline_runner.run_action", return_value=_OK_MCP):
            status, msg = run_audit_flow(ws, "M1", prompter=_Prompt(answers=["y"]))
        self.assertEqual(status, "audited")  # 单一审计腿闭环即可，无需 quality 票

    def test_push_present_audit_leg(self):
        from k3dge.engine import audit_flow

        ws = _ws()
        import json as _j

        (ws / ".agent" / "audit_jobs.json").write_text(_j.dumps({"jobs": [
            {"job_id": "J-a", "role": "audit", "milestone_id": "M1", "state": "awaiting"}]}), encoding="utf-8")
        calls = []

        def fake(_ws, ref, *, io=None, timeout_default=60, arguments=None):
            calls.append((ref, arguments.get("job_id")))
            return TransportResult(True, "mcp", "ok")

        with mock.patch("k3dge.engine.worktree.present", return_value=[]), \
             mock.patch("k3dge.engine.audit_flow.run_action", side_effect=fake):
            r = audit_flow.push_present(ws, "M1")
        assert r["ok"] and {c[0] for c in calls} == {"audit.present"}


class TestGateIdDispatch(TestCase):
    """拒绝携带闭集 gate_id → `nextstep.GATE_NEXT` 表驱动派发（票 gate_action_dispatch）。

    锁死的旧病：消费点靠 `"未审计" in msg` 之类的**文案子串**决定下一步，改措辞即静默失效
    （同形前科：A-01 子里程碑 id 误放行）。
    """

    def _sidecar(self, ws) -> dict:
        """侧车形状 `{"next": [...], "primary": ...}` ⇒ 返回**主处理点**卡片。"""
        data = json.loads((ws / ".k3dge" / "next.json").read_text(encoding="utf-8"))
        return data["next"][0] if data.get("next") else data

    def test_audit_flow_rejection_routes_by_gate_id(self) -> None:
        ws = _ws_oneshot()  # 无 12 列报告 ⇒ gate_id=audit_report_missing
        with mock.patch("k3dge.engine.pipeline_runner.run_action", return_value=_OK_MCP):
            status, _ = run_audit_flow(ws, "M1", prompter=_Prompt(answers=["y"]))
        self.assertEqual(status, "rejected")
        self.assertIn("k3dge milestone audit-submit M1", self._sidecar(ws)["fact"])

    def test_declined_fix_routes_by_gate_id(self) -> None:
        ws = _ws_oneshot()
        _open_report(ws)
        with mock.patch("k3dge.engine.pipeline_runner.run_action", return_value=_OK_MCP):
            status, _ = run_audit_flow(ws, "M1", prompter=_Prompt(answers=["n"]))
        self.assertEqual(status, "rejected")
        self.assertIn("转人工干预", self._sidecar(ws)["fact"])

    def test_seal_preconditions_rejection_carries_declared_gate_id(self) -> None:
        from k3dge.engine import gates
        from k3dge.engine.seal import seal_preconditions_error

        ws = _ws()
        _mk_task(ws)
        (ws / "docs" / "guides").mkdir(parents=True)
        (ws / "docs" / "guides" / "g.md").write_text(
            "# G\n<!-- k3dge:guide-stub -->\n", encoding="utf-8")
        (ws / ".agent" / "pipeline.toml").write_text(
            '[checks.seal]\npreconditions = ["guides_filled"]\n', encoding="utf-8")
        err = seal_preconditions_error(ws, "M1")
        self.assertIsInstance(err, gates.Rejection)
        self.assertEqual(err.gate_id, "guides_filled")   # id == 契约里声明的那个
        self.assertIn("Unfilled guide stubs", str(err))   # 仍是 str：既有断言/print 不破

    def test_seal_flow_rejection_is_table_driven(self) -> None:
        ws = _ws()
        _mk_task(ws)
        _clean_report(ws)
        with _audit_ok(), _record_ok(), \
             mock.patch("k3dge.engine.seal_flow.run_milestone_alignment", return_value=(True, "ok", [])):
            with mock.patch(
                "k3dge.engine.seal_flow.seal_preconditions_error",
                return_value=gates.Rejection("tasks_all_done", "票没干完"),
            ):
                with mock.patch("k3dge.engine.seal_flow.seal_milestone", return_value=(True, "sealed")):
                    status, msg = run_seal_flow(ws, "M1", prompter=_Prompt(answers=["y"]))
        self.assertEqual(status, "rejected")
        self.assertIn("票没干完", msg)                    # 原文照登
        self.assertIn("票据未全 done", self._sidecar(ws)["fact"])

    def test_seal_prompt_wording_is_single_sourced(self) -> None:
        """封板那一问的两个投影同一句（票 decision_single_source）。"""
        from k3dge.engine import nextstep

        ws = _ws()
        _mk_task(ws)
        _clean_report(ws)
        out = io.StringIO()
        with _audit_ok(), _record_ok(), \
             mock.patch("k3dge.engine.seal_flow.run_milestone_alignment", return_value=(True, "ok", [])):
            with mock.patch("k3dge.engine.seal_flow.seal_preconditions_error", return_value=None):
                with mock.patch("k3dge.engine.seal_flow.seal_milestone", return_value=(True, "sealed")):
                    status, _ = run_seal_flow(
                        ws, "M1", prompter=_Prompt(out_stream=out, answers=["n"]))
        self.assertEqual(status, "seal_declined")
        self.assertIn(nextstep.question_text("seal_ready", "M1"), out.getvalue())

    def test_audit_open_prompt_wording_is_single_sourced(self) -> None:
        from k3dge.engine import nextstep

        ws = _ws_oneshot()
        _open_report(ws)
        out = io.StringIO()
        with mock.patch("k3dge.engine.pipeline_runner.run_action", return_value=_OK_MCP):
            run_audit_flow(ws, "M1", prompter=_Prompt(out_stream=out, answers=["n"]))
        text = out.getvalue()
        self.assertIn("发现 1 项待修", text)  # prompt 走 question 投影
        self.assertIn(nextstep.question_text("audit_open", "M1", n=1), text)


class TestStagesAreDeclaredNotHardcoded(TestCase):
    """外部步读声明面（`[checks.audit].stages_*`），不再硬编码 action ref。

    病灶：原 `milestone_audit.streams` 写死 `k3dit.actions.audit|verify`，而
    `pipeline.toml` 的 `[pipelines.on_seal_enter/on_pre_seal]` 只有校验没有执行者
    ⇒ AGENTS.md §12 声称的机制不存在（§13 缺"到达"环）。
    """

    def test_executor_reads_declared_stages(self):
        from k3dge.engine import gates

        self.assertEqual(gates.stages(_ws(), "audit", "produce"), ["audit.actions.audit"])
        self.assertEqual(gates.stages(_ws(), "audit", "verify"), ["audit.actions.verify"])
        self.assertEqual(gates.all_stage_refs(_ws()),
                         ["audit.actions.audit", "audit.actions.verify"])

    def test_downstream_can_rebind_stages(self):
        """下游可配（用户裁定）：改声明面 .agent/pipeline.toml 就换实现，只有一处。"""
        from k3dge.engine import gates

        ws = _ws()
        (ws / ".agent" / "pipeline.toml").write_text(
            '[checks.audit]\nstages_produce = ["myauditor.actions.lens"]\nstages_verify = []\n',
            encoding="utf-8")
        self.assertEqual(gates.stages(ws, "audit", "produce"), ["myauditor.actions.lens"])
        self.assertEqual(gates.stages(ws, "audit", "verify"), [])
        self.assertEqual(gates.all_stage_refs(ws), ["myauditor.actions.lens"])

    def test_audit_flow_calls_the_declared_ref(self):
        ws = _ws_oneshot()
        _clean_report(ws)
        (ws / ".agent" / "pipeline.toml").write_text(
            '[checks.audit]\nstages_produce = ["dummy.actions.lens"]\nstages_verify = []\n',
            encoding="utf-8")
        calls = []

        def fake(_ws, ref, *, io=None, timeout_default=60, arguments=None):
            calls.append(ref)
            return TransportResult(True, "mcp", "ok")   # dummy 透镜：真读声明面即可，不是 manual 路径

        with mock.patch("k3dge.engine.pipeline_runner.run_action", side_effect=fake):
            status, _ = run_audit_flow(ws, "M1", prompter=_Prompt(answers=["y"]))
        self.assertEqual(status, "audited")
        self.assertIn("dummy.actions.lens", calls)          # 真读了声明
        self.assertNotIn("k3dit.actions.audit", calls)      # 没有硬编码兜底
        self.assertEqual([c for c in calls if c.endswith("actions.verify")], [])  # verify 声明为空 ⇒ 跳过

    def test_no_pipelines_section_left_in_repo_config(self):
        """声明面唯一：仓内配置不得再有 `[pipelines.*]` 段（注释里提历史不算）。"""
        root = Path(__file__).resolve().parents[3]
        for rel in (".agent/pipeline.toml",
                    "src/k3dge/templates/assets/pipeline.toml.template"):
            lines = (root / rel).read_text(encoding="utf-8").splitlines()
            sections = [ln.strip() for ln in lines if ln.strip().startswith("[pipelines.")]
            self.assertEqual(sections, [], f"{rel} 仍有已废段：{sections}")


class TestAuditNoNoop(TestCase):
    """ADR-0004 §2.1.11：先判"这一跳是否真跑过"，再谈报告在不在。

    回归的洞：传输层把 skip 与 manual 都报 `ok=True`，而 `run_audit_flow` 只看
    `_find_report` ⇒ 仓里一份**旧报告**就能把"什么都没跑"兜成闭环（M10 实测过）。
    """

    def _refused(self, produced, answers=("y",)):
        ws = _ws_oneshot()
        _clean_report(ws)  # 旧报告在场——这正是旧代码会误判闭环的条件
        with mock.patch("k3dge.engine.pipeline_runner.run_action", return_value=produced):
            return ws, run_audit_flow(ws, "M1", prompter=_Prompt(answers=list(answers)))

    def test_skip_not_closed_even_with_stale_report(self) -> None:
        ws, (status, msg) = self._refused(TransportResult(True, "skip", "skipped", skipped=True))
        self.assertEqual(status, "refused")
        self.assertIn("skip", msg)
        from k3dge.engine.audit_flow import audit_result_of
        self.assertEqual(audit_result_of(status), "refused")

    def test_transport_failure_not_closed_even_with_stale_report(self) -> None:
        _ws, (status, _msg) = self._refused(TransportResult(False, "mcp", "boom"))
        self.assertEqual(status, "refused")

    def test_manual_first_transport_is_also_degraded(self) -> None:
        """🅰2：判"有没有独立透镜"（事实），不判"链里排第几"。manual 在**首选位**时
        `downgrades` 为空，但结果仍须记 `degraded-manual` 且报告须署名——否则
        "把 manual 排第一"就成了绕开署名要求、且 trailer 记成 `closed`（高估）的路。
        """
        from k3dge.engine.audit_flow import audit_call_result

        self.assertEqual(audit_call_result(TransportResult(True, "manual", "ok")), "degraded-manual")
        self.assertEqual(audit_call_result(_OK_MCP), "closed")
        # 端到端：manual 首选 + 无署名报告 ⇒ 拒
        ws = _ws_oneshot()
        _clean_report(ws)                      # _AUDIT_CLEAN 不含署名
        with mock.patch("k3dge.engine.pipeline_runner.run_action", return_value=_OK_MANUAL):
            status, msg = run_audit_flow(ws, "M1", prompter=_Prompt(answers=["y"]))
        self.assertEqual(status, "refused")
        self.assertIn("署名", msg)

    def test_downgraded_needs_signature(self) -> None:
        ws = _ws_oneshot()
        _clean_report(ws)  # 无署名（_AUDIT_CLEAN 不含 _SIGNS）
        prod = TransportResult(True, "manual", "ok", downgrades=["mcp→manual"])
        with mock.patch("k3dge.engine.pipeline_runner.run_action", return_value=prod):
            status, msg = run_audit_flow(ws, "M1", prompter=_Prompt(answers=["y"]))
        self.assertEqual(status, "refused")
        self.assertIn("署名", msg)

    def test_downgraded_and_signed_is_degraded_manual(self) -> None:
        ws = _ws_oneshot()
        _clean_report(ws)
        p = ws / "docs" / "reviews" / "2026-09-01-M1-audit.md"
        p.write_text(p.read_text(encoding="utf-8") + _SIGNS, encoding="utf-8")
        prod = TransportResult(True, "manual", "ok", downgrades=["mcp→manual"])
        with mock.patch("k3dge.engine.pipeline_runner.run_action", return_value=prod):
            status, msg = run_audit_flow(ws, "M1", prompter=_Prompt(answers=["y"]))
        self.assertEqual(status, "audited_degraded")
        from k3dge.engine.audit_flow import SEALABLE_AUDIT_RESULTS, audit_result_of
        self.assertEqual(audit_result_of(status), "degraded-manual")
        self.assertIn("degraded-manual", SEALABLE_AUDIT_RESULTS)
        self.assertIn("降级", msg)

    def test_empty_stage_declaration_is_refused(self) -> None:
        """配置层的同一个洞：`stages_produce` 留空 ⇒ 一次都没跑，**不得**因旧报告判闭环。"""
        ws = _ws_oneshot()
        _clean_report(ws)
        (ws / ".agent" / "pipeline.toml").write_text(
            '[roles.audit]\nbind = "k3dit"\nmode = "oneshot"\n'
            "[checks.audit]\nstages_produce = []\nstages_verify = []\n",
            encoding="utf-8",
        )
        status, msg = run_audit_flow(ws, "M1", prompter=_Prompt(answers=["y"]))
        self.assertEqual(status, "refused")
        self.assertIn("stages_produce", msg)

    def test_skip_does_not_advance_but_closed_does(self) -> None:
        """闭集纪律：只有 closed / degraded-manual 允许推进版号。"""
        from k3dge.engine.audit_flow import AUDIT_RESULTS, SEALABLE_AUDIT_RESULTS, audit_result_of
        self.assertEqual(AUDIT_RESULTS, ("closed", "degraded-manual", "escalated", "refused"))
        self.assertEqual(SEALABLE_AUDIT_RESULTS, ("closed", "degraded-manual"))
        self.assertIsNone(audit_result_of("ratchet_open"))   # in-flight：未正常返回 ⇒ 不推进
        self.assertIsNone(audit_result_of("audit_open"))
        self.assertNotIn("refused", SEALABLE_AUDIT_RESULTS)
