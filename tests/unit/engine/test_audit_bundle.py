"""k3dit 交付包**消费侧**（k3dit 仓 0008）：验契约 → 自证 → 标准 `git apply` 落补丁。

这些测试用**合成包**（不依赖 k3dit 在场）：k3dge 的消费逻辑必须能独立被验——
契约面（`bundle_version`/`status`/`apply_order`）、fail-clear（异版/未闭环/脏树）、
以及对历史**零改动**的 dry-run。
"""
from __future__ import annotations

import json
import os
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
    d0 = ab.bundle_digest(b)
    (b / "report.md").write_text("# 审计 changed\n", encoding="utf-8")
    assert ab.bundle_digest(b) != d0                            # 摘要随内容变
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
    # **未闭环 ⇒ 部分落地**（用户裁定 乙）：不整包拒；未关项所在文件被排除、升级记在结果里
    assert r2["ok"] is True and r2["partial"] is True, r2
    assert "code-1" in (r2["escalated"] or []), r2
    assert "src/a.py" in (r2["unclosed_files"] or []), r2
    # 未关项走 **hunk 级**（不再整文件排除）：解析出它在 `src/a.py:1`，由落地侧剔掉重叠 hunk
    assert r2["unclosed_hunks"] == {"src/a.py": [1]}, r2["unclosed_hunks"]
    assert "src/a.py" in (r2["apply"].get("dropped_hunks") or {}), r2["apply"]


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


