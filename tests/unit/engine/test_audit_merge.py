"""三路合并落补丁：包是对**审计当时基线**生成的，主干前进后 `git apply` 会冲突 ⇒ 走 base/theirs/ours 合并。

真跑出处（2026-09-27）：旧包 `fix.patch` 在 `flowlint.py:162` 冲突（我们后来往该文件落了 14 枚钉）⇒
只会 `git apply` 时整包落不下、24 条修复全废。合并要能：① 钉与修复不重叠时自动合；② 真重叠时**如实报冲突**；
③ 显式排除某些文件（不做猜测）。
"""

import difflib
import hashlib
import json
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
    # ocr2-723：旧析取后半恒真（前半 ⇒ 后半），"无部分合并"一半永不独立失败。直接断言空合并。
    assert res["merged"] == {}, res


def test_merge_excludes_files_explicitly(tmp_path):
    """`exclude` 是**显式的**（例如"这条修复与现测试期望冲突"）：被排除的文件不进合并结果。"""
    b = make_bundle(tmp_path)
    ws = _ws(tmp_path, "x = 1\ny = 2\n")
    res = am.merge_into(ws, b, exclude=["src/a.py"])
    assert res["ok"] and res["merged"] == {} and res["excluded"] == ["src/a.py"], res


def test_touched_files_reads_both_patches(tmp_path) -> None:
    """"两份的并集"只有**两层摸不同文件**才测得到（t-088）。

    `make_bundle` 的 fix.patch 与 pins.patch 都指 `src/a.py`——摘掉 pins 那一项，
    并集结果不变、本测照绿。手工两份不同文件的补丁，缺哪层都红。
    """
    b = tmp_path / "b"
    b.mkdir()
    (b / "fix.patch").write_text(
        "--- a/src/a.py\n+++ b/src/a.py\n@@ -1 +1 @@\n-x\n+y\n", encoding="utf-8")
    (b / "pins.patch").write_text(
        "--- a/docs/x.md\n+++ b/docs/x.md\n@@ -1 +1 @@\n-a\n+b\n", encoding="utf-8")
    assert am.touched_files(b) == {"src/a.py", "docs/x.md"}
    # 旧夹具的同文件形状仍在（回归对照）
    assert am.touched_files(make_bundle(tmp_path / "mb")) == {"src/a.py"}


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
    (b / "baseline.json").write_text(json.dumps(
        {"files": {rel: hashlib.sha1(base.encode()).hexdigest()}, "tree_hash": "x", "count": 1}),
        encoding="utf-8")
    (b / "manifest.json").write_text(json.dumps(
        {"bundle_version": 1, "apply_order": ["fix.patch"], "pins": {"in_code": True}}), encoding="utf-8")
    (b / "fix.patch").write_text("".join(difflib.unified_diff(
        base.splitlines(keepends=True), theirs.splitlines(keepends=True),
        fromfile=f"a/{rel}", tofile=f"b/{rel}")), encoding="utf-8")
    # ocr2-437：必须证明夹具真造出 **>1 处冲突**（rc=2 形状）——否则夹具漂成单处冲突时
    # 本测仍绿，`1 <= rc <= 127` 这条语义其实没被覆盖。
    base_file = tmp_path / "base_c.py"
    base_file.write_text(base, encoding="utf-8")
    m = am._merge_file(ws / rel, base_file, b / "code" / rel)
    assert m["conflict"] and m["conflicts"] > 1, m
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


def test_fail_channel_matches_success_shape(tmp_path) -> None:
    """失败面必须与成功面同键，否则新调用方 KeyError（399）。

    判据从**真成功合并的键集**推导（t-089）：手抄的键清单只验证"`_fail` 和它自己
    一致"——成功面哪天加一个键，本测（该防的漂移恰恰是这个）照样绿。
    字面清单降级为"下限说明"保留。
    """
    from k3dge.engine.audit_merge import _fail

    b = make_bundle(tmp_path)
    ws = _ws(tmp_path, "# k3dit:pending old-1 钉\nx = 1\ny = 2\n")
    ok = am.merge_into(ws, b)
    assert ok["ok"], ok
    got = _fail("x")
    missing = set(ok) - set(got)
    assert not missing, f"失败面缺成功面的键：{sorted(missing)}"
    for key in ("ok", "merged", "conflicts", "missing", "pins_rels", "pins_patch",
                "excluded", "detail"):
        assert key in got, key          # 下限（改名/删键也要有意识地过这条）


def test_missing_files_reach_the_detail(tmp_path, monkeypatch) -> None:
    """主干缺文件过去只在 `missing` 里、detail 空串 ⇒ 落盘方一句话都拼不出（400）。"""

    bundle = tmp_path / "bundle"
    bundle.mkdir(parents=True)
    # （旧行的 `(bundle / "pins").mkdir()` 是上一代包布局残渣：merge_into/replay 从不读
    #  `pins/`——换成只建包根目录，t-091。）
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
    # code-6 支路要**真被走到**（t-087）：修复侧必须有这份文件，否则循环在更早的
    # `not theirs.is_file()` 就 `missing.append` 了——断言由错误路径满足，
    # code-6（base 在、主干缺）回归检测不到。
    (bundle / "code").mkdir()
    (bundle / "code" / "gone.py").write_text("fixed\n", encoding="utf-8")
    res = am.merge_into(tmp_path, bundle)
    # ocr2-724：本分支的要点是"幻影文件不得报成功合并"——旧断言缺 ok 侧，成功/失败同脸也绿。
    assert res["ok"] is False, res
    assert res["missing"] == ["gone.py"], res
    assert "主干缺文件" in res["detail"], res
    assert (tmp_path / "gone.py").exists() is False, "主干缺文件不得被凭空写出来"


