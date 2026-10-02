"""⑦ 进程件：ensure 幂等 / present 抽取 / advance 提交 / 非 ff 拒绝。"""

import os
import subprocess
from pathlib import Path

import pytest

from k3dge.engine import worktree as W


@pytest.fixture(autouse=True)
def _isolate_git_env(tmp_path, monkeypatch):
    """全模块 git 环境隔离（t-310）：一份口径，测试侧与生产侧同时生效。

    - `GIT_CONFIG_GLOBAL=os.devnull` + `GIT_CONFIG_NOSYSTEM=1`：宿主 globalconfig
      （core.hooksPath / commit.gpgsign / alias.* / init.defaultBranch）不再左右
      断言红绿。生产 `_git` 剥 `GIT_*` 但**白名单保留这一对**，所以它包住的生产
      调用与这里的裸 subprocess 走同一形状。
    - HOME/XDG 进临时目录：兜任何 git 版本对 globalconfig 的兜底寻径，绝不碰开发者
      真 `~/.gitconfig`。
    - 身份不靠环境：`_repo` 写 repo-local `user.*`，生产提交自带 `-c`。
    """
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))


def _g(cwd: Path, *args: str) -> str:
    """断言可信的 git stdout（t-313/314）：`check=True` 让 git 的 stderr 进异常。

    裸 `.stdout.strip()` 在命令失败时回空串——把"前置条件坏了"伪装成"引擎 bug"
    （`assert <sha> == ""`），或让 `count("\\n") == 0` 在空输出上假绿。
    """
    r = subprocess.run(["git", *args], cwd=str(cwd), check=True,
                       capture_output=True, text=True)
    return r.stdout


def _grc(cwd: Path, *args: str) -> int:
    """只关心返回码的负例探测（--verify 期待失败）。"""
    return subprocess.run(["git", *args], cwd=str(cwd),
                          capture_output=True, text=True).returncode


def _repo(tmp_path: Path) -> Path:
    _g(tmp_path, "init", "-qb", "main")
    _g(tmp_path, "config", "user.name", "t")
    _g(tmp_path, "config", "user.email", "t@t")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "m.py").write_text("def f():\n    # k3dit:pending A-1 x\n    return 1\n", encoding="utf-8")
    (tmp_path / "clash.py").write_text("shared = 0\n", encoding="utf-8")
    _g(tmp_path, "add", "-A")
    _g(tmp_path, "commit", "-qm", "base")
    return tmp_path


