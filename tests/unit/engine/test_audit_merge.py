"""三路合并落补丁：包是对**审计当时基线**生成的，主干前进后 `git apply` 会冲突 ⇒ 走 base/theirs/ours 合并。

真跑出处（2026-09-27）：旧包 `fix.patch` 在 `flowlint.py:162` 冲突（我们后来往该文件落了 14 枚钉）⇒
只会 `git apply` 时整包落不下、24 条修复全废。合并要能：① 钉与修复不重叠时自动合；② 真重叠时**如实报冲突**；
③ 显式排除某些文件（不做猜测）。
"""

from pathlib import Path

from k3dge.engine import audit_merge as am

from .test_audit_verify import make_bundle


def _ws(tmp: Path, text: str) -> Path:
    ws = tmp / "ws"
    (ws / "src").mkdir(parents=True)
    (ws / "src" / "a.py").write_text(text, encoding="utf-8")
    return ws


def test_merge_applies_fix_when_trunk_only_added_pins(tmp_path):
    """主干只多了钉行（我们落的标记）＋修复改代码行 ⇒ **不重叠 ⇒ 自动合**（这正是真跑的形状）。"""
    b = make_bundle(tmp_path)
    ws = _ws(tmp_path, "# k3dit:pending old-1 我们后落的钉\nx = 1\ny = 2\n")   # 钉在前，代码行未动
    res = am.merge_into(ws, b)
    assert res["ok"], res
    text = res["merged"]["src/a.py"]
    assert "# k3dit:pending old-1" in text          # 我们的钉保住
    assert "added_by_fix = True" in text            # 审计的**修复**合进来
    assert res["pins_patch"] == "pins.patch"        # 钉那层由调用方正向应用（失败则并集）
    assert "<<<<<<<" not in text
    # 钉层并集：两边各有一枚钉 ⇒ 两枚都留（`union_pins`）
    u = am.union_pins(ws, b, "src/a.py")
    assert u["ok"] and "# k3dit:pending old-1" in u["text"] and "# k3dit:fixed code-1" in u["text"], u


def test_merge_reports_real_conflict(tmp_path):
    """主干改了**同一行**（`y = 2` → `y = 99`）而修复也改了该区域 ⇒ 报冲突、不猜。"""
    b = make_bundle(tmp_path)
    ws = _ws(tmp_path, "x = 1\ny = 99\n")
    res = am.merge_into(ws, b)
    assert not res["ok"] and res["conflicts"] == ["src/a.py"], res
    assert res["merged"] == {} or "src/a.py" not in res["merged"]


def test_merge_excludes_files_explicitly(tmp_path):
    """`exclude` 是**显式的**（例如"这条修复与现测试期望冲突"）：被排除的文件不进合并结果。"""
    b = make_bundle(tmp_path)
    ws = _ws(tmp_path, "x = 1\ny = 2\n")
    res = am.merge_into(ws, b, exclude=["src/a.py"])
    assert res["ok"] and res["merged"] == {} and res["excluded"] == ["src/a.py"], res


def test_touched_files_reads_both_patches(tmp_path):
    b = make_bundle(tmp_path)
    assert am.touched_files(b) == {"src/a.py"}


def test_merge_file_rc_is_conflict_count_not_error(tmp_path):
    """`git merge-file` 返回码＝**冲突个数**：一处文件里有两处冲突时 rc=2，**不是**"合并失败"。

    真跑实测：把 `>1` 当错误 ⇒ 真包的 `audit_bundle.py`（2 处冲突）被判"合并失败"（detail 空），
    排查方向跑偏。用例：两个改动区都冲突 ⇒ 仍必须报 `conflicts=[rel]`。
    """
    ws = tmp_path / "ws"
    b = tmp_path / "b"
    rel = "src/c.py"
    base = "".join(f"l{i}\n" for i in range(1, 21))
    # **两侧改同一行**（两处）才会真冲突：相邻插入是能干净合上的（夹具第一版就造错了）
    ours = base.replace("l3\n", "ours_A\n").replace("l15\n", "ours_B\n")
    theirs = base.replace("l3\n", "theirs_A\n").replace("l15\n", "theirs_B\n")
    for root, text in ((ws, ours), (b / "code", theirs)):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    (b / "baseline.json").write_text(__import__("json").dumps(
        {"files": {rel: __import__("hashlib").sha1(base.encode()).hexdigest()}, "tree_hash": "x", "count": 1}),
        encoding="utf-8")
    (b / "manifest.json").write_text(__import__("json").dumps(
        {"bundle_version": 1, "apply_order": ["fix.patch"], "pins": {"in_code": True}}), encoding="utf-8")
    import difflib

    (b / "fix.patch").write_text("".join(difflib.unified_diff(
        base.splitlines(keepends=True), theirs.splitlines(keepends=True),
        fromfile=f"a/{rel}", tofile=f"b/{rel}")), encoding="utf-8")
    r = am.merge_into(ws, b)
    assert r["ok"] is False and r["conflicts"] == [rel], r        # 冲突（不是 MERGE_FAILED 那一类）


def test_hunks_multi_file_boundary():
    """`_hunks` 不得把下一文件的 `--- a/` 头吞进上一 hunk（ocr-048）。"""

    patch = (
        "diff --git a/x.py b/x.py\n"
        "--- a/x.py\n"
        "+++ b/x.py\n"
        "@@ -1,2 +1,2 @@\n"
        " a\n"
        "-b\n"
        "+B\n"
        "diff --git a/y.py b/y.py\n"
        "--- a/y.py\n"
        "+++ b/y.py\n"
        "@@ -5,1 +5,1 @@\n"
        "-c\n"
        "+C\n"
    )
    h = am._hunks(patch)
    assert set(h) == {"x.py", "y.py"}
    assert len(h["x.py"]) == 1 and len(h["y.py"]) == 1
    assert not any("y.py" in ln for ln in h["x.py"][0]["lines"])
    assert all(not ln.startswith("--- a/") for ln in h["x.py"][0]["lines"])


def test_fail_channel_matches_success_shape() -> None:
    """失败面必须与成功面同键，否则新调用方 KeyError（399）。"""
    from k3dge.engine.audit_merge import _fail

    got = _fail("x")
    for key in ("ok", "merged", "conflicts", "missing", "pins_rels", "pins_patch",
                "excluded", "detail"):
        assert key in got, key


def test_missing_files_reach_the_detail(tmp_path, monkeypatch) -> None:
    """主干缺文件过去只在 `missing` 里、detail 空串 ⇒ 落盘方一句话都拼不出（400）。"""

    bundle = tmp_path / "bundle"
    (bundle / "pins").mkdir(parents=True)
    (tmp_path / "base").mkdir()
    (bundle / "manifest.json").write_text(
        '{"bundle_version":"1","apply_order":["fix.patch"],"pins":{"in_code":false}}',
        encoding="utf-8")
    (bundle / "fix.patch").write_text("not a real patch\n", encoding="utf-8")
    monkeypatch.setattr(am, "_owned_replay",
                        lambda b, **k: {"ok": True, "root": str(tmp_path / "base")})
    monkeypatch.setattr(am, "patch_rels",
                        lambda b, name: {"gone.py"} if name == "fix.patch" else set())
    (tmp_path / "base" / "gone.py").write_text("x\n", encoding="utf-8")   # base 有、主干没有
    res = am.merge_into(tmp_path, bundle)
    assert res["missing"] == ["gone.py"], res
    assert "主干缺文件" in res["detail"], res