def test_theirs_missing_is_reported_separately(tmp_path, monkeypatch) -> None:
    """对照（t-087 的兄弟支路）：补丁声明了文件而包里根本没有 ⇒ 走 theirs-missing 路径。"""
    bundle = tmp_path / "bundle"
    bundle.mkdir(parents=True)
    # （旧行的 `(bundle / "pins").mkdir()` 是上一代包布局残渣：merge_into/replay 从不读
    #  `pins/`——换成只建包根目录，t-091。）
    (tmp_path / "base").mkdir()
    (bundle / "manifest.json").write_text(
        '{"bundle_version":"1","apply_order":["fix.patch"],"pins":{"in_code":false}}',
        encoding="utf-8")
    (bundle / "fix.patch").write_text("not a real patch\n", encoding="utf-8")
    monkeypatch.setattr(am, "_owned_replay",
                        lambda b, **k: {"ok": True, "root": str(tmp_path / "base")})
    monkeypatch.setattr(am, "patch_rels",
                        lambda b, name: {"ghost.py"} if name == "fix.patch" else set())
    res = am.merge_into(tmp_path, bundle)
    assert res["missing"] == ["ghost.py"], res
    # ocr2-725：只看 missing 时，"记了 missing 又写出空/合并文件"的回归照样绿——
    # 文件既不得报合并，也不得在工作区物化（与主干缺分支同契约"不静默丢修复"）。
    assert res["ok"] is False, res
    assert "ghost.py" not in res["merged"], res
    assert not (tmp_path / "ghost.py").exists(), "包里没有的文件不得被凭空写出来"


def test_union_pins_refuses_binary(tmp_path):
    """任一输入非 UTF-8（二进制）⇒ 不合，直接拒（ocr2-046）。

    `decode("replace")` + `write_text(utf-8)` 会把二进制静默改写损坏。
    """
    b = make_bundle(tmp_path)
    ws = _ws(tmp_path, "x = 1\n")
    (ws / "src" / "a.py").write_bytes(b"\xff\xfe\x00binary")
    u = am.union_pins(ws, b, "src/a.py")
    assert not u["ok"] and "非 UTF-8" in u["detail"], u


def test_manifest_non_object_fails_clear(tmp_path):
    """ocr2-211：外部包 manifest 顶层非对象 / apply_order 非列表 ⇒ 结构化拒绝，不抛 AttributeError。"""
    ws = _ws(tmp_path, "x = 1\ny = 2\n")
    b = make_bundle(tmp_path / "a")
    (b / "manifest.json").write_text('["not", "object"]', encoding="utf-8")
    res = am.merge_into(ws, b)
    assert res["ok"] is False and "顶层不是对象" in res["detail"], res
    b2 = make_bundle(tmp_path / "b")
    (b2 / "manifest.json").write_text('{"apply_order": 3, "pins": {"in_code": false}}',
                                      encoding="utf-8")
    res2 = am.merge_into(ws, b2)
    assert res2["ok"] is False and "apply_order 不是列表" in res2["detail"], res2


def test_merge_does_not_fall_back_to_pins_contaminated_code(tmp_path, monkeypatch):
    """ocr2-212：反向钉后的中间树缺文件 ⇒ 记 missing，不回落含钉的 `code/`（会重复写钉）。"""
    ws = _ws(tmp_path, "x = 1\ny = 2\n")
    bundle = make_bundle(tmp_path / "b")
    base_root = tmp_path / "base"
    (base_root / "src").mkdir(parents=True)
    (base_root / "src" / "a.py").write_text("# k3dit:pending old-1\nx = 1\ny = 2\n", encoding="utf-8")
    mid_root = tmp_path / "mid"
    mid_root.mkdir()          # 反向 pins 后 a.py 不存在
    monkeypatch.setattr(am, "_owned_replay", lambda b, **k: {"ok": True, "root": str(base_root)})
    monkeypatch.setattr(am, "replay_to_baseline", lambda b, **k: {"ok": True, "root": str(mid_root)})
    res = am.merge_into(ws, bundle)
    assert res["missing"] == ["src/a.py"], res
    assert res["merged"] == {}, res


def test_union_pins_missing_code_file_fails_clear(tmp_path):
    """ocr2-213：包 `code/` 缺 rel ⇒ `{ok:False}` 契约，不裸 FileNotFoundError。"""
    b = make_bundle(tmp_path)
    ws = _ws(tmp_path, "x = 1\ny = 2\n")
    res = am.union_pins(ws, b, "src/missing.py")
    assert res["ok"] is False and "缺该文件" in res["detail"], res
