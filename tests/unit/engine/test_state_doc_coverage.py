"""`overview.md` 必须列全状态闭集（`ARCH_STATE_DOC_DRIFT`）：`[NEXT]` 态 + task 态。"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from k3dge.engine import nextstep, state_machine
from k3dge.engine.evaluator import ConsistencyEngine


def _git(repo: Path, *args: str) -> None:
    """git 前置失败要**带 stderr 出声**（t-260）。

    `check=True` 的 `CalledProcessError` 只含命令与 rc，git 的真实抱怨（stderr）
    被 `capture_output` 吞掉——"环境不行"会读成"产品 bug"。
    """
    proc = subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失败：{proc.stderr.strip()}")


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


@unittest.skipUnless(shutil.which("git"), "fixture 需要 git（`init -b` 要求 ≥2.28）")
class TestStateDocCoverage(unittest.TestCase):
    def setUp(self) -> None:
        # cleanup **先登记**再建仓（t-262）：`setUp` 中途抛错时 unittest 不会跑
        # `tearDown`，旧写法每次都泄漏一个临时目录；addCleanup 在 setUp 失败时照跑。
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = _make_repo(Path(self._tmp.name))

    def _violations(self):
        # `force_full=True`（t-263）：默认路径先读 `get_changed_files()`，它认继承的
        # `K3DGE_BASE_SHA`——本 fixture 仓**没有提交**，ambient base sha 会让 GitError
        # 早退，本闸根本不跑，纯负断言就此假绿。文档闸与 change-set 无关，强制全量。
        return ConsistencyEngine(self.repo).evaluate(force_full=True).violations

    def _rules(self) -> list:
        return [v.rule_id for v in self._violations()]

    def _write(self, text: str) -> None:
        (self.repo / "docs" / "architecture" / "overview.md").write_text(text, encoding="utf-8")

    def _drift_violation(self):
        vs = [v for v in self._violations() if v.rule_id == "ARCH_STATE_DOC_DRIFT"]
        self.assertEqual(len(vs), 1, vs)
        return vs[0]

    def test_full_state_set_passes(self) -> None:
        self._write(_full_overview())
        self.assertNotIn("ARCH_STATE_DOC_DRIFT", self._rules())

    def test_missing_next_state_is_violation(self) -> None:
        """victim 从**同源**取、断言替换真的落地、missing 集合里必须有它（t-264）。

        旧测写死 `audit_suggested`：上游改名/删除后 `str.replace` 变 no-op，
        fixture 仍是 100% 全表，测红成"规则没报"——把过期 fixture 误报成规则故障。
        """
        original = _full_overview()
        victim = sorted(nextstep.STATE_OPTIONS)[0]
        text = original.replace(f"`{victim}`", "`something_else`", 1)
        self.assertNotEqual(text, original, f"`{victim}` 不在 fixture 表里——过期 fixture，不是规则")
        self._write(text)
        det = self._drift_violation().detail or {}
        self.assertIn(victim, det.get("missing"), det)

    def test_missing_task_state_is_violation(self) -> None:
        original = _full_overview()
        victim = sorted(s.value for s in state_machine.TaskState)[0]
        text = original.replace(f"`{victim}`", "`paused`", 1)
        self.assertNotEqual(text, original, f"`{victim}` 不在 fixture 表里——过期 fixture，不是规则")
        self._write(text)
        det = self._drift_violation().detail or {}
        self.assertIn(victim, det.get("missing"), det)

    def test_plain_words_without_backticks_do_not_count(self) -> None:
        original = _full_overview()
        victim = sorted(nextstep.STATE_OPTIONS)[1]
        text = original.replace(f"`{victim}`", victim, 1)
        self.assertNotEqual(text, original)
        self._write(text)
        det = self._drift_violation().detail or {}
        self.assertIn(victim, det.get("missing"), det)

    def test_priority_mismatch_is_violation(self) -> None:
        """三分支只测过一条（t-261）：priority 漂移分支此前零覆盖——
        `_full_overview()` 的数字直接抄自 `STATE_OPTIONS`，永远对得上。
        这里**手动改一个数字**，断言 got/want 都如实报。"""
        original = _full_overview()
        state = sorted(nextstep.STATE_OPTIONS)[0]
        want = int(nextstep.STATE_OPTIONS[state]["priority"])
        got = want + 5
        text = original.replace(f"| {want} | `{state}` |", f"| {got} | `{state}` |", 1)
        self.assertNotEqual(text, original, "priority 行形状变了——fixture 过期")
        self._write(text)
        det = self._drift_violation().detail or {}
        self.assertEqual(det.get("state"), state, det)
        self.assertEqual(det.get("got"), got, det)
        self.assertEqual(det.get("want"), want, det)

    def test_doc_listing_no_states_does_not_report(self) -> None:
        """另一半规则"要么不写、要么写全"（t-261③）：一列状态都没有的骨架
        overview.md **不报**——只有写了一半才误导。"""
        self._write("# Arch\n\n## 6. 状态机\n\n{{todo: 待补表}}\n")
        self.assertNotIn("ARCH_STATE_DOC_DRIFT", self._rules())

    def test_missing_overview_is_not_a_violation(self) -> None:
        self.assertNotIn("ARCH_STATE_DOC_DRIFT", self._rules())


if __name__ == "__main__":
    unittest.main()
