"""架构文档新鲜度（seal 收摊时算的事实）：`M<last>` 边界 .. HEAD 区间内 src/spec 变过而 overview 未动 ⇒ 报。"""
import subprocess
import tempfile
import unittest
from pathlib import Path

from k3dge.engine.seal_flow import _architecture_staleness, _boundary_tag_before


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _init(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "tester")
    (repo / "docs" / "architecture").mkdir(parents=True)
    (repo / "docs" / "architecture" / "overview.md").write_text("# Arch\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "chore: init")
    _git(repo, "tag", "-a", "M9", "-m", "boundary M9")


class TestArchitectureFreshness(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "repo"
        _init(self.repo)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_boundary_tag_before_skips_current_milestone(self) -> None:
        self.assertEqual(_boundary_tag_before(self.repo, "M10"), "M9")
        self.assertEqual(_boundary_tag_before(self.repo, "M9"), "")  # 自己是唯一 tag ⇒ 无

    def test_src_changed_without_overview_warns(self) -> None:
        (self.repo / "src" / "a.py").write_text("x = 2\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "feat: change")
        line = _architecture_staleness(self.repo, "M10")
        self.assertIn("未更新", line)
        self.assertIn("M9", line)

    def test_overview_touched_in_range_is_ok(self) -> None:
        (self.repo / "src" / "a.py").write_text("x = 2\n", encoding="utf-8")
        (self.repo / "docs" / "architecture" / "overview.md").write_text("# Arch v2\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "docs: arch + code")
        self.assertIn("已更新", _architecture_staleness(self.repo, "M10"))

    def test_no_code_change_since_boundary_is_ok(self) -> None:
        (self.repo / "docs" / "memo").mkdir(parents=True)
        (self.repo / "docs" / "memo" / "x.md").write_text("# x\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "docs: memo only")
        self.assertIn("无改动", _architecture_staleness(self.repo, "M10"))

    def test_first_milestone_without_boundary_is_ok(self) -> None:
        line = _architecture_staleness(self.repo, "M9")
        self.assertIn("首个里程碑", line)


if __name__ == "__main__":
    unittest.main()
