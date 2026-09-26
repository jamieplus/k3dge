"""k3dit 交付包**消费侧**（k3dit 仓 0028）：验契约 → 自证 → 标准 `git apply` 落补丁。

这些测试用**合成包**（不依赖 k3dit 在场）：k3dge 的消费逻辑必须能独立被验——
契约面（`bundle_version`/`status`/`apply_order`）、fail-clear（异版/未闭环/脏树）、
以及对历史**零改动**的 dry-run。
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from k3dge.engine import audit_bundle as ab

_FIX = """--- a/src/a.py
+++ b/src/a.py
@@ -1,2 +1,3 @@
 x = 1
 y = 2
+added_by_fix = True
"""
_PINS = """--- a/src/a.py
+++ b/src/a.py
@@ -1,3 +1,4 @@
+x = 1  # k3dit:fixed code-1 复核通过
 x = 1
 y = 2
 added_by_fix = True
"""


def _repo(tmp: Path) -> Path:
    ws = tmp / "ws"
    (ws / "src").mkdir(parents=True)
    (ws / "src" / "a.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
    for argv in (["init", "-q"], ["add", "-A"],
                 ["-c", "user.email=a@b", "-c", "user.name=a", "commit", "-qm", "base"]):
        subprocess.run(["git", *argv], cwd=ws, check=True, capture_output=True)
    return ws


def _bundle(tmp: Path, *, version: int = 1, status: str = "closed", order=("fix.patch", "pins.patch"),
            patches: bool = True) -> Path:
    b = tmp / "bundle"
    b.mkdir(parents=True, exist_ok=True)
    if patches:
        (b / "fix.patch").write_text(_FIX, encoding="utf-8")
        (b / "pins.patch").write_text(_PINS, encoding="utf-8")
    (b / "report.md").write_text("# 审计\n", encoding="utf-8")
    (b / "findings.json").write_text(json.dumps({"items": []}, ensure_ascii=False), encoding="utf-8")
    (b / "manifest.json").write_text(json.dumps({
        "bundle_version": version, "status": status, "unclosed": 0 if status == "closed" else 3,
        "apply_order": list(order), "patches": ["fix.patch", "pins.patch"],
        "pins": {"count": 1, "by_state": {"fixed": 1}, "in_code": True},
        "flow": {"windows": {"fix": 2, "review": 1}, "rework_ratio": 1.0},
        "coverage": {"audited_files": 1}, "input": "/tmp/x", "mode": "full", "job_id": "j1",
    }, ensure_ascii=False), encoding="utf-8")
    return b


def test_bundle_facts_and_digest_read_the_contract_surface(tmp_path):
    b = _bundle(tmp_path)
    f = ab.bundle_facts(b)
    assert f["bundle_version"] == 1 and f["status"] == "closed"
    assert f["apply_order"] == ["fix.patch", "pins.patch"] and f["flow"]["windows"]["fix"] == 2
    assert ab.bundle_digest(b) == ab.bundle_digest(b)          # 确定性
    (b / "report.md").write_text("# 审计 changed\n", encoding="utf-8")
    assert ab.bundle_digest(b) != ab.bundle_digest(b) if False else True  # 摘要随内容变（下一行实证）
    d1 = ab.bundle_digest(b)
    (b / "report.md").write_text("# 审计\n", encoding="utf-8")
    assert ab.bundle_digest(b) != d1


def test_consume_fails_clear_on_unknown_version_and_unclosed(tmp_path, monkeypatch):
    ws = _repo(tmp_path)
    monkeypatch.setattr(ab, "verify_bundle", lambda *a, **k: {"ok": True})
    bad_ver = _bundle(tmp_path / "v", version=999)
    r = ab.consume(ws, bad_ver)
    assert r["ok"] is False and r["error"] == "BUNDLE_VERSION_UNSUPPORTED"
    open_b = _bundle(tmp_path / "o", status="partial")
    r2 = ab.consume(ws, open_b)
    assert r2["ok"] is False and r2["error"] == "NOT_CLOSED"
    assert "unclosed" in r2["detail"]


def test_consume_fails_clear_when_pack_self_check_fails(tmp_path, monkeypatch):
    ws = _repo(tmp_path)
    monkeypatch.setattr(ab, "verify_bundle",
                        lambda *a, **k: {"ok": False, "errors": ["包结构版本不认"]})
    r = ab.consume(ws, _bundle(tmp_path))
    assert r["ok"] is False and r["error"] == "VERIFY_FAILED"


def test_apply_bundle_uses_standard_git_apply_and_refuses_dirty_tree(tmp_path):
    ws = _repo(tmp_path)
    b = _bundle(tmp_path)
    dry = ab.apply_bundle(ws, b, dry_run=True)
    assert dry["ok"] and dry["dry_run"] and dry["applied"] == ["fix.patch", "pins.patch"]
    assert (ws / "src" / "a.py").read_text(encoding="utf-8") == "x = 1\ny = 2\n"   # dry-run 零改动

    res = ab.apply_bundle(ws, b)
    assert res["ok"] and res["files"] == ["src/a.py"]
    txt = (ws / "src" / "a.py").read_text(encoding="utf-8")
    assert "added_by_fix = True" in txt and "k3dit:fixed code-1" in txt       # 两条补丁都落了

    dirty_ws = _repo(tmp_path / "d")
    (dirty_ws / "src" / "a.py").write_text("x = 999\n", encoding="utf-8")     # 在途改动
    r = ab.apply_bundle(dirty_ws, b)
    assert r["ok"] is False and r["error"] == "DIRTY_TREE"
    assert "在途" in r["detail"] or "不干净" in r["detail"]


def test_apply_bundle_reports_missing_patch_file(tmp_path):
    ws = _repo(tmp_path)
    b = _bundle(tmp_path, order=("fix.patch", "pins.patch"), patches=False)
    r = ab.apply_bundle(ws, b)
    assert r["ok"] is False and r["error"] == "PATCH_MISSING:fix.patch"


def test_cli_transport_substitutes_known_placeholders_only():
    from k3dge.engine.pipeline_runner import _cli_command

    cmd = "k3dit audit --verify {bundle} --milestone {milestone_id} --keep {} || echo {nope}"
    got = _cli_command(cmd, {"bundle": "/tmp/b", "milestone_id": "M11"})
    assert got == "k3dit audit --verify /tmp/b --milestone M11 --keep {} || echo {nope}"


def test_bundle_audit_leg_routes_and_fails_clear(tmp_path, monkeypatch):
    """封板审计腿 `mode="bundle"`（k3dit 仓 0028 消费方）：

    - 找不到 k3dit ⇒ **拒绝**（声明面与实现面不符时不得静默换成别的形状）；
    - k3dit 未闭环 ⇒ **拒绝**（未关不得当已审）；
    - 闭环 ⇒ 消费 + 落树 + 提交，并且**落到共用尾**（`early is None`）。
    """
    from k3dge.engine import milestone_audit as ma

    ws = _repo(tmp_path)
    (ws / ".agent").mkdir(exist_ok=True)
    (ws / ".agent" / "pipeline.toml").write_text('[roles.audit]\nbind = "k3dit"\nmode = "bundle"\n',
                                                 encoding="utf-8")
    assert ma._audit_mode(ws) == "bundle"

    # ① 没有 k3dit ⇒ 拒绝（code=audit_bundle_no_k3dit）
    monkeypatch.setattr(ab, "find_k3dit", lambda w: None)
    early, _ = ma._bundle_audit_leg(ws, "M99", ma._Prompt.default(), "b" * 40)
    assert early is not None and early[0] == "refused" and "找不到 k3dit" in early[1]

    # ② 产包未闭环 ⇒ 拒绝
    monkeypatch.setattr(ab, "find_k3dit", lambda w: ["k3dit"])
    monkeypatch.setattr(ab, "run_path_audit",
                        lambda w, out, **k: {"ok": True, "rc": 3, "payload": {"status": "incomplete", "unclosed": 2}})
    early, _ = ma._bundle_audit_leg(ws, "M99", ma._Prompt.default(), "b" * 40)
    assert early is not None and early[0] == "refused" and "未闭环" in early[1]

    # ③ 闭环 + 消费成功 ⇒ 落树提交，并返回 (None, msg) 让共用尾收口
    def _fake_run(w, out, **k):
        # 真工具会产包（含 12 列报告）；这里造最小包，让"报告落地"有源可落
        out.mkdir(parents=True, exist_ok=True)
        (out / "report.md").write_text(
            "# 审计\n\n| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n",
            encoding="utf-8")
        return {"ok": True, "rc": 0, "payload": {"status": "closed", "incomplete": False}}

    monkeypatch.setattr(ab, "run_path_audit", _fake_run)
    monkeypatch.setattr(ab, "consume",
                        lambda w, b, **k: {"ok": True, "apply": {"files": ["src/a.py"]},
                                           "facts": {"job_id": "j9"}, "digest": "d" * 64})
    (ws / "src" / "a.py").write_text("x = 1\ny = 2\nz = 3\n", encoding="utf-8")
    early, msg = ma._bundle_audit_leg(ws, "M99", ma._Prompt.default(), "b" * 40)
    assert early is None and "bundle 审计腿闭环" in msg and "工具 k3dit" in msg
    from k3dge.engine.seal import head_commit
    from k3dge.engine.audit_report import _find_report

    assert head_commit(ws)            # 确实产生了一次提交
    # ① 报告落地：判定面（checklist/触发）靠 `_find_report` 在 docs/reviews 里找它
    found = _find_report(ws, "M99", "audit")
    assert found, "包里的 12 列报告必须落到 docs/reviews（否则 checklist/judged 看不到审计产物）"
    assert "docs/reviews" in found[0].as_posix() and "k3dit-bundle" in found[0].name
    # ② 包在**仓外**：k3dit 的中间产物不该进被审树（旧位置 <ws>/.k3dit/... 会留未跟踪目录）
    import subprocess

    status = subprocess.run(["git", "-C", str(ws), "status", "--porcelain"],
                            capture_output=True, text=True).stdout
    assert ".k3dit" not in status and ".k3ge" not in status, status
    assert not (ws / ".k3dit").exists()


def test_run_path_audit_passes_mode_and_pins(tmp_path, monkeypatch):
    """工具参数必须**传到位**：`--mode` 与 `--pins` 是 k3dit 的两个运行旋钮（纯审计/钉只随包）。"""
    seen = {}

    def _fake_run(argv, cwd, timeout):
        seen["argv"] = argv
        return 0, '{"ok": true, "status": "closed"}'

    monkeypatch.setattr(ab, "_run", _fake_run)
    monkeypatch.setattr(ab, "find_k3dit", lambda w: ["k3dit"])
    ab.run_path_audit(tmp_path, tmp_path / "b", mode="audit-only", pins="artifact")
    argv = seen["argv"]
    assert argv[argv.index("--mode") + 1] == "audit-only"
    assert argv[argv.index("--pins") + 1] == "artifact"


def test_leg_reads_tool_knobs_from_declaration_and_audit_only_is_evidence_only(tmp_path, monkeypatch):
    """工具运行参数走**声明面**（`[roles.audit] k3dit_mode/k3dit_pins`），不在腿里写死。

    纯审计（`k3dit_mode = "audit-only"`）＝**只出证据不封板**：报告必须落 `docs/reviews/`，
    包按 `apply_order` 落钉，然后以 `refused(audit_evidence_only)` 交回（`status=partial` 是设计）。
    """
    from k3dge.engine import milestone_audit as ma
    from k3dge.engine.audit_report import _find_report

    ws = _repo(tmp_path)
    (ws / ".agent").mkdir(exist_ok=True)
    (ws / ".agent" / "pipeline.toml").write_text(
        '[roles.audit]\nbind = "k3dit"\nmode = "bundle"\n'
        'k3dit_mode = "audit-only"\nk3dit_pins = "artifact"\n', encoding="utf-8")
    monkeypatch.setattr(ab, "find_k3dit", lambda w: ["k3dit"])

    calls = {}

    def _fake_run(w, out, *, mode="full", pins="inplace", **k):
        calls["mode"], calls["pins"] = mode, pins
        out.mkdir(parents=True, exist_ok=True)
        (out / "report.md").write_text(
            "# 审计\n\n| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n", encoding="utf-8")
        return {"ok": True, "rc": 0, "payload": {"status": "partial", "unclosed": 3}}

    monkeypatch.setattr(ab, "run_path_audit", _fake_run)
    consumed = {}

    def _fake_consume(w, b, **k):
        consumed.update(k)
        return {"ok": True, "apply": {"files": []}, "facts": {"job_id": "j1"}, "digest": "e" * 64}

    monkeypatch.setattr(ab, "consume", _fake_consume)
    monkeypatch.setattr(ab, "commit_applied", lambda w, m, f: "c" * 40)
    early, _ = ma._bundle_audit_leg(ws, "M77", ma._Prompt.default(), "b" * 40)
    assert calls == {"mode": "audit-only", "pins": "artifact"}      # 声明面被读到并传下去
    assert consumed.get("require_closed") is False                  # partial 不进 NOT_CLOSED
    assert early is not None and early[0] == "refused" and "只出证据" in early[1]
    assert _find_report(ws, "M77", "audit"), "纯审计也要落报告（证据）"

    # 非法取值 ⇒ 拒绝（不静默按缺省跑）
    (ws / ".agent" / "pipeline.toml").write_text(
        '[roles.audit]\nbind = "k3dit"\nmode = "bundle"\nk3dit_mode = "quick"\n', encoding="utf-8")
    early2, _ = ma._bundle_audit_leg(ws, "M77", ma._Prompt.default(), "b" * 40)
    assert early2 is not None and early2[0] == "refused" and "不合法" in early2[1]
