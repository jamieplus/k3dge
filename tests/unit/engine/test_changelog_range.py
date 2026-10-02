"""CHANGELOG 由**提交区间**生成（ADR-0004 §2.1.12）。

为何用真 git 仓：这一条的保证就是"区间内每个非机械提交都有条目"——桩掉 git 只剩同义反复。
"""

import itertools
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest import TestCase, mock

from k3dge.engine.changelog import build_notes_from_range, mechanical_commit

_SEQ = itertools.count(1)


def _git(ws: Path, *args: str) -> str:
    """所有 git 前置**必须查返回码、失败带 stderr**（t-083/084）。

    旧 `_repo()` 的 `git init` 不查 rc：git 缺失/不可用时测继续在**非仓库目录**上跑，
    每一处红都伪装成 CHANGELOG 断言失败。环境钉法见 `_GitRepoCase.setUp`。
    """
    r = subprocess.run(["git", *args], cwd=str(ws), capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失败：{(r.stderr or r.stdout).strip()}")
    return r.stdout


class _GitRepoCase(TestCase):
    """临时 git 仓的共享脚手架：清理**在创建时**登记，环境自始隔离。

    - `TemporaryDirectory` + `addCleanup`（t-083）：旧 `mkdtemp + atexit` 只在解释器
      退出才清，CI 长跑＝无界堆积；且 setUp 中途抛错时 atexit 之前目录已泄漏。
    - `GIT_CONFIG_GLOBAL=devnull` + `GIT_CONFIG_NOSYSTEM` + `HOME` 进临时目录：
      宿主 globalconfig（commit.gpgsign / core.hooksPath / include.path）不再翻测；
      该 patch 作用于整个进程环境 ⇒ 连 `build_notes_from_range` 内部起的 git 也吃到。
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        patcher = mock.patch.dict(os.environ, {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "HOME": self._tmp.name,
        })
        patcher.start()
        self.addCleanup(patcher.stop)
        self.ws = Path(self._tmp.name) / "repo"
        self.ws.mkdir()
        _git(self.ws, "init", "-q")
        _git(self.ws, "config", "user.name", "t")
        _git(self.ws, "config", "user.email", "t@t")

    def commit(self, subject: str, *, body: str = "") -> str:
        """提交面保证**真的产生了提交**（t-084）：旧夹具恒写同名文件同名内容，
        复用 subject（扩展 `test_filters_mechanical_commits` 时极易踩）会撞上
        "nothing to commit"——提交被静默跳过，区间里根本没有它，测照样绿。
        唯一化内容 + add/commit/rev-parse 全部查错，堵掉这两类静默。"""
        (self.ws / "f.txt").write_text(f"{subject} #{next(_SEQ)}\n", encoding="utf-8")
        _git(self.ws, "add", "-A")
        msg = subject + (f"\n\n{body}" if body else "")
        _git(self.ws, "commit", "-q", "--no-verify", "-m", msg)
        head = _git(self.ws, "rev-parse", "HEAD").strip()
        self.assertTrue(head, "rev-parse 回了空——仓库没有提交，前置坏了")
        return head

    def tag(self, name: str) -> None:
        _git(self.ws, "tag", "-a", name, "-m", name)


class TestMechanical(TestCase):
    def test_round_work_and_seal_commits_are_mechanical(self) -> None:
        self.assertTrue(mechanical_commit("round work M10", ""))
        self.assertTrue(mechanical_commit("chore(seal): seal milestone M10",
                                          "Seal-milestone: M10\nAudit-result: closed"))

    def test_normal_commit_is_not_mechanical(self) -> None:
        self.assertFalse(mechanical_commit("feat(engine): add x", ""))
        self.assertFalse(mechanical_commit("fix: correct y", ""))
        # 非 conventional **不是**机械件：它要进 `uncovered`（漏项信号），静默滤掉＝把病藏起来
        self.assertFalse(mechanical_commit("some prose subject", ""))
        self.assertFalse(mechanical_commit("unknown-type: x", ""))


class TestRangeNotes(_GitRepoCase):
    def test_covers_every_non_mechanical_commit_since_the_tag(self) -> None:
        self.commit("chore: seed")
        self.tag("M9")
        self.commit("feat(engine): add thing")
        self.commit("fix(audit): repair thing")
        self.commit("docs: explain thing")
        notes, uncovered = build_notes_from_range(self.ws)
        self.assertEqual(uncovered, [])
        for text in ("add thing", "repair thing", "explain thing"):
            self.assertIn(text, notes)
        self.assertIn("### Added", notes)
        self.assertIn("### Fixed", notes)
        self.assertIn("### Changed", notes)

    def test_filters_mechanical_commits(self) -> None:
        self.commit("chore: seed")
        self.tag("M9")
        self.commit("feat: real work")
        self.commit("round work M10")
        self.commit("chore(seal): seal milestone M10", body="Seal-milestone: M10")
        notes, _u = build_notes_from_range(self.ws)
        self.assertIn("real work", notes)
        self.assertNotIn("round work", notes)
        self.assertNotIn("seal milestone", notes)

    def test_no_previous_tag_yields_empty_notes(self) -> None:
        self.commit("feat: only work")
        self.assertEqual(build_notes_from_range(self.ws), ("", []))

    def test_untyped_subject_is_reported_not_invented(self) -> None:
        self.commit("chore: seed")
        self.tag("M9")
        self.commit("feat: typed work")
        self.commit("unknown-type: work that cannot be filed")
        notes, uncovered = build_notes_from_range(self.ws)
        self.assertIn("typed work", notes)
        self.assertNotIn("work that cannot be filed", notes)   # 不猜它归哪一节
        self.assertEqual(len(uncovered), 1)   # 漏项信号（调用方告警，不静默吞掉）

    def test_previous_tag_selection_uses_highest_number(self) -> None:
        self.commit("chore: seed")
        self.tag("M9")
        self.commit("feat: in M10")
        self.tag("M10")
        self.commit("feat: in M11")
        notes, _u = build_notes_from_range(self.ws)
        self.assertIn("in M11", notes)
        self.assertNotIn("in M10", notes)     # 区间从最大号边界起算


class TestNoDoubleWrite(TestCase):
    """ADR-0004 §2.1.12：`task done` **不再**写 CHANGELOG（双写＝漏项与漂移的来源）。"""

    def test_mark_task_done_leaves_changelog_untouched(self) -> None:
        from k3dge.engine.task_write import mark_task_done

        ws = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, ws, ignore_errors=True)
        (ws / "docs" / "tasks").mkdir(parents=True)
        changelog = ws / "CHANGELOG.md"
        changelog.write_text("# Changelog\n\n## [Unreleased]\n\n## [1.0.0] - 2026-01-01\n",
                             encoding="utf-8")
        before = changelog.read_text(encoding="utf-8")
        p = ws / "docs" / "tasks" / "2026-09-20-M10-feat-x.md"
        p.write_text("---\nstatus: in_progress\nmilestone: M10\npriority: P2\ndate: 2026-09-20\n---\n\n# X\n",
                     encoding="utf-8")
        ok, _msg, out = mark_task_done(ws, p.name)   # 入口收 ident（路径或其唯一子串）
        self.assertTrue(ok)
        self.assertTrue(out.name.endswith(".done.md"))
        self.assertEqual(changelog.read_text(encoding="utf-8"), before)


def test_change_type_maps_agree_across_the_two_owners() -> None:
    """两表同口径的**方向**要对（t-085）：旧测只查交集——`_RANGE_TYPES` 允许当超集
    （changelog 侧多收几个前缀），真正会破坏文档承诺的是反方向：`_CT_MAP` 加了前缀
    而 `_RANGE_TYPES` 没有（提交闸允许的类型的 CHANGELOG 里没有对应节）。
    精确不变量：`set(_CT_MAP) ⊆ set(_RANGE_TYPES)` 且在共有键上**值同名**。"""
    from k3dge.engine import version
    from k3dge.engine.changelog import _RANGE_TYPES

    missing = sorted(set(version._CT_MAP) - set(_RANGE_TYPES))
    assert not missing, f"_CT_MAP 的前缀没进 _RANGE_TYPES（CHANGELOG 会缺节）：{missing}"
    drift = {k: (_RANGE_TYPES[k], version._CT_MAP[k]) for k in version._CT_MAP
             if _RANGE_TYPES[k] != version._CT_MAP[k]}
    assert not drift, f"两处映射漂移: {drift}"


def test_perf_prefix_lands_in_the_same_section() -> None:
    """perf 提交**实际落**的节走整条链（t-086）。

    封板路上 perf 先被 `_infer_change_type` 重写成 `refactor` 再查节；旧断言比的
    `_RANGE_TYPES["perf"] == _CT_MAP["perf"]` 是**没人消费**的键对——refactor 若被
    重映射而 perf 原样留着，两处写手把 perf 分到不同节，测仍绿。现在钉：改写结果 →
    该结果在两张表的落节一致，且**真生成器**（build_notes_from_range）把 perf 提交
    落到 `_CT_MAP[refactor]` 那一节。
    """
    from pathlib import Path as _P
    from k3dge.engine import version
    from k3dge.engine.changelog import _RANGE_TYPES

    typed = version._infer_change_type("perf(engine): speed up x", None)
    assert typed == "refactor"
    assert _RANGE_TYPES["perf"] == version._CT_MAP[typed], "changelog 与 version 的落节分叉"

    ws = _P(tempfile.mkdtemp())
    try:
        _git(ws, "init", "-q")
        _git(ws, "config", "user.name", "t")
        _git(ws, "config", "user.email", "t@t")
        def _mk(subject: str) -> None:
            (ws / "f.txt").write_text(subject, encoding="utf-8")   # 勿用 `or` 串：write_text
            _git(ws, "add", "-A")                                  # 返回字符数（真值）会短路
            _git(ws, "commit", "-q", "-m", subject)
        _mk("chore: seed")
        _git(ws, "tag", "-a", "M9", "-m", "M9")
        _mk("perf(engine): speed up thing")
        notes, uncovered = build_notes_from_range(ws)
        assert uncovered == []
        section = _RANGE_TYPES["perf"]          # == _CT_MAP["refactor"]
        assert f"### {section}" in notes, notes
        assert "speed up thing" in notes.split(f"### {section}")[1].split("###")[0], notes
    finally:
        import shutil
        shutil.rmtree(ws, ignore_errors=True)