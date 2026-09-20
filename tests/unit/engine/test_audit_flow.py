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
    import subprocess

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
    # 审计线模型：消费仓必须是 git 仓且有提交（线从 HEAD 拉起，L=送检基线）
    subprocess.run(["git", "init", "-qb", "main", str(root)], check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "seed"],
                   cwd=root, check=True, capture_output=True)


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
            # 篡改编排状态里的基线（模拟报告与审计线锁点脱钩）
            state = json.loads((ws / STATE_REL).read_text(encoding="utf-8"))
            state["jobs"][-1]["baseline"] = "0" * 40
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

    def test_advance_repins_baseline_and_records_actor(self) -> None:
        # P0：提版即重钉——判读在 L、修后线到 L1，报告须按 L1 签；by 落账
        from k3dge.engine.audit_flow import advance_line, materialize, show_job

        with TemporaryDirectory() as d:
            ws = Path(d)
            _mk_ws(ws, "0")
            r1 = submit_audit(ws, "M1", targets=["src"])
            old = r1["baseline"]
            wt = ws / ".k3dge" / "wt" / "M1"
            (wt / "src" / "mod.py").write_text("def f() -> int:\n    return 2\n", encoding="utf-8")
            r = advance_line(ws, "M1", by="hall")
            self.assertTrue(r["ok"] and r["baseline"] != old, r)
            self.assertEqual(r["repinned"], [r1["job_id"]])
            state = json.loads((ws / STATE_REL).read_text(encoding="utf-8"))
            job = state["jobs"][-1]
            self.assertEqual(job["baseline"], r["baseline"])
            self.assertEqual(job["advances"][-1]["by"], "hall")
            # dummy 仍回 submit 时旧基线 ⇒ 拒收如实（真 Hall 会按新基线重签）
            r2 = collect_audit(ws, "M1")
            self.assertEqual(r2["state"], "failed")
            self.assertIn("baseline", r2["detail"])

    def test_show_reads_local_ledger(self) -> None:
        from k3dge.engine.audit_flow import show_job

        with TemporaryDirectory() as d:
            ws = Path(d)
            _mk_ws(ws, "0")
            r1 = submit_audit(ws, "M1", targets=["src"])
            out = show_job(ws, "M1")
            self.assertTrue(out["ok"] and len(out["jobs"]) == 1)
            self.assertEqual(out["jobs"][0]["job_id"], r1["job_id"])
            self.assertIsInstance(out["recent_downgrades"], list)

    def test_materialize_snapshot_without_touching_line(self) -> None:
        import subprocess

        from k3dge.engine.audit_flow import materialize

        with TemporaryDirectory() as d:
            ws = Path(d)
            _mk_ws(ws, "0")
            r1 = submit_audit(ws, "M1", targets=["src"])
            before = subprocess.run(["git", "rev-parse", "k3dit/M1"], cwd=ws,
                                    capture_output=True, text=True).stdout.strip()
            out = materialize(ws, "M1")
            self.assertTrue(out["ok"], out)
            dest = ws / out["dest"]
            self.assertTrue((dest / "src" / "mod.py").is_file())
            self.assertFalse((dest / ".git").exists())
            after = subprocess.run(["git", "rev-parse", "k3dit/M1"], cwd=ws,
                                   capture_output=True, text=True).stdout.strip()
            self.assertEqual(before, after)                       # 线原位未动
            self.assertEqual(out["rev"], r1["baseline"])          # 缺 oid 即基线
            bad = materialize(ws, "M1", rev="0" * 40)
            self.assertFalse(bad["ok"])

    def test_present_seq_bumps_only_on_delivery(self) -> None:
        from unittest import mock

        import k3dge.engine.audit_flow as audit_flow

        with TemporaryDirectory() as d:
            ws = Path(d)
            _mk_ws(ws, "0")
            r1 = submit_audit(ws, "M1", targets=["src"])

            class _Ok:
                ok, detail, downgrades, payload = True, "", [], ""

            with mock.patch.object(audit_flow, "run_action", return_value=_Ok()):
                p1 = audit_flow.push_present(ws, r1["job_id"])
                p2 = audit_flow.push_present(ws, r1["job_id"])
            self.assertTrue(p1["ok"] and p1["pushed"][0]["seq"] == 1)
            self.assertEqual(p2["pushed"][0]["seq"], 2)
            state = json.loads((ws / STATE_REL).read_text(encoding="utf-8"))
            self.assertEqual(state["jobs"][-1]["present_seq"], 2)


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

    # 播报态：席位一圈的细节走 pointers（不再有 if_y 分支字段）
    assert "ratchet_open" in STATE_OPTIONS
    assert any("§1.4" in p for p in STATE_OPTIONS["ratchet_open"]["pointers"])


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
    draft.write_text("# 质量报告（94 条草稿，无 kind 标记）\n", encoding="utf-8")
    hdr = (
        "| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n")
    (tmp_path / ".agent" / "audit_jobs.json").write_text(_j.dumps({"jobs": [
        {"job_id": "J-q", "role": "quality", "milestone_id": "M9", "state": "awaiting",
         "baseline": "sha256:mine", "ticket_task": None}]}), encoding="utf-8")

    class _R:
        ok, detail, downgrades, payload, skipped = True, "", [], "", False

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
         "baseline": "sha256:mine", "ticket_task": None}]}), encoding="utf-8")
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


def test_collect_closed_pins_baseline_ref(tmp_path):
    import subprocess

    from k3dge.engine.audit_flow import STATE_REL, collect_audit, submit_audit

    ws = Path(tmp_path)
    _mk_ws(ws, "0")
    r1 = submit_audit(ws, "M1", targets=["src"])
    r2 = collect_audit(ws, "M1")
    assert r2["state"] == "closed" and r2["baseline_pinned"] is True
    out = subprocess.run(["git", "rev-parse", f"refs/audit-baseline/{r1['job_id']}"],
                         cwd=ws, capture_output=True, text=True).stdout.strip()
    assert out == r1["baseline"]  # 报告引用的基线钉 ref 留存，重演悬空也不丢
