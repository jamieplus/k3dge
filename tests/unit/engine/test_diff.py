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


def _git_available() -> bool:
    """git 是这两条测的**前置**而非产品依赖（生产对缺 git 走 GIT_UNAVAILABLE 降级，
    t-101）：缺/太老（`init -b` 需 ≥2.28）时显式 skip，而不是 error 一屏。"""
    if not shutil.which("git"):
        return False
    with tempfile.TemporaryDirectory() as d:   # 探针目录随用随清（裸 mkdtemp＝泄漏）
        probe = subprocess.run(["git", "init", "-q", "-b", "probe", d],
                               capture_output=True, text=True)
    return probe.returncode == 0


def _git(repo, *args) -> str:
    return subprocess.run(["git", *args], cwd=str(repo), check=True,
                          capture_output=True, text=True).stdout


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

    @unittest.skipUnless(_git_available(), "需要 git（`init -b` 要求 ≥2.28）")
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
            # 非法 base（`-` 开头/含空白）：入口拒、不递给 git（ocr-229）
            for bad_base in ("-b extra", "  ", "a b"):
                with mock.patch.dict(os.environ, {"K3DGE_BASE_SHA": bad_base}):
                    if bad_base.strip():
                        with self.assertRaises(GitError):
                            get_changed_files(repo)

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
    @unittest.skipUnless(_git_available(), "需要 git")
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


if __name__ == "__main__":
    unittest.main()