def test_ignored_runtime_projection_does_not_trip_dirty_tree(tmp_path):
    """审计开跑即重写 `.agent/audit_checklist.json` ⇒ 它必须与工单账一样是 **gitignored 投影**。

    它是 tracked 的时候：任何带补丁的封板在落补丁相位必被自家 `DIRTY_TREE` 挡（真跑实测：M11
    续跑的包 `apply_order` 非空 ⇒ 直接拒），而那个"脏"既不是被审改动也不是在途工作。
    """
    ws = _repo(tmp_path / "proj")
    (ws / ".gitignore").write_text(".agent/audit_jobs.json\n.agent/audit_checklist.json\n",
                                   encoding="utf-8")
    for argv in (["add", "-A"], ["-c", "user.email=a@b", "-c", "user.name=a", "commit", "-qm", "ignore"]):
        subprocess.run(["git", *argv], cwd=ws, check=True, capture_output=True)
    (ws / ".agent").mkdir(exist_ok=True)
    (ws / ".agent" / "audit_checklist.json").write_text('{"milestone": "M1"}\n', encoding="utf-8")
    rc, out = subprocess.run(["git", "status", "--porcelain"], cwd=ws,
                             capture_output=True, text=True).returncode, \
        subprocess.run(["git", "status", "--porcelain"], cwd=ws, capture_output=True,
                       text=True).stdout
    assert rc == 0 and out.strip() == "", out        # 投影不污染工作树

    r = ab.apply_bundle(ws, _bundle(tmp_path / "proj"))
    assert r.get("error") != "DIRTY_TREE", r
    assert r["ok"] is True, r


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
    """封板审计腿 `mode="bundle"`（k3dit 仓 0008 消费方）：

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
                          row_state="待修", input_path=str(w))       # 目标是**当前**工作区（w）
        shutil.rmtree(out, ignore_errors=True)      # 同一测试里腿会被调多次 ⇒ 目标目录先清
        shutil.copytree(src, out)
        return {"ok": True, "rc": 3, "payload": {"status": "partial", "unclosed": 2}}

    monkeypatch.setattr(ab, "run_path_audit", _run_open)
    ws2 = _repo(tmp_path / "ws_open")          # 干净工作区（上一 case 的落地会留脏树 ⇒ DIRTY_TREE）
    (ws2 / ".agent").mkdir(exist_ok=True)
    (ws2 / ".agent" / "pipeline.toml").write_text(
        '[roles.audit]\nbind = "k3dit"\nmode = "bundle"\nk3dit_mode = "audit-only"\n', encoding="utf-8")
    import subprocess as _sp

    _sp.run(["git", "-C", str(ws2), "add", "-A"], check=True, capture_output=True)   # 声明必须**已提交**
    _sp.run(["git", "-C", str(ws2), "-c", "user.email=t@t", "-c", "user.name=t",
             "commit", "-qm", "decl"], check=True, capture_output=True)
    early, msg = ma._bundle_audit_leg(ws2, "M99", ma._Prompt.default(), "b" * 40)
    # 未关 ⇒ **部分落地**（落已修、排除未关项所在文件）；声明是 audit-only ⇒ 仍以 refused 交回，
    # 但**升级信息必须由 k3dge 的这条闸报出来**（k3dit 里没人看得到升级）。
    assert early is not None and early[0] == "refused" and "只出证据" in early[1], early
    assert "升级" in early[1] and "code-1" in early[1], early

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

    def _fake_run(argv, cwd, timeout, env=None):
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
        # 元组自左向右求值：先建目录再写文件（旧顺序在 out 尚不存在时抛 FileNotFoundError，
        # 于是"提交失败带原因"这条被测路径根本没走到，t-118）
        out.mkdir(parents=True, exist_ok=True),
        (out / "report.md").write_text("# 审计\n", encoding="utf-8"),
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


def test_post_apply_check_is_read_from_declaration_and_run(tmp_path, monkeypatch):
    """落库后校验走**声明面**（`[roles.audit] post_apply_check`）：修复并进主干必须过消费仓自己的测试。

    真跑出处（2026-09-27）：补丁过了 `git apply` 但让测试红 ⇒ 只有"落完记得跑测试"这条**人的习惯**在挡。
    """
    ws = _repo(tmp_path)
    (ws / ".agent").mkdir(exist_ok=True)
    (ws / ".agent" / "pipeline.toml").write_text(
        '[roles.audit]\nbind = "k3dit"\nmode = "bundle"\npost_apply_check = "true"\n', encoding="utf-8")
    ok = ab._post_apply_check(ws, ws)
    assert ok["cmd"] == "true" and ok["ok"] is True, ok
    (ws / ".agent" / "pipeline.toml").write_text(
        '[roles.audit]\nbind = "k3dit"\nmode = "bundle"\npost_apply_check = "exit 3"\n', encoding="utf-8")
    bad = ab._post_apply_check(ws, ws)
    assert bad["ok"] is False and bad["rc"] == 3, bad
    (ws / ".agent" / "pipeline.toml").write_text('[roles.audit]\nbind = "k3dit"\nmode = "bundle"\n',
                                                 encoding="utf-8")
    skipped = ab._post_apply_check(ws, ws)
    assert skipped["cmd"] == "" and skipped["ok"] is True       # 未声明 ⇒ 跳过（如实报 cmd=''）


def test_report_rows_are_reconciled_with_what_actually_landed(tmp_path):
    """**承重缺口**（2026-09-27）：报告行 ↔ 实际落地必须机械对账，否则虚报已审。

    证据链：`audit_checklist._snapshot` 的 `pending` ＝报告 `待修` 行数；`--exclude` 掉的文件其条目仍写
    "已修" ⇒ `pending=0` ⇒ 封板判据被糊弄。规则：位置列指向被排除文件的行 ⇒ 状态改 `待修` + 处置标注原因。
    """
    body = ("# 审计\n\n"
            "| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
            "| a-1 | 2026-09-27 | 中 | P1 | 正确性 | x | src/x/landed.py:10 | 已修 | 改了 | 验了 | | |\n"
            "| a-2 | 2026-09-27 | 中 | P1 | 正确性 | y | src/x/excluded.py:20 | 已修 | 改了 | 验了 | | |\n"
            "| a-3 | 2026-09-27 | 低 | P3 | 规范 | z | src/x/excluded.py:5 | 有意留 | 有意留：理由 | | | |\n"
            "| a-4 | 2026-09-27 | 低 | P3 | 规范 | w | src/x/notlanded.py:7 | 已修 | 改了 | 验了 | | |\n")
    r = ab.reconcile_report_rows(body, ["src/x/excluded.py", "src/x/notlanded.py"], ["a-2"])
    assert r["changed"] == 2 and sorted(r["ids"]) == ["a-2", "a-4"], r
    out = str(r["body"])
    assert out.count("| 已修 |") == 3, out                   # **状态列不动**（用户裁定：改在验证列）
    assert "待验：未闭环（转人工）" in out, out               # 未关项
    assert "升级：本次未落" in out, out                       # 已修但没落
    assert "| 有意留 |" in out and out.count("升级：本次未落") == 1, out   # 有意留不标
    # 无排除项 ⇒ 原样（不动报告）
    same = ab.reconcile_report_rows(body, [], [])
    assert same["changed"] == 0 and same["body"] == body
    # 表头不合规 ⇒ 原样返回（不冒险改坏报告）
    bad = ab.reconcile_report_rows("# 审计\n\n没有表\n", ["src/x/excluded.py"], ["a-2"])
    assert bad["changed"] == 0 and bad["body"] == "# 审计\n\n没有表\n"


def test_tool_state_never_lands_in_a_foreign_subject(tmp_path, monkeypatch):
    """工具状态（hall root / ledger）**不得落到外部被审仓**（真跑实测：k3dit 把 `.k3dit/` 与 `ledger/` 建进
    被审仓 k3dge ⇒ 工作区变脏 ⇒ 消费相位被自家 `DIRTY_TREE` 拒，而且那些是工具状态不是审计产物）。
    外部被审仓 ⇒ 落缓存（确定性路径，跨轮续用）；工具审自己 ⇒ 不动（保持仓库内状态连续性）。
    """
    subj = tmp_path / "subject"
    subj.mkdir()
    fake_tool = tmp_path / "k3dit" / ".venv" / "bin" / "k3dit"
    fake_tool.parent.mkdir(parents=True)
    fake_tool.write_text("#!/bin/sh\n", encoding="utf-8")
    (tmp_path / "k3dit" / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    monkeypatch.setenv("K3GE_AUDIT_CACHE", str(tmp_path / "cache"))
    env = ab._tool_env(subj, [str(fake_tool)])
    assert env["K3DIT_HALL_ROOT"].startswith(str(tmp_path / "cache"))
    assert env["K3DIT_LEDGER"].startswith(str(tmp_path / "cache"))
    assert str(subj) not in env["K3DIT_HALL_ROOT"] and "K3DIT_HALL_ROOT" not in {
        k: v for k, v in os.environ.items() if k == "K3DIT_HALL_ROOT"}
    # 工具审自己：不覆盖（沿用仓库内状态）
    monkeypatch.setenv("K3DIT_HALL_ROOT", "/tmp/keep-me")
    env2 = ab._tool_env(tmp_path / "k3dit", [str(fake_tool)])
    assert env2["K3DIT_HALL_ROOT"] == "/tmp/keep-me"


def test_tool_timeout_is_a_knob_with_mode_defaults(tmp_path, monkeypatch):
    """墙钟预算必须是**声明面旋钮**（真跑实测：8 文件 full 跑超 1h 被 `_run` 掐断 ⇒ 整轮白烧）。"""
    from k3dge.engine import milestone_audit as ma

    ws = _repo(tmp_path)
    (ws / ".agent").mkdir(exist_ok=True)
    monkeypatch.setattr(ab, "find_k3dit", lambda w: ["k3dit"])
    seen = {}

    def _fake_run(w, out, **k):
        seen.update(k)
        out.mkdir(parents=True, exist_ok=True)
        (out / "report.md").write_text("# 审计\n", encoding="utf-8")
        return {"ok": False, "rc": 9, "payload": {}, "detail": "stub"}

    monkeypatch.setattr(ab, "run_path_audit", _fake_run)
    (ws / ".agent" / "pipeline.toml").write_text('[roles.audit]\nbind = "k3dit"\nmode = "bundle"\n',
                                                 encoding="utf-8")
    ma._bundle_audit_leg(ws, "M1", ma._Prompt.default(), "b" * 40)
    assert seen["timeout"] == 7200                      # full（缺省）⇒ 2h
    (ws / ".agent" / "pipeline.toml").write_text(
        '[roles.audit]\nbind = "k3dit"\nmode = "bundle"\nk3dit_mode = "audit-only"\n', encoding="utf-8")
    ma._bundle_audit_leg(ws, "M1", ma._Prompt.default(), "b" * 40)
    assert seen["timeout"] == 3600                      # 纯审计 ⇒ 1h
    (ws / ".agent" / "pipeline.toml").write_text(
        '[roles.audit]\nbind = "k3dit"\nmode = "bundle"\nk3dit_timeout = "abc"\n', encoding="utf-8")
    early, _ = ma._bundle_audit_leg(ws, "M1", ma._Prompt.default(), "b" * 40)
    assert early is not None and early[0] == "refused" and "k3dit_timeout" in early[1], early


def test_partial_landing_fails_closed_when_unclosed_files_are_unresolvable(tmp_path, monkeypatch):
    """未关项解不出 `location` ⇒ **不许部分落地**（否则会连未关项的修复一起落＝虚报）。"""
    ws = _repo(tmp_path)
    b = _bundle(tmp_path / "noloc", status="partial")
    items = json.loads((b / "findings.json").read_text(encoding="utf-8"))
    for it in items["items"]:
        it.pop("location", None)
    (b / "findings.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(ab, "verify_bundle", lambda *a, **k: {
        "ok": True, "errors": [], "local": {"unclosed": ["code-1"], "facts": {}, "counts": {}}})
    r = ab.consume(ws, b)
    assert r["ok"] is False and r["error"] == "UNRESOLVED_UNCLOSED", r


def test_salvage_on_tool_failure_still_lands_a_report_and_writes_a_digest(tmp_path, monkeypatch):
    """**超时/失败也要出报告**（用户裁定）：工具不会自己 `write_bundle` ⇒ `k3dit hall export --latest` 抢救，
    然后照常验收 + 部分落地 + 升级；运行摘要随包留（事后能看出问题在哪）。
    """
    from k3dge.engine import milestone_audit as ma

    ws = _repo(tmp_path)
    monkeypatch.setenv("K3GE_AUDIT_CACHE", str(tmp_path / "cache"))     # 包与摘要都落缓存（仓外）
    (ws / ".agent").mkdir(exist_ok=True)
    (ws / ".agent" / "pipeline.toml").write_text('[roles.audit]\nbind = "k3dit"\nmode = "bundle"\n',
                                                 encoding="utf-8")
    import subprocess as _sp

    _sp.run(["git", "-C", str(ws), "add", "-A"], check=True, capture_output=True)   # 声明须已提交（否则脏树）
    _sp.run(["git", "-C", str(ws), "-c", "user.email=t@t", "-c", "user.name=t",
             "commit", "-qm", "decl"], check=True, capture_output=True)
    monkeypatch.setattr(ab, "find_k3dit", lambda w: ["k3dit"])
    monkeypatch.setattr(ab, "run_path_audit", lambda w, out, **k: {
        "ok": False, "rc": 124, "payload": {}, "detail": "timed out after 7200 seconds"})

    def _salvage(w, out, **k):
        import shutil

        src = make_bundle(tmp_path / "salv", claimed="partial", finding_state="pending",
                          row_state="待修", input_path=str(w))
        shutil.rmtree(out, ignore_errors=True)
        shutil.copytree(src, out)
        return {"ok": True, "rc": 0, "out": str(out), "detail": ""}

    monkeypatch.setattr(ab, "salvage_bundle", _salvage)
    early, msg = ma._bundle_audit_leg(ws, "M77", ma._Prompt.default(), "b" * 40)
    assert early is None or early[0] != "audit_bundle_run_failed", early      # 不再因"产包失败"停住
    assert "抢救" in msg, (early, msg)
    digests = list((tmp_path / "cache").rglob("run-digest.json"))
    assert digests, "运行摘要必须随产物留下"
    import json as _json

    d = _json.loads(digests[0].read_text(encoding="utf-8"))
    assert d["rc"] == 124 and d["salvage_rc"] == 0 and "tool_state_dir" in d, d


def test_unclosed_findings_exclude_only_their_hunks_not_the_whole_file(tmp_path, monkeypatch):
    """**hunk 级部分落地**（用户裁定："已修的为什么不能落，不是 git 管理吗？"）：
    同文件里两个 hunk，未关项只落在第二个 ⇒ 第一段的修复必须照落，只有第二段被剔掉。
    """
    import difflib

    def _mk(ws: Path, bundle: Path) -> None:
        rel = "src/big.py"
        base = "".join(f"line{i}\n" for i in range(1, 31))
        mid = base.replace("line3\n", "line3\nfixed_A = True\n").replace("line25\n", "line25\nfixed_B = True\n")
        (ws / "src").mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(base, encoding="utf-8")
        (bundle / "code" / rel).parent.mkdir(parents=True, exist_ok=True)
        (bundle / "code" / rel).write_text(mid, encoding="utf-8")
        patch = "".join(difflib.unified_diff(base.splitlines(keepends=True), mid.splitlines(keepends=True),
                                             fromfile=f"a/{rel}", tofile=f"b/{rel}"))
        (bundle / "fix.patch").write_text(patch, encoding="utf-8")
        (bundle / "baseline.json").write_text(json.dumps(
            {"files": {rel: __import__("hashlib").sha1(base.encode()).hexdigest()}, "tree_hash": "x", "count": 1},
            ensure_ascii=False), encoding="utf-8")
        (bundle / "findings.json").write_text(json.dumps({"items": [
            {"id": "f-1", "state": "fixed", "review_ack": True, "location": f"{rel}:4"},
            {"id": "f-2", "state": "pending", "review_ack": False, "location": f"{rel}:25"}]},
            ensure_ascii=False), encoding="utf-8")
        (bundle / "manifest.json").write_text(json.dumps({
            "bundle_version": 1, "status": "incomplete", "unclosed": 1, "apply_order": ["fix.patch"],
            "input": str(ws), "mode": "full", "job_id": "j1",
            "pins": {"count": 0, "by_state": {}, "in_code": True}}, ensure_ascii=False), encoding="utf-8")
        (bundle / "report.md").write_text(
            "# 审计\n\n| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
            f"| f-1 | 2026-09-27 | 中 | P1 | 正确性 | a | {rel}:4 | 已修 | 改了 | 验了 | | |\n"
            f"| f-2 | 2026-09-27 | 中 | P1 | 正确性 | b | {rel}:25 | 待修 | 待处置 | | | |\n",
            encoding="utf-8")

    ws = tmp_path / "ws"
    bundle = tmp_path / "b"
    _mk(ws, bundle)
    import subprocess as _sp

    for argv in (["init", "-q"], ["add", "-A"],
                 ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"]):
        _sp.run(["git", *argv], cwd=ws, check=True, capture_output=True)     # apply 需要 git 仓
    r = ab.consume(ws, bundle, expect_input=str(ws))
    assert r["ok"], r
    text = (ws / "src" / "big.py").read_text(encoding="utf-8")
    assert "fixed_A = True" in text, text          # 第 1 段（已修）**照落**
    assert "fixed_B = True" not in text, text      # 第 2 段（未关项）被剔掉
    assert r["unclosed_hunks"] == {"src/big.py": [25]}, r["unclosed_hunks"]


def test_landing_policy_belongs_to_the_caller(tmp_path):
    """落地策略**归调用方**（声明面 `k3dit_landing` / CLI `--landing`）：k3ge 只执行、不自己拍。

    `closed-only`＝未关项不落；`partial`（默认）＝只剔未关项那些 hunk；`all`＝全落但行上标升级（封板仍被挡）。
    """
    ws = _repo(tmp_path / "a")
    b = _bundle(tmp_path / "a" / "b", status="partial")
    r = ab.consume(ws, b, landing="closed-only")
    assert r["ok"] is False and "closed-only" in r["detail"], r
    ws2 = _repo(tmp_path / "c")
    b2 = _bundle(tmp_path / "c" / "b", status="partial")
    r2 = ab.consume(ws2, b2, landing="all")
    assert r2["ok"] and r2["escalated"] == ["code-1"] and r2["unclosed_hunks"] == {}, r2
    assert "src/a.py" in (r2["apply"].get("files") or []), r2["apply"]      # all ⇒ 全落
    assert "added_by_fix = True" in (ws2 / "src" / "a.py").read_text(encoding="utf-8")  # all ⇒ 未关项也照落
    assert ab.consume(ws, b, landing="weird")["error"] == "BAD_LANDING"


def test_patch_with_escaping_path_is_refused_before_apply(tmp_path, monkeypatch):
    """code-2（报告）：补丁目标路径越出 target（绝对 / `..` / 盘符）⇒ **先拒**（`APPLY_PATH_ESCAPE`），
    不再让 `git apply` 的 APPLY_* 错误码替我们说话。"""
    ws = _repo(tmp_path)
    b = _bundle(tmp_path / "esc")
    (b / "fix.patch").write_text("--- a/../evil.py\n+++ b/../evil.py\n@@ -1 +1 @@\n-x\n+y\n", encoding="utf-8")
    r = ab.apply_bundle(ws, b)
    assert r["ok"] is False and r["error"].startswith("APPLY_PATH_ESCAPE"), r
    assert "evil.py" in r["detail"], r


def test_files_come_from_the_patch_not_from_the_whole_worktree(tmp_path):
    """code-3（报告）：`files`＝**补丁声明的 rel**；工作树上的其它改动（在途文件/构建产物）不得
    被当成审计产物交给 `commit_applied`。"""
    ws = _repo(tmp_path)
    (ws / "stray.txt").write_text("x\n", encoding="utf-8")          # 在途改动（未跟踪）
    b = _bundle(tmp_path)
    r = ab.apply_bundle(ws, b, allow_dirty=True)
    assert r["ok"], r
    assert r["files"] == ["src/a.py"], r["files"]                   # 只报补丁声明的文件


def test_tree_moved_between_dry_run_and_apply_is_refused(tmp_path, monkeypatch):
    """code-1（报告）：dry-run 与真打之间 HEAD/工作树被挪动 ⇒ `TREE_MOVED`（不真打）。"""
    ws = _repo(tmp_path)
    b = _bundle(tmp_path)

    def _dry(w, bundle, order):
        (w / "src" / "a.py").write_text("x = 1\ny = 2\nconcurrent = True\n", encoding="utf-8")   # 模拟并发改动
        return {"ok": True, "files": ["src/a.py"], "applied": order}

    monkeypatch.setattr(ab, "_dry_run_via_worktree", _dry)
    r = ab.apply_bundle(ws, b)
    assert r["ok"] is False and r["error"] == "TREE_MOVED", r
    assert "concurrent = True" in (ws / "src" / "a.py").read_text(encoding="utf-8")   # 没被真打


def test_half_applied_patches_are_rolled_back_before_merge_fallback(tmp_path, monkeypatch):
    """code-7/10（报告）：真打时第 1 条已落、第 2 条失败 ⇒ **先逆序回滚**再降级合并；
    失败面必须带真实 `applied`/`rolled_back`（不许硬编码空列表）。
    （失败若发生在 dry-run，树上什么都没落 ⇒ 这条要走"dry-run 过、真打半落"的路径来验。）
    """
    import subprocess as _sp

    ws = _repo(tmp_path)
    b = _bundle(tmp_path)

    def _dry(w, bundle, order):
        return {"ok": True, "files": ["src/a.py"], "applied": order}

    def _half(ws_, bundle, order):
        _sp.run(["git", "-C", str(ws_), "apply", str(bundle / "fix.patch")], check=True, capture_output=True)
        return {"ok": False, "error": "APPLY_FAILED:pins.patch", "applied": ["fix.patch"], "detail": "boom"}

    monkeypatch.setattr(ab, "_dry_run_via_worktree", _dry)
    monkeypatch.setattr(ab, "_apply_sequential", _half)
    # 让**合并兜底也失败**（否则它会干净合上、ok=True ⇒ 看不到回滚的效果）⇒ 走失败面看真实账
    monkeypatch.setattr(ab, "_apply_sequential_merged",
                        lambda *a, **k: {"ok": False, "error": "MERGE_FAILED", "detail": "stub", "conflicts": []})
    r = ab.apply_bundle(ws, b)
    assert r["ok"] is False, r
    assert r["applied"] == ["fix.patch"] and r["rolled_back"] == ["fix.patch"], r
    assert "added_by_fix" not in (ws / "src" / "a.py").read_text(encoding="utf-8"), "半落必须回滚干净"


def test_tool_state_root_is_hardened_and_refuses_symlink(tmp_path, monkeypatch):
    """code-9（报告）：工具状态目录可被环境劫持 ⇒ `mkdir 0700`、拒符号链接、拒非目录；不安全就**别放子进程**。"""
    ok = tmp_path / "state"
    assert ab._harden_state_root(ok) == "" and (ok.stat().st_mode & 0o777) == 0o700
    (tmp_path / "real").mkdir()
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "real")
    assert "符号链接" in ab._harden_state_root(link), ab._harden_state_root(link)
    monkeypatch.setenv("K3GE_AUDIT_CACHE", str(tmp_path / "cache"))
    monkeypatch.setattr(ab, "_harden_state_root", lambda root: "stub: 不安全")
    env = ab._tool_env(tmp_path, [str(tmp_path / "k3dit")])
    assert "K3GE_STATE_UNSAFE" in env and "K3DIT_HALL_ROOT" not in env, env
    r = ab.run_path_audit(tmp_path, tmp_path / "out", k3dit=["k3dit"])
    assert r["ok"] is False and "状态目录不安全" in r["detail"], r


def test_land_report_collects_only_its_own_projection_roots(tmp_path, monkeypatch):
    """value-10（报告）：落报告提交的"本轮产物"**显式化**——只认 `docs/generated` 与 `docs/specs`，
    不盲扫整个 `docs/`（否则会把别人的在途文档改动卷进审计提交）。"""
    from k3dge.engine import doc_catalog

    ws = _repo(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    (out / "report.md").write_text("# 审计\n", encoding="utf-8")
    (ws / "docs" / "generated").mkdir(parents=True, exist_ok=True)
    (ws / "docs" / "generated" / "api.md").write_text("api\n", encoding="utf-8")
    (ws / "docs" / "stray.md").write_text("stray\n", encoding="utf-8")      # 别人的在途文档（未跟踪）
    monkeypatch.setattr(doc_catalog, "write_docs_index", lambda w: (ws / "docs" / "generated" / "docs-index.json"))
    (ws / "docs" / "generated" / "docs-index.json").write_text("{}\n", encoding="utf-8")
    seen = {}
    monkeypatch.setattr(ab, "commit_applied",
                        lambda w, m, f: (seen.update(files=list(f)) or ("a" * 40, "")))
    monkeypatch.setattr(ab, "write_run_digest", lambda *a, **k: "")
    r = ab.land_report(ws, "M1", out)
    assert r["ok"], r
    assert "docs/generated/api.md" in seen["files"], seen["files"]
    assert not any(f.startswith("docs/stray") for f in seen["files"]), seen["files"]


def test_bundle_input_matches_accepts_full_mode_stage(tmp_path, monkeypatch):
    """`INPUT_MISMATCH` 修复：`full` 模式 k3dit 把被审仓 stage 成 `<state>/hall/run/<job>/stage`，
    它与 workspace **同一身份**（state 根按 realpath 确定性生成）⇒ 该认；别处的 stage 仍拒。"""
    monkeypatch.setenv("K3GE_AUDIT_CACHE", str(tmp_path / "cache"))
    ws = tmp_path / "ws"
    ws.mkdir()
    stage = ab.tool_state_dir(ws) / "hall" / "run" / "job1" / "stage"
    assert ab.bundle_input_matches(str(ws), str(ws)) is True                 # (a) realpath 相等
    assert ab.bundle_input_matches(str(stage), str(ws)) is True             # (b) 本仓 stage 副本
    foreign = tmp_path / "cache" / "k3dit-state-DEADBEEF0000" / "hall" / "run" / "j" / "stage"
    assert ab.bundle_input_matches(str(foreign), str(ws)) is False          # 错 key（别的仓）的 stage
    assert ab.bundle_input_matches("/tmp/elsewhere/stage", str(ws)) is False  # 仓外
    # 本 state 根下但**不是** hall/run/<job>/stage 的也算别的身份（只认 stage 这一形）
    assert ab.bundle_input_matches(str(ab.tool_state_dir(ws) / "ledger"), str(ws)) is False


def test_consume_accepts_bundle_recorded_against_stage(tmp_path, monkeypatch):
    """回归：包 `manifest.input` 记成 stage 副本时，consume 不该再以 `INPUT_MISMATCH` 拒
    （此前 full 模式自产包**永远**过不了这道守卫 ⇒ 封版停在消费步）。"""
    monkeypatch.setenv("K3GE_AUDIT_CACHE", str(tmp_path / "cache"))
    ws = tmp_path / "ws"
    ws.mkdir()
    bundle = _bundle(tmp_path)                                              # 结构完整的合成闭包
    man = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    stage = ab.tool_state_dir(ws) / "hall" / "run" / "j1" / "stage"
    man["input"] = str(stage)
    (bundle / "manifest.json").write_text(json.dumps(man, ensure_ascii=False), encoding="utf-8")
    r = ab.consume(ws, bundle, expect_input=str(ws))
    assert r.get("error") != "INPUT_MISMATCH", r


def test_bundle_leg_success_returns_audited_not_audit_noop(tmp_path, monkeypatch):
    """bundle 腿闭环后必须返回 `audited`（ocr-008）：否则掉进 oneshot 的 `audit_noop`
    （"声明面无 produce 步 ⇒ 一次都没跑"）把已闭环的边界误判成 refused。"""
    from k3dge.engine import milestone_audit as ma

    ws = _repo(tmp_path)
    (ws / ".agent").mkdir(exist_ok=True)
    (ws / ".agent" / "pipeline.toml").write_text(
        '[roles.audit]\nbind = "k3dit"\nmode = "bundle"\n', encoding="utf-8")
    monkeypatch.setattr(ma, "_bundle_audit_leg", lambda *a, **k: (None, "closed!"))
    status, msg = ma.run_audit_flow(ws, "M1", prompter=ma._Prompt.default())
    assert status == "audited", (status, msg)
    assert "audit_noop" not in msg


def test_cli_command_quotes_substituted_values():
    """`{path}` 等插值经 `shell=True` 执行 ⇒ 值必须引号化（防裂参/命令注入，code-10）。"""
    from k3dge.engine.pipeline_runner import _cli_command

    out = _cli_command("k3dit audit --verify {bundle}", {"bundle": "/tmp/a b; rm -rf x"})
    assert out == "k3dit audit --verify '/tmp/a b; rm -rf x'"


def test_dry_run_worktree_failure_cleans_tempdir(tmp_path, monkeypatch) -> None:
    """`worktree add` 失败的早退发生在 try/finally 之前 ⇒ mkdtemp 的目录永久残留（395）。"""
    import tempfile as _tf

    from k3dge.engine import audit_bundle as ab

    real_mkdtemp = _tf.mkdtemp
    made: list = []

    def spy(*a, **k):
        d = real_mkdtemp(*a, **k)
        made.append(d)
        return d

    monkeypatch.setattr(_tf, "mkdtemp", spy)
    monkeypatch.setattr(ab, "_git", lambda *a, **k: (128, "fatal: not a git repository"))
    res = ab._dry_run_via_worktree(tmp_path, tmp_path / "bundle", ["fix.patch"])
    assert res["ok"] is False and res["error"] == "WORKTREE_UNAVAILABLE"
    from pathlib import Path as _P

    assert not [d for d in made if _P(d).exists()], "临时目录没被清"


def test_audit_flow_has_no_dead_audit_surface() -> None:
    """两态 verb 退休后留下的死件不得复活（397/398）。"""
    from k3dge.engine import audit_flow

    assert not hasattr(audit_flow, "_count_status")
    assert not hasattr(audit_flow, "_REPORT_HEADER_TOKEN")


def test_repo_gitignore_covers_both_runtime_projections():
    """决策的钉子：`audit_jobs.json` 与 `audit_checklist.json` 都不许再入库（ADR-0004 §2.1.10）。"""
    import subprocess
    import tempfile

    repo = Path(__file__).resolve().parents[3]
    with tempfile.TemporaryDirectory() as d:
        for rel in (".agent/audit_jobs.json", ".agent/audit_checklist.json"):
            f = Path(d) / "probe"
            f.parent.mkdir(exist_ok=True)
            r = subprocess.run(["git", "-C", str(repo), "check-ignore", "-q", "--", rel],
                               capture_output=True, text=True)
            assert r.returncode == 0, f"{rel} 未被 .gitignore 覆盖 ⇒ 审计一跑就会弄脏工作树"
def test_dummy_peer_state_and_report_shape(tmp_path, monkeypatch) -> None:
    """dummy peer 桩自身的三条不变量（t-013/014/015）——它是"对端契约"的替身，桩不可信则开环/闭环两态的验证全无意义。"""
    import importlib.util
    import json as _json
    import sys

    import pytest

    src = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "dummy_peer.py"

    def load(tag: str):
        spec = importlib.util.spec_from_file_location(f"dummy_peer_{tag}", src)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f"dummy_peer_{tag}"] = mod
        spec.loader.exec_module(mod)
        return mod

    # ① 状态路径可显式覆盖；缺省时按**检出**派生（不再全机共用一个固定名）
    monkeypatch.setenv("DUMMY_PEER_STATE", str(tmp_path / "jobs.json"))
    m = load("a")
    assert str(m._STATE_FILE) == str(tmp_path / "jobs.json")
    monkeypatch.delenv("DUMMY_PEER_STATE")
    m2 = load("b")
    assert m2._STATE_FILE.name.startswith("k3dge_dummy_peer_jobs-") and m2._STATE_FILE != m._STATE_FILE

    # ② 畸形 DUMMY_PENDING ⇒ 入口式 BAD_CONFIG（旧写法在工具内部抛 ValueError，
    #    而文档说的"默认 0"只在变量缺失时生效）
    monkeypatch.setenv("DUMMY_PENDING", " ")          # 空/纯空白＝视作未设（回落 0）
    assert _json.loads(m2.dummy_submit(baseline="b" * 40))["ok"]
    monkeypatch.setenv("DUMMY_PENDING", "abc")
    job = _json.loads(m2.dummy_submit(baseline="a" * 40, milestone_id="M9"))
    assert job["ok"]
    bad = _json.loads(m2.dummy_collect(job["payload"]["job_id"]))
    assert bad["ok"] is False and bad["error"] == "BAD_CONFIG", bad

    # ③ 报告里**只有一条** `- **基线**:`，且值＝submit 传真值（旧桩又拼一条 40 个 0）
    monkeypatch.setenv("DUMMY_PENDING", "1")
    ok = _json.loads(m2.dummy_collect(job["payload"]["job_id"]))
    md = ok["payload"]["report_markdown"]
    assert ok["ok"] and md.count("- **基线**:") == 1, md
    assert "aaaa" in md and "0000" not in md.split("- **基线**:")[1].splitlines()[0]
    assert md.count("| D1 ") == 1                       # 开环态真产出一条待修

    # ④ 状态文件是符号链接 ⇒ 拒用（不顺着它把账本写到别处）
    link = tmp_path / "linked.json"
    link.symlink_to(tmp_path / "elsewhere.json")
    monkeypatch.setenv("DUMMY_PEER_STATE", str(link))
    with pytest.raises(RuntimeError, match="符号链接"):
        load("c")._load_jobs()
