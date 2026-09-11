"""Tests for the seal-flow state machine and peer-action runner."""

from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path
from unittest import TestCase, mock

from k3dge.engine import milestone as ms
from k3dge.engine import audit_checklist as ac
from k3dge.engine.pipeline_runner import (
    TransportResult,
    load_pipeline_config,
    resolve_action,
    run_action,
)

_OK_MANUAL = TransportResult(True, "manual", "ok")


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


_AUDIT = (
    "| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |\n"
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
    "| A1 | x | s | p | t | desc1 | loc | 待修 | - | - | 待复审 | - |\n"
    "| A2 | x | s | p | t | desc2 | loc | 有意留 | - | - | 通过 | - |\n"
    "| A3 | x | s | p | t | desc3 | loc | 已修 | - | - | 通过 | - |\n"
)


class TestAuditStats(TestCase):
    def test_parse_counts(self) -> None:
        stats = ms._parse_audit_stats(_AUDIT)
        self.assertEqual(stats["待修"], 1)
        self.assertEqual(stats["有意留"], 1)
        self.assertEqual(stats["已修"], 1)
        self.assertEqual(stats["total"], 3)

    def test_find_report(self) -> None:
        ws = _ws()
        p = ws / "docs" / "reviews" / "2026-09-01-M1-x.md"
        p.write_text(_AUDIT, encoding="utf-8")
        found = ms._find_audit_report(ws, "M1")
        self.assertIsNotNone(found)
        self.assertEqual(found[0], p)

    def test_ensure_leftovers(self) -> None:
        ws = _ws()
        p = ws / "docs" / "reviews" / "2026-09-01-M1-x.md"
        p.write_text(_AUDIT, encoding="utf-8")
        ms._ensure_leftovers(ws, _AUDIT, p)
        leftover = (ws / "docs" / "reviews" / "LEFTOVERS.md").read_text(encoding="utf-8")
        self.assertIn("A2", leftover)
        self.assertIn("有意留", leftover)


class TestPrompt(TestCase):
    def test_injected_answers(self) -> None:
        pr = ms._Prompt(answers=["y", "n"])
        self.assertTrue(pr.ask("enter?", default_yes=False))
        self.assertFalse(pr.ask("fix?", default_yes=True))

    def test_non_interactive_defaults(self) -> None:
        pr = ms._Prompt(in_stream=io.StringIO(""), out_stream=io.StringIO())
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
        ws = _ws()
        _clean_report(ws)
        calls = []

        def fake(_ws, ref, *, io=None, timeout_default=60, arguments=None):
            calls.append((ref, arguments or {}))
            return TransportResult(True, "mcp", "ok")

        with mock.patch("k3dge.engine.pipeline_runner.run_action", side_effect=fake):
            status, _ = ms.run_audit_flow(ws, "M1", prompter=ms._Prompt(answers=["y"]))
        self.assertEqual(status, "audited")
        produce = {r: a for r, a in calls if r.endswith(("actions.audit", "actions.quality"))}
        self.assertIn("k3dit.actions.audit", produce)
        self.assertNotIn("pass_number", produce["k3dit.actions.audit"])  # never leaks k3dit internals
        self.assertIn("M1", produce["k3dit.actions.audit"].get("target_scope", ""))
        self.assertEqual(produce["k3dit.actions.audit"].get("milestone_id"), "M1")
        verify = {r: a for r, a in calls if r.endswith("actions.verify")}
        self.assertIn("k3dit.actions.verify", verify)
        self.assertTrue(str(verify["k3dit.actions.verify"].get("path", "")).endswith(".md"))

    def test_rejection_quotes_the_peer_suggested_report_path(self) -> None:
        ws = _ws()  # no report on disk
        payload = json.dumps({"ok": True, "lens_count": 5, "report_path": "docs/reviews/2026-09-03-M1-code.md"})
        with mock.patch(
            "k3dge.engine.pipeline_runner.run_action",
            return_value=TransportResult(True, "mcp", "ok", payload=payload),
        ):
            status, msg = ms.run_audit_flow(ws, "M1", prompter=ms._Prompt(answers=["y"]))
        self.assertEqual(status, "rejected")
        self.assertIn("docs/reviews/2026-09-03-M1-code.md", msg)
        self.assertIn("k3dge 不代笔正文", msg)

    def test_audited_when_clean(self) -> None:
        ws = _ws()
        _clean_report(ws)
        with mock.patch("k3dge.engine.pipeline_runner.run_action", return_value=_OK_MANUAL):
            status, _ = ms.run_audit_flow(ws, "M1", prompter=ms._Prompt(answers=["y"]))
        self.assertEqual(status, "audited")

    def test_rejected_when_audit_missing(self) -> None:
        ws = _ws()  # no report
        with mock.patch("k3dge.engine.pipeline_runner.run_action", return_value=_OK_MANUAL):
            status, _ = ms.run_audit_flow(ws, "M1", prompter=ms._Prompt(answers=["y"]))
        self.assertEqual(status, "rejected")

    def test_declined_fix_rejects(self) -> None:
        ws = _ws()
        _open_report(ws)
        with mock.patch("k3dge.engine.pipeline_runner.run_action", return_value=_OK_MANUAL):
            status, _ = ms.run_audit_flow(ws, "M1", prompter=ms._Prompt(answers=["n"]))
        self.assertEqual(status, "rejected")

    def test_escalates_after_max_verify_attempts(self) -> None:
        ws = _ws()
        _open_report(ws)
        with mock.patch("k3dge.engine.pipeline_runner.run_action", return_value=_OK_MANUAL):
            # three fix-yes answers -> 4th loop escalates (max=3)
            status, _ = ms.run_audit_flow(
                ws, "M1", prompter=ms._Prompt(answers=["y", "y", "y"]), max_verify_attempts=3
            )
        self.assertEqual(status, "escalated")


