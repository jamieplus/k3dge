"""封版记录的 durable 面（ADR-0004 §2.1.10）：trailer 四键 + 边界 tag。

为何用**真 git 仓**：这两件事的全部价值就是"有可复算的凭据"——重演版本必须在真 git 上验
（`git log --format=%(trailers)` / `git rev-parse <tag>^{commit}`），桩掉 git 就只剩同义反复。

回归的洞（本会话实测）：审计常常**零提交**（`worktree.advance` 只在脏时提交；线 tip == 主干头
⇒ 无新提交），报告只落在工作树里 ⇒ 把记录挂在"审计的提交"上没有载体。修法＝挂在**封版提交**
（封版动作必然产生改动）。
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from unittest import TestCase

from k3dge.engine.seal import (
    SEAL_TRAILER_KEYS,
    format_seal_trailers,
    parse_seal_trailers,
    seal_record,
    tag_audit_baseline,
)


def _git(ws: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(ws), *args], capture_output=True,
                          text=True).stdout.strip()


def _repo() -> Path:
    ws = Path(tempfile.mkdtemp())
    _git(ws, "init", "-q")
    _git(ws, "-c", "user.name=t", "-c", "user.email=t@t", "commit",
         "-q", "--no-verify", "--allow-empty", "-m", "chore: init")
    return ws


class TestTrailerFormat(TestCase):
    def test_roundtrip_is_single_sourced(self) -> None:
        text = format_seal_trailers("M10", "abc1234", "k3dit@seat", "closed")
        parsed = parse_seal_trailers(text)
        self.assertEqual(set(parsed), set(SEAL_TRAILER_KEYS))
        self.assertEqual(parsed["seal-milestone"], "M10")
        self.assertEqual(parsed["audit-baseline"], "abc1234")
        self.assertEqual(parsed["audit-result"], "closed")

    def test_missing_keys_are_not_invented(self) -> None:
        self.assertEqual(parse_seal_trailers("chore: nothing here"), {})
        # 空值 ⇒ `-`（记录里"没席位"与"没这个键"必须能区分）
        self.assertEqual(parse_seal_trailers(format_seal_trailers("M1", "abc", "", ""))["audit-seat"], "-")

    def test_parses_git_trailers_output_shape(self) -> None:
        text = _git(_repo(), "log", "-1", "--format=%(trailers)")  # 不带 trailer 的形态
        self.assertEqual(parse_seal_trailers(text), {})


class TestSealRecord(TestCase):
    def test_commit_carries_trailers_and_tag_points_at_baseline(self) -> None:
        ws = _repo()
        baseline = _git(ws, "rev-parse", "HEAD")
        (ws / "docs" / "tasks" / "archive" / "M10").mkdir(parents=True)
        (ws / "docs" / "tasks" / "archive" / "M10" / "x.md").write_text("# x\n", encoding="utf-8")

        ok, msg = seal_record(ws, "M10", baseline=baseline, seat="k3dit@seat", result="closed")
        self.assertTrue(ok, msg)
        body = _git(ws, "log", "-1", "--format=%B")
        parsed = parse_seal_trailers(body)
        self.assertEqual(parsed["seal-milestone"], "M10")
        self.assertEqual(parsed["audit-baseline"], baseline)
        self.assertEqual(parsed["audit-result"], "closed")
        self.assertEqual(parsed["audit-seat"], "k3dit@seat")
        # tag 指向**基线**（审哪版封哪版），不是封版提交
        self.assertEqual(_git(ws, "rev-parse", "M10^{commit}"), baseline)
        self.assertNotEqual(_git(ws, "rev-parse", "HEAD"), baseline)

    def test_zero_audit_commit_still_gets_a_record(self) -> None:
        """审计零提交 ⇒ 仍有封版提交承载记录（否则记录没有载体）。"""
        ws = _repo()
        baseline = _git(ws, "rev-parse", "HEAD")
        ok, msg = seal_record(ws, "M10", baseline=baseline, result="closed")
        self.assertTrue(ok, msg)
        self.assertIn("无改动", msg)          # 空改动不造空提交
        self.assertEqual(_git(ws, "rev-parse", "M10^{commit}"), baseline)

    def test_clean_tree_does_not_create_empty_commit(self) -> None:
        ws = _repo()
        baseline = _git(ws, "rev-parse", "HEAD")
        seal_record(ws, "M11", baseline=baseline, result="closed")
        self.assertEqual(_git(ws, "rev-list", "--count", "HEAD"), "1")  # 只有 init


class TestTagBoundary(TestCase):
    def test_idempotent_same_target_and_refuses_move(self) -> None:
        ws = _repo()
        first = _git(ws, "rev-parse", "HEAD")
        _git(ws, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--no-verify",
             "--allow-empty", "-m", "chore: second")
        second = _git(ws, "rev-parse", "HEAD")

        ok, msg = tag_audit_baseline(ws, "M10", first)
        self.assertTrue(ok, msg)
        ok2, msg2 = tag_audit_baseline(ws, "M10", first)          # 幂等
        self.assertTrue(ok2, msg2)
        self.assertIn("已在", msg2)
        ok3, msg3 = tag_audit_baseline(ws, "M10", second)         # 指向不同 ⇒ 拒
        self.assertFalse(ok3)
        self.assertIn("不移动", msg3)
        self.assertEqual(_git(ws, "rev-parse", "M10^{commit}"), first)  # 未被移动

    def test_refuses_invalid_baseline_and_id(self) -> None:
        ws = _repo()
        self.assertFalse(tag_audit_baseline(ws, "M10", "")[0])
        self.assertFalse(tag_audit_baseline(ws, "M10", "not-a-sha")[0])
        self.assertFalse(tag_audit_baseline(ws, "M 10", "abc1234")[0])   # 非法里程碑 id

    def test_record_fails_when_not_a_repo(self) -> None:
        ws = Path(tempfile.mkdtemp())
        ok, msg = seal_record(ws, "M10", baseline="abc1234", result="closed")
        self.assertFalse(ok)
        self.assertIn("git", msg.lower())
