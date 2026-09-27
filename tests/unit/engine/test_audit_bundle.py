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

from .test_audit_verify import make_bundle


def _bundle(tmp: Path, *, version: int = 1, status: str = "closed", order=("fix.patch", "pins.patch"),
            patches: bool = True) -> Path:
    """合成包＝**结构完整**的包（`code/` + `baseline.json` + 12 列表格 + 真生成的补丁）。

    走 `test_audit_verify.make_bundle`（单一夹具）：消费侧的闸现在会真读这些文件，
    所以"只写 manifest 的假包"已不能代表真实输入。
    `patches=False` ⇒ 造"补丁缺失"的形态（给 `apply_bundle` 的 fail-clear 用）。
    """
    b = make_bundle(tmp, version=version, claimed=status, order=order,
                    finding_state=("fixed" if status == "closed" else "pending"),
                    row_state=("已修" if status == "closed" else "待修"))
    if not patches:
        (b / "fix.patch").unlink(missing_ok=True)
        (b / "pins.patch").unlink(missing_ok=True)
    return b


def _repo(tmp: Path) -> Path:
    ws = tmp / "ws"
    (ws / "src").mkdir(parents=True)
    (ws / "src" / "a.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
    for argv in (["init", "-q"], ["add", "-A"],
                 ["-c", "user.email=a@b", "-c", "user.name=a", "commit", "-qm", "base"]):
        subprocess.run(["git", *argv], cwd=ws, check=True, capture_output=True)
    return ws


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
    bad_ver = _bundle(tmp_path / "v", version=999)
    r = ab.consume(ws, bad_ver)
    assert r["ok"] is False and r["error"] == "BUNDLE_VERSION_UNSUPPORTED"
    open_b = _bundle(tmp_path / "o", status="partial")
    r2 = ab.consume(ws, open_b)
    # 闭环判据归**消费侧**（不再读产出方自报的 status）⇒ 未关由本地算出来
    assert r2["ok"] is False and r2["error"] == "VERIFY_FAILED"
    assert "未闭环（消费侧算）" in r2["detail"] and "闭环事实不一致" not in r2["detail"]


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

    # ② 产包未闭环 ⇒ 拒绝。**闭环由消费侧自己算**（不再读产出方自报的 status）⇒ 得让 consume 拿到真包
    monkeypatch.setattr(ab, "find_k3dit", lambda w: ["k3dit"])

    def _run_open(w, out, **k):
        import shutil

        src = make_bundle(tmp_path / "opensrc", claimed="partial", finding_state="pending",
                          row_state="待修", input_path=str(ws))
        shutil.rmtree(out, ignore_errors=True)      # 同一测试里腿会被调多次 ⇒ 目标目录先清
        shutil.copytree(src, out)
        return {"ok": True, "rc": 3, "payload": {"status": "partial", "unclosed": 2}}

    monkeypatch.setattr(ab, "run_path_audit", _run_open)
    early, _ = ma._bundle_audit_leg(ws, "M99", ma._Prompt.default(), "b" * 40)
    assert early is not None and early[0] == "refused" and "未闭环（消费侧算）" in early[1], early

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
    ab.run_path_audit(tmp_path, tmp_path / "b", mode="audit-only", pins="artifact",
                      scope="src/k3dit/tools,docs")
    argv = seen["argv"]
    assert argv[argv.index("--mode") + 1] == "audit-only"
    assert argv[argv.index("--pins") + 1] == "artifact"
    assert argv[argv.index("--scope") + 1] == "src/k3dit/tools,docs"
    seen.clear()
    ab.run_path_audit(tmp_path, tmp_path / "b")          # 空 scope ⇒ **不传**该参（用 k3dit 缺省）
    assert "--scope" not in seen["argv"]


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

    def _fake_run(w, out, *, mode="full", pins="inplace", scope="", **k):
        calls["mode"], calls["pins"], calls["scope"] = mode, pins, scope
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
    monkeypatch.setattr(ab, "commit_applied", lambda w, m, f: ("c" * 40, ""))
    early, _ = ma._bundle_audit_leg(ws, "M77", ma._Prompt.default(), "b" * 40)
    assert calls == {"mode": "audit-only", "pins": "artifact", "scope": ""}   # 声明面被读到并传下去

    # scope 也走声明面（`k3dit_scope`）：**相对仓根**才合法；绝对路径 / `..` 一律拒绝——送审范围不该被
    # 旋钮带到仓外（那只会是写错；静默接受会让报告覆盖范围与声明不符）。
    (ws / ".agent" / "pipeline.toml").write_text(
        '[roles.audit]\nbind = "k3dit"\nmode = "bundle"\nk3dit_mode = "audit-only"\n'
        'k3dit_scope = "src/k3dit/tools,docs"\n', encoding="utf-8")
    ma._bundle_audit_leg(ws, "M77", ma._Prompt.default(), "b" * 40)
    assert calls.get("scope") == "src/k3dit/tools,docs", calls
    for _bad in ("/etc", "../outside", "src/../.."):
        (ws / ".agent" / "pipeline.toml").write_text(
            f'[roles.audit]\nbind = "k3dit"\nmode = "bundle"\nk3dit_scope = "{_bad}"\n',
            encoding="utf-8")
        _early, _ = ma._bundle_audit_leg(ws, "M77", ma._Prompt.default(), "b" * 40)
        assert _early is not None and _early[0] == "refused" and "k3dit_scope" in _early[1], _bad
    (ws / ".agent" / "pipeline.toml").write_text(
        '[roles.audit]\nbind = "k3dit"\nmode = "bundle"\n'
        'k3dit_mode = "audit-only"\nk3dit_pins = "artifact"\n', encoding="utf-8")
    assert consumed.get("require_closed") is False                  # partial 不进 NOT_CLOSED
    assert early is not None and early[0] == "refused" and "只出证据" in early[1]
    assert _find_report(ws, "M77", "audit"), "纯审计也要落报告（证据）"

    # 非法取值 ⇒ 拒绝（不静默按缺省跑）
    (ws / ".agent" / "pipeline.toml").write_text(
        '[roles.audit]\nbind = "k3dit"\nmode = "bundle"\nk3dit_mode = "quick"\n', encoding="utf-8")
    early2, _ = ma._bundle_audit_leg(ws, "M77", ma._Prompt.default(), "b" * 40)
    assert early2 is not None and early2[0] == "refused" and "不合法" in early2[1]


def test_leg_refuses_with_reason_when_commit_fails(tmp_path, monkeypatch):
    """提交失败必须**带原因**回绝（不再静默留 staged 树）。

    真跑出处（2026-09-27 C 验收）：报告刚落、`docs-index` 过期 ⇒ 本地钩子 `DOC_INDEX_STALE` 拦下提交，
    而 `commit_applied` 只 `return ""` ⇒ 腿输出只表现为"没提提交"，真实原因被吞，树留在 staged 态
    （下一次跑又被 `DIRTY_TREE` 挡）。此测试钉住：① 提交前重生投影；② 失败带 git 报错；③ 退 `refused`。
    """
    from k3dge.engine import doc_catalog, milestone_audit as ma

    ws = _repo(tmp_path)
    (ws / ".agent").mkdir(exist_ok=True)
    (ws / ".agent" / "pipeline.toml").write_text(
        '[roles.audit]\nbind = "k3dit"\nmode = "bundle"\nk3dit_mode = "audit-only"\n', encoding="utf-8")
    monkeypatch.setattr(ab, "find_k3dit", lambda w: ["k3dit"])
    monkeypatch.setattr(ab, "run_path_audit", lambda w, out, **k: (
        (out / "report.md").write_text("# 审计\n", encoding="utf-8"),
        out.mkdir(parents=True, exist_ok=True),
        {"ok": True, "rc": 0, "payload": {"status": "partial", "unclosed": 1}})[-1])
    monkeypatch.setattr(ab, "consume", lambda w, b, **k: {
        "ok": True, "apply": {"files": ["src/a.py"]}, "facts": {"job_id": "j1"}, "digest": "e" * 64})
    idx = ws / doc_catalog.INDEX_REL
    idx.parent.mkdir(parents=True, exist_ok=True)
    idx.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(doc_catalog, "write_docs_index", lambda w: idx)      # 投影重生（真函数在测试仓无 docs/）
    monkeypatch.setattr(ab, "commit_applied",
                        lambda w, m, f: ("", "git commit 失败：hook DOC_INDEX_STALE 拦下"))
    early, _ = ma._bundle_audit_leg(ws, "M77", ma._Prompt.default(), "b" * 40)
    assert early is not None and early[0] == "refused", early
    assert "提交失败" in early[1] and "DOC_INDEX_STALE" in early[1], early[1]


def test_leg_lands_report_even_when_consume_is_refused(tmp_path, monkeypatch):
    """消费被拒（脏树 / 补丁打不上）**也必须把报告落到 `docs/reviews/` 并提交**。

    真跑出处（2026-09-27）：第一轮腿产包后因 `DIRTY_TREE` 被拒 ⇒ 20KB/31 行报告**只留在缓存目录**，
    随后为了验收换窄 scope 重跑 ⇒ 落仓的成了"0 行结论"的空报告。跑完没留下证据＝这一轮（2.29M prompt）白跑。
    """
    from k3dge.engine import doc_catalog, milestone_audit as ma
    from k3dge.engine.audit_report import _find_report

    ws = _repo(tmp_path)
    (ws / ".agent").mkdir(exist_ok=True)
    (ws / ".agent" / "pipeline.toml").write_text(
        '[roles.audit]\nbind = "k3dit"\nmode = "bundle"\nk3dit_mode = "audit-only"\n', encoding="utf-8")
    monkeypatch.setattr(ab, "find_k3dit", lambda w: ["k3dit"])
    monkeypatch.setattr(ab, "run_path_audit", lambda w, out, **k: (
        out.mkdir(parents=True, exist_ok=True),
        (out / "report.md").write_text(
            "# 审计\n\n| ID | 日期 |\n| --- | --- |\n| d-1 | 2026-09-27 |\n", encoding="utf-8"),
        {"ok": True, "rc": 0, "payload": {"status": "partial", "unclosed": 3}})[-1])
    monkeypatch.setattr(ab, "consume", lambda w, b, **k: {"ok": False, "error": "DIRTY_TREE",
                                                          "detail": "工作树不干净"})
    idx = ws / doc_catalog.INDEX_REL
    idx.parent.mkdir(parents=True, exist_ok=True)
    idx.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(doc_catalog, "write_docs_index", lambda w: idx)
    seen = {}
    monkeypatch.setattr(ab, "commit_applied",
                        lambda w, m, f: (seen.update(msg=m, files=list(f)) or ("d" * 40, "")))
    early, _ = ma._bundle_audit_leg(ws, "M77", ma._Prompt.default(), "b" * 40)
    assert early is not None and early[0] == "refused" and "DIRTY_TREE" in early[1], early
    assert "报告已落" in early[1], early[1]
    got = _find_report(ws, "M77", "audit")           # (path, text)
    assert got and "d-1" in got[1], "报告必须真的落盘（含内容）"
    assert doc_catalog.INDEX_REL in seen["files"], seen["files"]      # 投影一并提交


def test_land_report_is_the_single_entry_used_by_all_three_paths(tmp_path, monkeypatch):
    """**流程体检（2026-09-27）**：同一序列（落报告 → 重生投影 → 一次提交）此前写了两遍、手动入口一遍没有。

    现在三个入口（腿正常路 / 腿拒绝路 / `k3dge audit bundle`）共用 `land_report`：
    报告与已落补丁**同一次提交**，投影（docs-index）并入；缺报告 ⇒ fail-clear。
    """
    from k3dge.engine import doc_catalog, search

    ws = _repo(tmp_path)
    out = tmp_path / "out"
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text("# 审计\n\n| ID |\n", encoding="utf-8")
    # 投影面：`sync_all`（文档/契约/索引）与 `write_symbol_index`（`k3dge where` 判据面）都要跑
    gen = ws / "docs" / "generated"
    gen.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(doc_catalog, "write_docs_index",
                        lambda w: (gen / "docs-index.json").write_text("{}\n", encoding="utf-8") or
                        (gen / "docs-index.json"))
    monkeypatch.setattr(search, "write_symbol_index",
                        lambda w: (gen / "symbol-index.json").write_text("{}\n", encoding="utf-8") or
                        (gen / "symbol-index.json"))
    seen = {}
    monkeypatch.setattr(ab, "commit_applied",
                        lambda w, m, f: (seen.update(msg=m, files=list(f)) or ("a" * 40, "")))
    r = ab.land_report(ws, "M1", out, extra_files=["src/a.py"], why="job j1")
    assert r["ok"] and r["commit"] == "a" * 40 and r["report"].endswith(".md")
    assert "src/a.py" in seen["files"], seen["files"]                       # 补丁与报告同一次提交
    assert "docs/generated/symbol-index.json" in seen["files"], seen["files"]   # 投影并入（engine 自有写入器）
    assert "job j1" in seen["msg"]
    assert "MM1" not in seen["msg"] and seen["msg"].count("M1") == 1, seen["msg"]   # id 原样用（别再前置 M）
    empty = tmp_path / "empty"
    empty.mkdir()
    bad = ab.land_report(ws, "M1", empty)
    assert not bad["ok"] and bad["error"] == "REPORT_MISSING"