class TestSealFlow(TestCase):
    def test_seal_requires_closed_audit(self) -> None:
        ws = _ws()
        _mk_task(ws)  # no report -> audit not closed
        with mock.patch.object(ms, "seal_milestone", return_value=(True, "sealed")) as seal:
            status, _ = ms.run_seal_flow(ws, "M1", prompter=ms._Prompt(answers=["y"]))
        self.assertEqual(status, "audit_needed")
        seal.assert_not_called()

    def test_deferred_when_operator_says_no(self) -> None:
        ws = _ws()
        _mk_task(ws)
        _clean_report(ws)
        with mock.patch.object(ms, "seal_milestone", return_value=(True, "sealed")) as seal:
            status, _ = ms.run_seal_flow(ws, "M1", prompter=ms._Prompt(answers=["n"]))
        self.assertEqual(status, "deferred")
        seal.assert_not_called()

    def test_sealed_when_audit_clean(self) -> None:
        ws = _ws()
        _mk_task(ws)
        _clean_report(ws)
        with mock.patch.object(ms, "run_milestone_alignment", return_value=(True, "ok", [])):
            with mock.patch.object(ms, "seal_milestone", return_value=(True, "sealed M1")) as seal:
                status, msg = ms.run_seal_flow(ws, "M1", prompter=ms._Prompt(answers=["y"]))
        self.assertEqual(status, "sealed")
        seal.assert_called_once()
        # closure note for context compression is written
        self.assertTrue(any(p.name.endswith("-closure.md") for p in (ws / "docs" / "reviews").iterdir()))

    def test_skip_enter_prompt_seals(self) -> None:
        ws = _ws()
        _mk_task(ws)
        _clean_report(ws)
        with mock.patch.object(ms, "run_milestone_alignment", return_value=(True, "ok", [])):
            with mock.patch.object(ms, "seal_milestone", return_value=(True, "sealed M1")) as seal:
                status, _ = ms.run_seal_flow(ws, "M1", skip_enter_prompt=True, prompter=ms._Prompt(answers=[]))
        self.assertEqual(status, "sealed")
        seal.assert_called_once()


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
        ok, _msg, path = ms.create_task(ws, "fix A1", typ="audit", milestone="M1", report="docs/reviews/x.md")
        self.assertTrue(ok)
        text = path.read_text(encoding="utf-8")
        self.assertIn("report: docs/reviews/x.md", text)
        self.assertIn("- **Report**:", text)

    def test_done_blocked_when_report_open(self) -> None:
        ws = _ws()
        self._rep(ws, "待修")
        _ok, _m, path = ms.create_task(ws, "fix A1", typ="audit", milestone="M1", report="docs/reviews/x.md")
        ok, msg = ms.mark_task_done(ws, path.name)[:2]
        self.assertFalse(ok)
        self.assertIn("A1", msg)

    def test_done_allowed_when_report_clean(self) -> None:
        ws = _ws()
        self._rep(ws, "已修")
        _ok, _m, path = ms.create_task(ws, "fix A1", typ="audit", milestone="M1", report="docs/reviews/x.md")
        ok, _msg = ms.mark_task_done(ws, path.name)[:2]
        self.assertTrue(ok)

    def test_unbound_task_not_gated(self) -> None:
        ws = _ws()
        _ok, _m, path = ms.create_task(ws, "plain task", typ="fix", milestone="M1")
        ok, _msg = ms.mark_task_done(ws, path.name)[:2]
        self.assertTrue(ok)