def test_ensure_present_advance(tmp_path):
    ws = _repo(tmp_path)
    wt = W.ensure(ws, "J1")
    assert wt.is_dir() and W.ensure(ws, "J1") == wt          # 幂等
    pre = W.present(ws, "J1")
    assert [p["id"] for p in pre] == ["A-1"]
    (wt / "src" / "m.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    head = W.advance(ws, "J1")
    assert head and head == _g(ws, "rev-parse", "k3dit/J1").strip()
    assert W.present(ws, "J1") == []                          # vanished 原料就位
    from k3dge.engine.attest import verify_commit, PREFIX
    body = _g(ws, "log", "-1", "--format=%B", head)
    assert PREFIX in body
    ok, msg = verify_commit(ws, head)
    assert ok, msg


def test_non_ff_rejected(tmp_path):
    ws = _repo(tmp_path)
    wt = W.ensure(ws, "J1")
    (wt / "a.py").write_text("q = 2\n", encoding="utf-8")          # 本地未提交 → advance 会先 commit
    # 模拟"他方"：用一次性 worktree（独立分支）在别处提交后，把 k3dit/J1 强推到那个头
    other = tmp_path / "other"
    _g(ws, "worktree", "add", "-b", "elsewhere", str(other), "k3dit/J1")
    (other / "theirs.py").write_text("z = 1\n", encoding="utf-8")
    _g(other, "add", "-A")
    _g(other, "commit", "-qm", "theirs")
    theirs = _g(other, "rev-parse", "HEAD").strip()
    _g(ws, "update-ref", "refs/heads/k3dit/J1", theirs)
    # worktree 留在旧检出但已提交过一次 ⇒ head 与分支互不为祖先 = 真分叉。
    # 不能用 `HEAD@{1}`：新建的 linked worktree 的 reflog 往往只有一条、旧值是 null OID，
    # 解不出目标，且不同 git 版本行为不一（t-311）。显式取那次检出的 commit；
    # `_g` 的 check=True 保证前置造不出来时报 git 的 stderr 而不是跑到假分叉（t-313）。
    (wt / "conflict.py").write_text("c = 1\n", encoding="utf-8")
    base = _g(wt, "rev-parse", "HEAD~1").strip()
    _g(wt, "checkout", "-q", "--detach", base)
    with pytest.raises(RuntimeError, match="non-fast-forward"):
        W.advance(ws, "J1")


def _commit_on_branch(ws, path, content):
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
    _g(ws, "add", "-A")
    _g(ws, "commit", "-qm", "main side")
    _commit_on_branch(ws, "clash.py", "branch = 2\n")
    c = W.merge_back(ws, "J1")
    assert not c["ok"] and c["mode"] == "conflict" and "人工" in c["message"]
    assert _g(ws, "status", "--porcelain").strip() == ""       # merge --abort 干净退出


def test_merge_back_rebase_when_main_moved(tmp_path):
    # 主干在 L 之后先走一步（无冲突）⇒ 线重演到主干头再 ff，无 merge 提交
    ws = _repo(tmp_path)
    W.ensure(ws, "J1")
    _commit_on_branch(ws, "line.py", "l = 1\n")
    (ws / "main.py").write_text("m = 1\n", encoding="utf-8")
    _g(ws, "add", "-A")
    _g(ws, "commit", "-qm", "main moved")
    r = W.merge_back(ws, "J1")
    assert r["ok"] and r["mode"] == "rebase", r
    assert (ws / "line.py").exists() and (ws / "main.py").exists()
    assert "merge" not in _g(ws, "log", "--oneline").lower()  # 线性史，无 merge 提交
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
    head = _g(ws, "rev-parse", "HEAD").strip()   # 空串喂给 materialize 会退化成"未知版本"假象（t-314）
    dest = tmp_path / "mat"
    out = W.materialize(ws, head, dest)
    assert out == dest and (dest / "src" / "m.py").is_file()
    assert not (dest / ".git").exists()                            # 纯内容，无库
    listing = _g(ws, "worktree", "list")
    assert listing.strip(), "worktree list 返回空——命令没跑成，'无新登记'的断言就成了 vacuous"
    assert listing.strip().count("\n") == 0                         # 无新 worktree 登记
    assert _g(ws, "rev-parse", "HEAD").strip() == head
    with pytest.raises(RuntimeError, match="未知版本"):
        W.materialize(ws, "0" * 40, tmp_path / "mat2")


def test_prune_keeps_unmerged_line_deletes_merged(tmp_path):
    ws = _repo(tmp_path)
    W.ensure(ws, "J1")
    _commit_on_branch(ws, "keep.py", "k = 1\n")
    out = W.prune(ws, "J1")                                    # 未并入 ⇒ 线保留原位
    assert not W.worktree_path(ws, "J1").exists()
    assert "branch:k3dit/J1" not in out["removed"]
    assert _grc(ws, "rev-parse", "--verify", "-q", "refs/heads/k3dit/J1") == 0
    W.merge_back(ws, "J1")                                     # 闸过合主干
    out = W.prune(ws, "J1")                                    # 然后删线
    assert "branch:k3dit/J1" in out["removed"]
    assert _grc(ws, "rev-parse", "--verify", "-q", "refs/heads/k3dit/J1") != 0


def test_strip_pins_full_line_only(tmp_path):
    ws = _repo(tmp_path)
    wt = W.ensure(ws, "J9")
    (wt / "src" / "m.py").write_text(
        "def f():\n    # k3dit:pending A-1 x\n    # k3dit:leftover L-1 有意留\n    return 1\n", encoding="utf-8")
    (wt / "note.md").write_text("# t\n<!-- k3dit:fixnote F-2 -->\n", encoding="utf-8")
    (wt / "keep.py").write_text("y = 2  # k3dit:pending T-3 trailing\n", encoding="utf-8")
    out = W.strip_pins(ws, "J9")
    assert out["stripped_lines"] == 2 and len(out["stripped_files"]) == 2   # pending A-1 + fixnote F-2
    assert out["kept"] == 1                                                  # leftover L-1 保留（长期文献）
    assert out["suspicious"] == ["keep.py:1"]                                # 行尾钉不动，只上报
    txt = (wt / "src" / "m.py").read_text(encoding="utf-8")
    assert "# k3dit:pending" not in txt and "y = 2" in (wt / "keep.py").read_text(encoding="utf-8")
    assert "k3dit:leftover L-1 有意留" in txt                                 # leftover 随文件留
    again = W.strip_pins(ws, "J9")
    assert again["stripped_lines"] == 0 and again["kept"] == 1               # 幂等


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
    assert "merge" not in _g(ws, "log", "--oneline").lower()


def test_present_reattaches_branch(tmp_path):
    ws = _repo(tmp_path)
    wt = W.ensure(ws, "J9")
    head = _g(ws, "rev-parse", "HEAD").strip()
    W.present(ws, "J9", commit=head)
    assert _g(wt, "symbolic-ref", "-q", "HEAD").strip() == "refs/heads/k3dit/J9"  # 看完切回，不留 detached


def test_merge_back_after_detached_present(tmp_path):
    ws = _repo(tmp_path)
    wt = W.ensure(ws, "J9")
    (wt / "extra.py").write_text("e = 1\n", encoding="utf-8")
    W.advance(ws, "J9")
    W.present(ws, "J9", commit=W.advance(ws, "J9"))  # 曾经的毒化路径：detach 残留
    _g(wt, "checkout", "-q", "--detach", "HEAD")     # 模拟旧 present 遗留的 detached
    (ws / "main.py").write_text("m = 1\n", encoding="utf-8")
    _g(ws, "add", "-A")
    _g(ws, "commit", "-qm", "main moved")
    r = W.merge_back(ws, "J9")
    assert r["ok"] and r["mode"] == "rebase", r
    assert (ws / "extra.py").exists() and (ws / "main.py").exists()


def test_merge_back_landing_gate_blocks_and_resets(tmp_path, monkeypatch):
    """落点机械闸红 ⇒ 不并、主干回滚到旧头（先验后并，主干不被污染）。"""
    ws = _repo(tmp_path)
    W.ensure(ws, "J1")
    _commit_on_branch(ws, "extra.py", "e = 1\n")
    before = _g(ws, "rev-parse", "HEAD").strip()
    monkeypatch.setattr(W, "_run_landing_gate",
                        lambda w: {"ok": False, "step": "tests", "message": "1 failed"})
    r = W.merge_back(ws, "J1")
    assert not r["ok"] and r["mode"] == "gate" and "落点" in r["message"]
    assert _g(ws, "rev-parse", "HEAD").strip() == before
    assert not (ws / "extra.py").exists()


def test_present_raise_when_restore_fails(tmp_path, monkeypatch):
    """复位 checkout 失败仍静默 ⇒ worktree 留 detached，毒化后续 rebase（339）。

    旧替身自造 `R` 类、吞 `**kw`、把分支名假成 `k3dge/job`（模块真前缀 `k3dit/`），
    且 `calls` 记了不——钉失败的可能是任何一次 checkout（t-317）。
    现在**包住真 `_git`**：只把复位那次（`checkout -q <branch>`，非 `--detach`）强制
    rc=1，其余走真 subprocess（CompletedProcess/text 契约同形状），并断言被钉的
    正是真分支名那次调用。
    """
    ws = _repo(tmp_path)
    W.ensure(ws, "J1")
    real = W._git
    forced = []

    def wrap(workspace, *args, **kw):
        if args and args[0] == "checkout" and "--detach" not in args:
            forced.append(args)
            return subprocess.CompletedProcess(list(args), 1, "", "fatal: simulated")
        return real(workspace, *args, **kw)

    monkeypatch.setattr(W, "_git", wrap)
    with pytest.raises(RuntimeError, match="复位失败"):
        W.present(ws, "J1", commit="HEAD")
    assert forced, "复位 checkout 从没发生——本测钉的形状已变"
    assert all(a[-1] == W.branch_name("J1") for a in forced), forced
