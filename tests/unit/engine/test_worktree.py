"""⑦ 进程件：ensure 幂等 / present 抽取 / advance 提交 / 非 ff 拒绝。"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from k3dge.engine import worktree as W


def _repo(tmp_path: Path) -> Path:
    def g(*a):
        subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True,
                       env={"PATH": "/usr/bin:/bin", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t", "HOME": str(tmp_path)})
    subprocess.run(["git", "init", "-qb", "main", str(tmp_path)], check=True, capture_output=True)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "m.py").write_text("def f():\n    # k3dit:pending A-1 x\n    return 1\n", encoding="utf-8")
    (tmp_path / "clash.py").write_text("shared = 0\n", encoding="utf-8")
    g("add", "-A"); g("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base")
    return tmp_path


def test_ensure_present_advance(tmp_path):
    ws = _repo(tmp_path)
    wt = W.ensure(ws, "J1")
    assert wt.is_dir() and W.ensure(ws, "J1") == wt          # 幂等
    pre = W.present(ws, "J1")
    assert [p["id"] for p in pre] == ["A-1"]
    (wt / "src" / "m.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    head = W.advance(ws, "J1")
    assert head and head == subprocess.run(["git", "rev-parse", "k3dit/J1"], cwd=ws, capture_output=True, text=True).stdout.strip()
    assert W.present(ws, "J1") == []                          # vanished 原料就位


def test_non_ff_rejected(tmp_path):
    ws = _repo(tmp_path)
    wt = W.ensure(ws, "J1")
    (wt / "a.py").write_text("q = 2\n", encoding="utf-8")          # 本地未提交 → advance 会先 commit
    # 模拟"他方"：用一次性 worktree（独立分支）在别处提交后，把 k3dit/J1 强推到那个头
    other = tmp_path / "other"
    r = subprocess.run(["git", "worktree", "add", "-b", "elsewhere", str(other), "k3dit/J1"],
                       cwd=ws, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    (other / "theirs.py").write_text("z = 1\n", encoding="utf-8")
    for a in (["add", "-A"], ["-c", "user.name=x", "-c", "user.email=x@x", "commit", "-qm", "theirs"]):
        assert subprocess.run(["git", *a], cwd=other, capture_output=True, text=True).returncode == 0
    theirs = subprocess.run(["git", "rev-parse", "HEAD"], cwd=other, capture_output=True, text=True).stdout.strip()
    subprocess.run(["git", "update-ref", "refs/heads/k3dit/J1", theirs], cwd=ws, check=True)
    # worktree 留在旧检出但已提交过一次 ⇒ head 与分支互不为祖先 = 真分叉
    (wt / "conflict.py").write_text("c = 1\n", encoding="utf-8")
    subprocess.run(["git", "checkout", "-q", "--detach", "HEAD@{1}"], cwd=wt, capture_output=True)
    with pytest.raises(RuntimeError, match="non-fast-forward"):
        W.advance(ws, "J1")


def _commit_on_branch(ws, path, content):
    import subprocess
    wt = W.worktree_path(ws, "J1")
    (wt / path).parent.mkdir(parents=True, exist_ok=True)
    (wt / path).write_text(content, encoding="utf-8")
    return W.advance(ws, "J1")


def test_merge_back_ff_and_conflict(tmp_path):
    ws = _repo(tmp_path)
    W.ensure(ws, "J1")
    _commit_on_branch(ws, "extra.py", "e = 1\n")
    r = W.merge_back(ws, "J1")
    assert r["ok"] and r["mode"] == "ff"
    assert (ws / "extra.py").exists()                          # 修的东西回到主干
    # 冲突：双方修改共同祖先里同一文件（真 merge 冲突路径）
    (ws / "clash.py").write_text("main = 1\n", encoding="utf-8")
    import subprocess
    subprocess.run(["git", "add", "-A"], cwd=ws, check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "main side"],
                   cwd=ws, check=True, capture_output=True)
    _commit_on_branch(ws, "clash.py", "branch = 2\n")
    c = W.merge_back(ws, "J1")
    assert not c["ok"] and c["mode"] == "conflict" and "人工" in c["message"]
    assert subprocess.run(["git", "status", "--porcelain"], cwd=ws, capture_output=True,
                          text=True).stdout.strip() == ""     # merge --abort 干净退出


def test_merge_back_rebase_when_main_moved(tmp_path):
    # 主干在 L 之后先走一步（无冲突）⇒ 线重演到主干头再 ff，无 merge 提交
    ws = _repo(tmp_path)
    W.ensure(ws, "J1")
    _commit_on_branch(ws, "line.py", "l = 1\n")
    (ws / "main.py").write_text("m = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=ws, check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "main moved"],
                   cwd=ws, check=True, capture_output=True)
    r = W.merge_back(ws, "J1")
    assert r["ok"] and r["mode"] == "rebase", r
    assert (ws / "line.py").exists() and (ws / "main.py").exists()
    log = subprocess.run(["git", "log", "--oneline"], cwd=ws, capture_output=True, text=True).stdout
    assert "merge" not in log.lower()  # 线性史，无 merge 提交
    out = W.prune(ws, "J1")            # 已并入 ⇒ 删现场删线
    assert not W.worktree_path(ws, "J1").exists()
    assert "branch:k3dit/J1" in out["removed"]


def test_merge_back_dirty_tree_refuses(tmp_path):
    ws = _repo(tmp_path)
    W.ensure(ws, "J1")
    _commit_on_branch(ws, "b.py", "x = 1\n")
    (ws / "dirty.py").write_text("uncommitted\n", encoding="utf-8")
    r = W.merge_back(ws, "J1")
    assert not r["ok"] and r["mode"] == "dirty"


def test_materialize_readonly_snapshot(tmp_path):
    ws = _repo(tmp_path)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ws,
                          capture_output=True, text=True).stdout.strip()
    dest = tmp_path / "mat"
    out = W.materialize(ws, head, dest)
    assert out == dest and (dest / "src" / "m.py").is_file()
    assert not (dest / ".git").exists()                            # 纯内容，无库
    assert subprocess.run(["git", "worktree", "list"], cwd=ws,
                          capture_output=True, text=True).stdout.strip().count("\n") == 0  # 无新 worktree 登记
    assert subprocess.run(["git", "rev-parse", "HEAD"], cwd=ws,
                          capture_output=True, text=True).stdout.strip() == head
    with pytest.raises(RuntimeError, match="未知版本"):
        W.materialize(ws, "0" * 40, tmp_path / "mat2")


def test_prune_keeps_unmerged_line_deletes_merged(tmp_path):
    ws = _repo(tmp_path)
    W.ensure(ws, "J1")
    _commit_on_branch(ws, "keep.py", "k = 1\n")
    out = W.prune(ws, "J1")                                    # 未并入 ⇒ 线保留原位
    assert not W.worktree_path(ws, "J1").exists()
    assert "branch:k3dit/J1" not in out["removed"]
    assert subprocess.run(["git", "rev-parse", "--verify", "-q", "refs/heads/k3dit/J1"],
                          cwd=ws, capture_output=True).returncode == 0
    W.merge_back(ws, "J1")                                     # 闸过合主干
    out = W.prune(ws, "J1")                                    # 然后删线
    assert "branch:k3dit/J1" in out["removed"]
    assert subprocess.run(["git", "rev-parse", "--verify", "-q", "refs/heads/k3dit/J1"],
                          cwd=ws, capture_output=True).returncode != 0


def test_strip_pins_full_line_only(tmp_path):
    ws = _repo(tmp_path)
    wt = W.ensure(ws, "J9")
    (wt / "src" / "m.py").write_text(
        "def f():\n    # k3dit:pending A-1 x\n    return 1\n", encoding="utf-8")
    (wt / "note.md").write_text("# t\n<!-- k3dit:fixnote F-2 -->\n", encoding="utf-8")
    (wt / "keep.py").write_text("y = 2  # k3dit:pending T-3 trailing\n", encoding="utf-8")
    out = W.strip_pins(ws, "J9")
    assert out["stripped_lines"] == 2 and len(out["stripped_files"]) == 2
    assert out["suspicious"] == ["keep.py:1"]            # 行尾钉不动，只上报
    assert "# k3dit" not in (wt / "src" / "m.py").read_text(encoding="utf-8")
    assert "y = 2" in (wt / "keep.py").read_text(encoding="utf-8")
    again = W.strip_pins(ws, "J9")
    assert again["stripped_lines"] == 0                  # 幂等


def test_merge_back_strips_before_ff(tmp_path):
    ws = _repo(tmp_path)
    W.ensure(ws, "J9")
    wt = W.worktree_path(ws, "J9")
    (wt / "src" / "m.py").write_text(
        "def f():\n    # k3dit:pending A-1 x\n    return 2\n", encoding="utf-8")
    W.advance(ws, "J9")                                  # 钉随线提交
    r = W.merge_back(ws, "J9")
    assert r["ok"] and r["mode"] == "ff", r
    assert r["stripped"]["stripped_lines"] == 1
    assert "# k3dit" not in (ws / "src" / "m.py").read_text(encoding="utf-8")  # 主干无钉
    log = subprocess.run(["git", "log", "--oneline"], cwd=ws, capture_output=True, text=True).stdout
    assert "merge" not in log.lower()