class TestExternalAuditPersist(TestCase):
    def test_persist_with_header_discoverable(self) -> None:
        ws = _ws()
        path = ms.persist_external_audit_report(ws, "M1", _AUDIT)
        self.assertTrue(path.name.endswith("-M1-external-audit.md"))
        self.assertTrue(path.is_file())
        found = ms._find_audit_report(ws, "M1")
        self.assertIsNotNone(found)
        self.assertEqual(ms._parse_audit_stats(found[1])["待修"], 1)

    def test_persist_without_header_canonicalizes(self) -> None:
        ws = _ws()
        # Human pastes rows but no 12-col header; system must still land a parseable report.
        pasted = "| A1 | x | s | p | t | desc | loc | 待修 | - | - | 待复审 | - |"
        path = ms.persist_external_audit_report(ws, "M1", pasted)
        text = path.read_text(encoding="utf-8")
        self.assertIn("ID | 日期", text)  # header was prepended
        found = ms._find_audit_report(ws, "M1")
        self.assertIsNotNone(found)
        self.assertEqual(ms._parse_audit_stats(found[1])["待修"], 1)

    def test_latest_submission_overwrites(self) -> None:
        ws = _ws()
        first = ms.persist_external_audit_report(ws, "M1", _AUDIT)
        second = ms.persist_external_audit_report(ws, "M1", _AUDIT.replace("待修", "已修"))
        self.assertEqual(first, second)
        found = ms._find_audit_report(ws, "M1")
        self.assertEqual(ms._parse_audit_stats(found[1])["待修"], 0)


class TestDocAudit(TestCase):
    def test_clean_when_no_docs(self) -> None:
        ws = _ws()
        with mock.patch.object(ms, "_changed_docs", return_value=[]):
            status, _ = ms.run_doc_audit(ws, io=io.StringIO())
        self.assertEqual(status, "clean")

    def test_creates_one_milestone_task(self) -> None:
        ws = _ws()
        created = Path("docs/tasks/2026-09-02-M1-audit-doc-audit.md")
        with mock.patch.object(ms, "_changed_docs", return_value=["docs/guides/a.md"]), \
             mock.patch("k3dge.engine.pipeline_runner.run_action", return_value=_OK_MANUAL), \
             mock.patch.object(ms, "scan_milestone_tasks", return_value=[]), \
             mock.patch.object(ms, "create_task", return_value=(True, "ok", created)) as ct:
            status, _ = ms.run_doc_audit(ws, io=io.StringIO())
        self.assertEqual(status, "reported")
        ct.assert_called_once()
        # milestone-scoped, non-blocking
        self.assertEqual(ct.call_args.kwargs.get("milestone"), "M1")

    def test_idempotent_when_open_task_exists(self) -> None:
        ws = _ws()
        existing = mock.Mock(path=Path("docs/tasks/x-audit-doc-audit.done.md"), status="done")
        open_task = mock.Mock(path=Path("docs/tasks/y-audit-doc-audit.md"), status="in-progress")
        with mock.patch.object(ms, "_changed_docs", return_value=["docs/guides/a.md"]), \
             mock.patch("k3dge.engine.pipeline_runner.run_action", return_value=_OK_MANUAL), \
             mock.patch.object(ms, "scan_milestone_tasks", return_value=[existing, open_task]), \
             mock.patch.object(ms, "create_task") as ct:
            status, _ = ms.run_doc_audit(ws, io=io.StringIO())
        self.assertEqual(status, "reported")
        ct.assert_not_called()  # one task per milestone, not per finding



