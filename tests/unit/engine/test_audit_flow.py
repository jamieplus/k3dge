"""整链（桩子先行）：submit → 协议外等待 → collect → 验壳 → 落盘 → 数计数。

无任何真实 peer：`.mcp.json` 把角色 `audit` 绑到 `tests/fixtures/dummy_peer.py`。
同一份契约下，真实 harness 只换绑定、k3dge 一行不改。
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from k3dge.engine.audit_flow import STATE_REL, collect_audit, submit_audit

DUMMY = str(Path(__file__).resolve().parents[2] / "fixtures" / "dummy_peer.py")

PIPELINE = """
[roles.audit]
bind = "dummy"

[peers.dummy.actions.submit]
transports = [ { provider = "mcp", tool = "dummy_submit", timeout = 60 } ]

[peers.dummy.actions.collect]
transports = [ { provider = "mcp", tool = "dummy_collect", timeout = 60 } ]
"""


def _mk_ws(root: Path, pending: str) -> None:
    (root / ".agent").mkdir(parents=True)
    (root / "src").mkdir()
    (root / "src" / "mod.py").write_text("def f() -> int:\n    return 1\n", encoding="utf-8")
    (root / ".agent" / "pipeline.toml").write_text(PIPELINE, encoding="utf-8")
    (root / ".mcp.json").write_text(json.dumps({
        "mcpServers": {
            "dummy": {
                "command": sys.executable,
                "args": [DUMMY],
                "env": {"DUMMY_PENDING": pending},
            }
        }
    }), encoding="utf-8")


def _set_pending(root: Path, pending: str) -> None:
    cfg = json.loads((root / ".mcp.json").read_text(encoding="utf-8"))
    cfg["mcpServers"]["dummy"]["env"]["DUMMY_PENDING"] = pending
    (root / ".mcp.json").write_text(json.dumps(cfg), encoding="utf-8")


class TestAuditFlowSkeleton(unittest.TestCase):
    def test_full_chain_open_then_closed(self) -> None:
        with TemporaryDirectory() as d:
            ws = Path(d)
            _mk_ws(ws, "2")

            r1 = submit_audit(ws, "M1", targets=["src"])
            self.assertEqual(r1["state"], "awaiting_audit", r1)
            self.assertTrue(r1["job_id"])
            self.assertTrue((ws / STATE_REL).is_file())

            # 第一次收：待修=2 → 闭环未成
            r2 = collect_audit(ws, "M1")
            self.assertEqual(r2["state"], "open", r2)
            self.assertEqual(r2["pending"], 2)
            self.assertTrue(r2["baseline_ok"])
            report = ws / r2["report"]
            self.assertTrue(report.is_file())
            self.assertIn("待修", report.read_text(encoding="utf-8"))
            self.assertIn("dummy+test-seat", r2["seat"])  # 出处字段由对端填、k3dge 只搬运

            # 「修复」后重审：换环境（新包 ⇒ 新基线）→ 待修=0 → 闭环
            _set_pending(ws, "0")
            r3 = submit_audit(ws, "M1", targets=["src"])
            self.assertEqual(r3["state"], "awaiting_audit", r3)
            r4 = collect_audit(ws, "M1")
            self.assertEqual(r4["state"], "closed", r4)
            self.assertEqual(r4["pending"], 0)

    def test_baseline_mismatch_is_rejected_not_swallowed(self) -> None:
        with TemporaryDirectory() as d:
            ws = Path(d)
            _mk_ws(ws, "0")
            submit_audit(ws, "M1", targets=["src"])
            # 篡改编排状态里的基线（模拟报告与送检包脱钩）
            state = json.loads((ws / STATE_REL).read_text(encoding="utf-8"))
            state["jobs"][-1]["bundle_hash"] = "sha256:" + "0" * 64
            (ws / STATE_REL).write_text(json.dumps(state), encoding="utf-8")
            r = collect_audit(ws, "M1")
            self.assertEqual(r["state"], "failed")
            self.assertEqual(r["error"], "FORMAT")
            self.assertIn("baseline", r["detail"])

    def test_collect_without_submit_says_so(self) -> None:
        with TemporaryDirectory() as d:
            ws = Path(d)
            _mk_ws(ws, "0")
            r = collect_audit(ws, "M1")
            self.assertEqual(r["state"], "awaiting_audit")
            self.assertIn("submit first", r["detail"])


if __name__ == "__main__":
    unittest.main()


def test_open_ratchet_jobs_filters_closed(tmp_path):
    """G2：路由只认本地账；collected/failed 不算在办。"""
    from k3dge.engine import audit_flow

    (tmp_path / ".agent").mkdir()
    import json

    (tmp_path / ".agent" / "audit_jobs.json").write_text(json.dumps({"jobs": [
        {"job_id": "J-1", "state": "collected"},
        {"job_id": "J-2", "state": "awaiting_audit", "milestone_id": "M9"},
        {"job_id": "J-3", "state": "failed"},
    ]}), encoding="utf-8")
    opens = audit_flow.open_ratchet_jobs(tmp_path)
    assert [j["job_id"] for j in opens] == ["J-2"]


def test_nextstep_has_ratchet_open():
    from k3dge.engine.nextstep import STATE_OPTIONS

    assert "ratchet_open" in STATE_OPTIONS and "§1.4" in STATE_OPTIONS["ratchet_open"]["if_y"]


def test_peer_status_no_peer_is_graceful(tmp_path):
    from k3dge.engine import audit_flow

    (tmp_path / ".agent").mkdir()
    r = audit_flow.peer_status(tmp_path, "J-x")
    assert r["ok"] is False and r["state"] == "unknown" and "message" in r


def test_push_present_no_job_graceful(tmp_path):
    from k3dge.engine import audit_flow

    (tmp_path / ".agent").mkdir()
    r = audit_flow.push_present(tmp_path, "no-such-key")
    assert r["ok"] is False and "skipped" in r


def test_collect_role_naming_and_kind_guard(tmp_path):
    """首夜事故回归：两腿各归各文件；案卷区被**无标记草稿**占位 ⇒ 拒落不覆盖。"""
    import datetime
    import json as _j
    from unittest import mock

    from k3dge.engine import audit_flow

    (tmp_path / ".agent").mkdir()
    (tmp_path / "docs" / "reviews").mkdir(parents=True)
    today = datetime.date.today().isoformat()
    draft = tmp_path / "docs" / "reviews" / f"{today}-M9-quality.md"
    draft.write_text("# k3lity 质量报告（94 条草稿，无 kind 标记）\n", encoding="utf-8")
    hdr = (
        "| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n")
    (tmp_path / ".agent" / "audit_jobs.json").write_text(_j.dumps({"jobs": [
        {"job_id": "J-q", "role": "quality", "milestone_id": "M9", "state": "awaiting",
         "bundle_hash": "sha256:mine", "ticket_task": None}]}), encoding="utf-8")

    class _R:
        ok, detail, downgrades, payload = True, "", [], ""

    env = {"ok": True, "kind": "report",
           "payload": {"report_markdown": "<!-- k3dge:kind: quality -->\n# 质量签署件\n\n" + hdr +
                         "| Q-1 | 2026-09-04 | 低 | P3 | 复杂度 | d | f.py:1 | 有意留 | 有意留 | e | 通过 | seat |\n"},
           "provenance": {"seat": "s", "baseline": "sha256:mine"}}
    with mock.patch.object(audit_flow, "run_action", return_value=_R()), \
         mock.patch.object(audit_flow, "_parse_envelope", return_value=env):
        r = audit_flow.collect_audit(tmp_path, "M9")
    assert r.get("ok") is False and "跨类" in r["message"]
    assert "草稿" in draft.read_text(encoding="utf-8")   # 原文件未动（拒覆盖）
    # 审计腿命名各走各的，不撞
    (tmp_path / ".agent" / "audit_jobs.json").write_text(_j.dumps({"jobs": [
        {"job_id": "J-a", "role": "audit", "milestone_id": "M9", "state": "awaiting",
         "bundle_hash": "sha256:mine", "ticket_task": None}]}), encoding="utf-8")
    env2 = {"ok": True, "kind": "report",
            "payload": {"report_markdown": "# 审计签署件\n\n" + hdr +
                      "| A-1 | 2026-09-04 | 低 | P3 | 缺陷 | d | f.py:1 | 已修 | 已修 | e | 通过 | seat |\n"},
            "provenance": {"seat": "s", "baseline": "sha256:mine"}}
    with mock.patch.object(audit_flow, "run_action", return_value=_R()), \
         mock.patch.object(audit_flow, "_parse_envelope", return_value=env2):
        r2 = audit_flow.collect_audit(tmp_path, "M9")
    assert r2.get("ok") and r2["report"].endswith("-audit.md") and (tmp_path / r2["report"]).is_file()


def test_prune_sweeps_tmp_shells(tmp_path):
    """弹壳区：seal 的 prune 顺手清空 tmp/（README 区规除外）。"""
    import json as _j

    from k3dge.engine import audit_flow

    (tmp_path / ".agent").mkdir()
    (tmp_path / "tmp").mkdir()
    (tmp_path / "tmp" / "README.md").write_text("区规", encoding="utf-8")
    (tmp_path / "tmp" / "apply_x.py").write_text("x", encoding="utf-8")
    (tmp_path / ".agent" / "audit_jobs.json").write_text(_j.dumps({"jobs": []}), encoding="utf-8")
    r = audit_flow.prune_finished(tmp_path)
    assert r["tmp_swept"] == 1 and (tmp_path / "tmp" / "README.md").exists()
    assert not (tmp_path / "tmp" / "apply_x.py").exists()
