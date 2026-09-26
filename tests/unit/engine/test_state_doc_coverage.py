"""`overview.md` 必须列全状态闭集（`ARCH_STATE_DOC_DRIFT`）：`[NEXT]` 态 + task 态。"""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from k3dge.engine import nextstep, state_machine
from k3dge.engine.evaluator import ConsistencyEngine


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _make_repo(tmp: Path) -> Path:
    repo = tmp / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "tester")
    (repo / ".agent").mkdir()
    (repo / ".agent" / "manifest.json").write_text(
        json.dumps({"package_root": "src", "domains": {}, "ignore": []}), encoding="utf-8"
    )
    (repo / "docs" / "architecture").mkdir(parents=True)
    return repo


def _full_overview() -> str:
    lines = ["# Arch", "", "## 6. 状态机", ""]
    lines += [f"| {nextstep.STATE_OPTIONS[s]['priority']} | `{s}` | 是 | … |" for s in sorted(nextstep.STATE_OPTIONS)]
    lines += [f"| 现态 `{s.value}` | 迁移 | 次态 |" for s in state_machine.TaskState]
    return "\n".join(lines) + "\n"


class TestStateDocCoverage(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = _make_repo(Path(self._tmp.name))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _rules(self) -> list:
        return [v.rule_id for v in ConsistencyEngine(self.repo).evaluate().violations]

    def _write(self, text: str) -> None:
        (self.repo / "docs" / "architecture" / "overview.md").write_text(text, encoding="utf-8")

    def test_full_state_set_passes(self) -> None:
        self._write(_full_overview())
        self.assertNotIn("ARCH_STATE_DOC_DRIFT", self._rules())

    def test_missing_next_state_is_violation(self) -> None:
        text = _full_overview().replace("`audit_suggested`", "`something_else`")
        self._write(text)
        self.assertIn("ARCH_STATE_DOC_DRIFT", self._rules())

    def test_missing_task_state_is_violation(self) -> None:
        text = _full_overview().replace("`deferred`", "`paused`")
        self._write(text)
        self.assertIn("ARCH_STATE_DOC_DRIFT", self._rules())

    def test_plain_words_without_backticks_do_not_count(self) -> None:
        text = _full_overview().replace("`normal`", "normal")
        self._write(text)
        self.assertIn("ARCH_STATE_DOC_DRIFT", self._rules())

    def test_missing_overview_is_not_a_violation(self) -> None:
        self.assertNotIn("ARCH_STATE_DOC_DRIFT", self._rules())


if __name__ == "__main__":
    unittest.main()