class TestRatchetAuditStep(TestCase):
    """G3：审计腿换源棘轮工单（roles.audit.mode=ratchet）。"""

    _RATCHET = '[roles.audit]\nbind = "k3dit"\nmode = "ratchet"\n\n[peers.k3dit]\nenabled = true\n'

    def _ws_r(self):
        ws = _ws()
        (ws / ".agent" / "pipeline.toml").write_text(self._RATCHET, encoding="utf-8")
        return ws

    def test_mode_detection(self):
        ws = self._ws_r()
        self.assertEqual(ms._audit_mode(ws), "ratchet")
        self.assertEqual(ms._audit_mode(_ws()), "scaffold")

    def test_step_submits_ticket_when_none(self):
        ws = self._ws_r()
        with mock.patch("k3dge.engine.audit_flow.submit_audit",
                        return_value={"ok": True, "job_id": "J-1", "state": "awaiting_audit"}):
            st, msg = ms._ratchet_audit_step(ws, "M1")
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
            st, msg = ms._ratchet_audit_step(ws, "M1")
        assert st == "progress" and "A-1" in msg
        with mock.patch("k3dge.engine.audit_flow.peer_status", return_value={"ok": True, "state": "done"}), \
             mock.patch("k3dge.engine.audit_flow.collect_audit",
                        return_value={"ok": True, "report": "docs/reviews/x.md",
                                      "merge": {"ok": True, "mode": "ff"}, "pending": 0}):
            st, msg = ms._ratchet_audit_step(ws, "M1")
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
            st, msg = ms._ratchet_audit_step(ws, "M1")
        assert st == "open" and "待修 2" in msg

    def test_collected_closes_without_resubmit(self):
        import json as _json

        ws = self._ws_r()
        (ws / ".agent" / "audit_jobs.json").write_text(_json.dumps({"jobs": [
            {"job_id": "J-9", "milestone_id": "M1", "state": "collected", "merge_ok": True,
             "report": "docs/reviews/M1-audit.md", "counts": {"待修": 0}}]}), encoding="utf-8")
        with mock.patch("k3dge.engine.audit_flow.submit_audit", side_effect=AssertionError("不该再建单")):
            st, msg = ms._ratchet_audit_step(ws, "M1")
        assert st == "closed" and "M1-audit.md" in msg

    def test_full_flow_ratchet_then_quality(self):
        """审计腿工单闭环后只剩 quality 腿；两腿皆净 ⇒ audited。"""
        import json as _json

        ws = self._ws_r()
        (ws / ".agent" / "audit_jobs.json").write_text(_json.dumps({"jobs": [
            {"job_id": "J-9", "milestone_id": "M1", "state": "collected", "merge_ok": True,
             "report": "docs/reviews/M1-audit.md", "counts": {"待修": 0}}]}), encoding="utf-8")
        _clean_report(ws)
        with mock.patch("k3dge.engine.pipeline_runner.run_action", return_value=_OK_MANUAL):
            status, msg = ms.run_audit_flow(ws, "M1", prompter=ms._Prompt(answers=["y"]))
        self.assertEqual(status, "audited")

    def test_merge_debt_retries_idempotently(self):
        import json as _j
        import os

        ws = self._ws_r()
        (ws / ".agent" / "audit_jobs.json").write_text(_j.dumps({"jobs": [
            {"job_id": "J-5", "milestone_id": "M1", "state": "collected", "merge_ok": False,
             "report": "r.md"}]}), encoding="utf-8")
        with mock.patch("k3dge.engine.worktree.merge_back", return_value={"ok": False, "mode": "dirty", "message": "m"}):
            st, msg = ms._ratchet_audit_step(ws, "M1")
        assert st == "stalled"
        with mock.patch("k3dge.engine.worktree.merge_back", return_value={"ok": True, "mode": "ff"}):
            st, msg = ms._ratchet_audit_step(ws, "M1")
        assert st == "closed" and "重试成功" in msg


class TestSingleAuditReport(TestCase):
    """ADR-0025 合并审计模块：一轮 = 一份 12 列；无独立 quality peer/leg。"""

    def test_audit_ratchet_closed_is_audited_without_quality(self):
        import json as _j

        ws = _ws()
        (ws / ".agent" / "audit_jobs.json").parent.mkdir(exist_ok=True)
        (ws / ".agent" / "audit_jobs.json").write_text(_j.dumps({"jobs": [
            {"job_id": "A-1", "role": "audit", "milestone_id": "M1", "state": "collected",
             "merge_ok": True, "report": "r.md", "counts": {"待修": 0}}]}), encoding="utf-8")
        (ws / "docs" / "reviews" / "2026-09-01-M1-audit.md").write_text(_AUDIT_CLEAN, encoding="utf-8")
        with mock.patch("k3dge.engine.pipeline_runner.run_action", return_value=_OK_MANUAL):
            status, msg = ms.run_audit_flow(ws, "M1", prompter=ms._Prompt(answers=["y"]))
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
