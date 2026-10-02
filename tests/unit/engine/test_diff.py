import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from k3dge.engine.diff import (
    GitError,
    _parse_porcelain,
    _parse_porcelain_z,
    _strip_quotes,
    get_changed_files,
    resolve_base,
)


def _git_env() -> dict:
    """ocr2-453：临时仓 git 调用必须出局宿主环境——GIT_DIR/GIT_WORK_TREE 会让 `git add`
    写进真仓；全局 gpgsign/hooksPath/autocrlf/excludesFile 会让 setup 因无关原因红或改写字节。"""
    e = {k: v for k, v in os.environ.items()
         if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_CONFIG", "K3DGE_BASE_SHA")}
    e["GIT_CONFIG_GLOBAL"] = os.devnull
    e["GIT_CONFIG_NOSYSTEM"] = "1"
    e["GIT_TERMINAL_PROMPT"] = "0"
    return e


def _probe_git() -> "tuple[bool, str]":
    """git 是这两条测的**前置**而非产品依赖（生产对缺 git 走 GIT_UNAVAILABLE 降级，t-101）。

    ocr2-452：探针不得把任何非零退出都读成"无需 git 跳过"——权限/safe.directory/
    GIT_DIR 泄漏等会让**整块 git 集成覆盖静默消失**。这里把探针 stderr 带进 skip 理由，
    并让探针与 `_git` 用同一份净化 env（否则跳过判定与执行环境不一致）。
    """
    if not shutil.which("git"):
        return False, "需要 git（机器上找不到 git）"
    with tempfile.TemporaryDirectory() as d:   # 探针目录随用随清（裸 mkdtemp＝泄漏）
        probe = subprocess.run(["git", "init", "-q", "-b", "probe", d],
                               capture_output=True, text=True, env=_git_env(), timeout=60)
    if probe.returncode != 0:
        detail = (probe.stderr or probe.stdout or "").strip().splitlines()
        tail = detail[-1] if detail else ""
        return False, (f"需要 git（`init -b` 失败 rc={probe.returncode}：{tail[:140]}）")
    return True, ""


_GIT_OK, _GIT_SKIP_REASON = _probe_git()


def _git_available() -> bool:
    return _GIT_OK


def _git(repo, *args) -> str:
    return subprocess.run(["git", *args], cwd=str(repo), check=True, timeout=60,
                          capture_output=True, text=True, env=_git_env()).stdout


def _make_repo(tmp) -> "tuple[Path, str]":
    """一份 bootstrap（t-102）：init＋身份＋两次提交（a 在 base 前、b 在 base 后）。
    两条 git 测原先各抄 8 行；环境隔离（t-101）也只需在这里改一处。"""
    repo = Path(tmp) / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@t.com")
    _git(repo, "config", "user.name", "t")
    (repo / "a.txt").write_text("1\n", encoding="utf-8")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-m", "one")
    first = _git(repo, "rev-parse", "HEAD").strip()
    (repo / "b.txt").write_text("2\n", encoding="utf-8")
    _git(repo, "add", "b.txt")
    _git(repo, "commit", "-m", "two")
    return repo, first


class TestDiff(unittest.TestCase):
    def test_parse_rename_takes_destination(self) -> None:
        self.assertEqual(_parse_porcelain("R  old.py -> new.py\n"), ["new.py"])

    def test_parse_quoted_path(self) -> None:
        self.assertEqual(_parse_porcelain('?? "foo bar.py"\n'), ["foo bar.py"])

    def test_strip_quotes_unescapes(self) -> None:
        self.assertEqual(_strip_quotes('"a\\"b"'), 'a"b')

    @unittest.skipUnless(_git_available(), _GIT_SKIP_REASON)
    def test_k3dge_base_sha_includes_committed(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo, first = _make_repo(d)
            with mock.patch.dict(os.environ, {"K3DGE_BASE_SHA": first}):
                files = get_changed_files(repo)
            # 只断"b.txt 在场"放得过"无视 base 返回全部跟踪文件"或"对着空树 diff"
            # 这类实现（t-099）：a.txt 提交在 base **之前**，必须**不在**结果里。
            self.assertIn("b.txt", files)
            self.assertNotIn("a.txt", files)
            # 未提交改动也在同一观测面里（status 路径）
            (repo / "c.txt").write_text("3\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"K3DGE_BASE_SHA": first}):
                files2 = get_changed_files(repo)
            self.assertIn("c.txt", files2)
            self.assertNotIn("a.txt", files2)
            # 非法 base（`-` 开头/含空白）：入口拒、不递给 git（ocr-229）。
            # 纯空白是"没设"（`strip()` 后空 ⇒ 回落 `resolve_base`），必须真跑不断言跳过（ocr2-114）。
            for bad_base in ("-b extra", "a b"):
                with mock.patch.dict(os.environ, {"K3DGE_BASE_SHA": bad_base}):
                    with self.assertRaises(GitError):
                        get_changed_files(repo)
            with mock.patch.dict(os.environ, {"K3DGE_BASE_SHA": "  "}):
                files3 = get_changed_files(repo)
                self.assertIn("c.txt", files3)

class TestPorcelainZ(unittest.TestCase):
    """`get_changed_files` 走的是 `-z` 路径（t-100）——live 代码此前**零直测**：
    NUL 分隔、rename/copy 的"下一 token 是原路径"消费、非 ASCII 不转义，
    任一回归都不会被 CI 发现。v1 解析器测的是 legacy 面，不能替它作证。"""

    def test_plain_and_untracked_entries(self) -> None:
        self.assertEqual(_parse_porcelain_z(" M x.py\0?? dir/y.md\0\0"),
                         ["x.py", "dir/y.md"])

    def test_rename_pair_consumes_origin_token(self) -> None:
        # git -z 的顺序是 **dest 在前、orig 在后**：跳过逻辑写反＝把原路径当改动面
        self.assertEqual(_parse_porcelain_z("R  docs/new.py\0docs/old.py\0"),
                         ["docs/new.py"])

    def test_copy_pair_consumes_origin_token(self) -> None:
        self.assertEqual(_parse_porcelain_z("C  a.py\0orig.py\0"), ["a.py"])

    def test_unicode_and_spaces_in_names_survive(self) -> None:
        self.assertEqual(_parse_porcelain_z("?? 中文 文件.py\0"), ["中文 文件.py"])

    def test_v1_rename_source_containing_arrow(self) -> None:
        # 源路径自带 " -> "（合法文件名）：从右切才拿到目标（ocr-228 的形状）
        self.assertEqual(_parse_porcelain("R  old -> odd.py -> new.py\n"), ["new.py"])


class TestResolveBase(unittest.TestCase):
    @unittest.skipUnless(_git_available(), _GIT_SKIP_REASON)
    def test_resolve_base_falls_back_to_head(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            repo.mkdir()
            _git(repo, "init", "-b", "dev")
            _git(repo, "config", "user.email", "t@t.com")
            _git(repo, "config", "user.name", "t")
            (repo / "a.txt").write_text("1\n", encoding="utf-8")
            _git(repo, "add", "a.txt")
            _git(repo, "commit", "-m", "one")
            self.assertEqual(resolve_base(repo), "HEAD")

    def test_unknown_base_falls_back_to_full_scan(self) -> None:
        # 基线不明时 `get_changed_files` 不得跳过已提交文件：`HEAD..HEAD` 空集会假绿（ocr2-053）。
        # fail-closed：回退全量 `ls-files`，已提交的改动仍被查到。
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            repo.mkdir()
            _git(repo, "init", "-b", "dev")
            _git(repo, "config", "user.email", "t@t.com")
            _git(repo, "config", "user.name", "t")
            (repo / "a.txt").write_text("1\n", encoding="utf-8")
            _git(repo, "add", "a.txt")
            _git(repo, "commit", "-m", "one")
            self.assertIn("a.txt", get_changed_files(repo))


if __name__ == "__main__":
    unittest.main()
