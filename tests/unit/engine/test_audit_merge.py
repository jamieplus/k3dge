"""三路合并落补丁：包是对**审计当时基线**生成的，主干前进后 `git apply` 会冲突 ⇒ 走 base/theirs/ours 合并。

真跑出处（2026-09-27）：旧包 `fix.patch` 在 `flowlint.py:162` 冲突（我们后来往该文件落了 14 枚钉）⇒
只会 `git apply` 时整包落不下、24 条修复全废。合并要能：① 钉与修复不重叠时自动合；② 真重叠时**如实报冲突**；
③ 显式排除某些文件（不做猜测）。
"""
from __future__ import annotations

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
