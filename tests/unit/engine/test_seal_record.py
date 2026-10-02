"""封版记录的 durable 面（ADR-0004 §2.1.10）：trailer 四键 + 边界 tag。

为何用**真 git 仓**：这两件事的全部价值就是"有可复算的凭据"——重演版本必须在真 git 上验
（`git log --format=%(trailers)` / `git rev-parse <tag>^{commit}`），桩掉 git 就只剩同义反复。

回归的洞（本会话实测）：审计常常**零提交**（`worktree.advance` 只在脏时提交；线 tip == 主干头
⇒ 无新提交），报告只落在工作树里 ⇒ 把记录挂在"审计的提交"上没有载体。修法＝挂在**封版提交**
（封版动作必然产生改动）。
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import TestCase

from k3dge.engine.seal import (
    SEAL_TRAILER_KEYS,
    format_seal_trailers,
    parse_seal_trailers,
    seal_record,
    tag_audit_baseline,
)
import shutil
import atexit


def _git(ws: Path, *args: str) -> str:
    """git 前置失败必须**炸出来**（t-271）：旧写法把 rc/stderr 一起扔了——git 缺失、
    仓没建起来时所有读断言拿到 `""`，`assertEqual("", baseline)` 之类的谜之 diff 之外，
    `test_parses_git_trailers_output_shape` 甚至会因 `git log` 失败回 `""` 而**假绿**。
    本文件的用法全是"必须成功"；失败就带 stderr 抛。
    """
    # 宿主 globalconfig 出局（t-272 尾账）：`commit.gpgsign=true` 的开发机会让 `--no-verify`
    # 之外的路径也炸；`alias.*`/`include.path` 伪装"引擎坏了"。测试侧 git 一律钉
    # GIT_CONFIG_GLOBAL=devnull + NOSYSTEM；仓库身份仍由各命令 `-c` 显式给。
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_CONFIG")}
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    r = subprocess.run(["git", "-C", str(ws), *args], capture_output=True, text=True, env=env)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失败：{(r.stderr or r.stdout).strip()}")
    return r.stdout.strip()


def _repo() -> Path:
    """临时仓必须**脱离任何外层 git 树**。

    `mkdtemp()` 继承 `TMPDIR`；CI 常把 TMPDIR 设在 build 目录下 ⇒ `git -C <ws> status --porcelain`
    会对**外层仓**成功，于是 `_commit_all` 一路 `git add -A` + commit 污染开发/CI 仓库，
    测试自己也失（t-274）。`GIT_CEILING_DIRECTORIES` 让 git 不再向上找。
    """
    root = Path(tempfile.mkdtemp()).resolve()
    atexit.register(shutil.rmtree, root, True)
    os.environ["GIT_CEILING_DIRECTORIES"] = str(root.parent)
    ws = root
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
        from k3dge.engine.attest import PREFIX, verify_commit
        self.assertIn(PREFIX, body)
        ok, amsg = verify_commit(ws, _git(ws, "rev-parse", "HEAD"))
        self.assertTrue(ok, amsg)

    def test_clean_tree_does_not_create_empty_commit(self) -> None:
        """干净树：不造空提交**但边界 tag 必须立**（t-273）。

        旧测把 `seal_record` 的返回扔了——若它返回 `(False, …)`（tag 被拒/提交失败），
        树根本没动，`rev-list --count == 1` 照样绿：测的是"什么都没发生"，
        不是"该发生的发生了"。返回与 tag 两头都要断。
        """
        ws = _repo()
        baseline = _git(ws, "rev-parse", "HEAD")
        ok, msg = seal_record(ws, "M11", baseline=baseline, result="closed")
        self.assertTrue(ok, msg)
        self.assertEqual(_git(ws, "rev-list", "--count", "HEAD"), "1")  # 只有 init
        self.assertEqual(_git(ws, "rev-parse", "M11^{commit}"), baseline)  # durable 边界在

    def test_reentrant_seal_record_is_idempotent(self) -> None:
        """code-7 正面回应：seal 是幂等重入入口。基线不变时重跑 `seal_record`
        ⇒ 不追加第二份提交、边界 tag 不移动 ⇒ git 事实唯一，本地账只是投影
        （声明面 `on_rerun=append` 落的是可重建投影，judged 只读 tag+trailer）。"""
        ws = _repo()
        baseline = _git(ws, "rev-parse", "HEAD")
        (ws / "f.md").write_text("x\n", encoding="utf-8")                 # 第一次制造改动 ⇒ 有封版提交
        ok1, m1 = seal_record(ws, "M12", baseline=baseline, result="closed")
        self.assertTrue(ok1, m1)
        commits_after_first = int(_git(ws, "rev-list", "--count", "HEAD"))
        self.assertEqual(commits_after_first, 2)                          # init + 封版提交
        ok2, m2 = seal_record(ws, "M12", baseline=baseline, result="closed")
        self.assertTrue(ok2, m2)
        self.assertIn("已在", m2)                                          # tag 幂等
        self.assertEqual(int(_git(ws, "rev-list", "--count", "HEAD")), commits_after_first)  # 无第二提交
        self.assertEqual(_git(ws, "rev-parse", "M12^{commit}"), baseline)  # 边界未动


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
        """只断布尔会把"git 自己拒了"当"我们的校验生效"（t-277）：`M 10` 这类名字
        git 也拒，校验器删掉测照样绿。逐个钉**是谁说的不**，并证 tag 确实没立。"""
        ws = _repo()
        ok, msg = tag_audit_baseline(ws, "M10", "")
        self.assertFalse(ok)
        self.assertIn("审计基线不可用", msg)
        ok2, msg2 = tag_audit_baseline(ws, "M10", "not-a-sha")
        self.assertFalse(ok2)
        self.assertIn("审计基线不可用", msg2)
        ok3, msg3 = tag_audit_baseline(ws, "M 10", "abc1234")     # 非法里程碑 id
        self.assertFalse(ok3)
        self.assertIn("milestone id", msg3.lower(), msg3)         # 是校验器拒的，不是 git
        self.assertEqual(_git(ws, "tag", "--list").strip(), "")

    def test_record_fails_when_not_a_repo(self) -> None:
        ws = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, ws, ignore_errors=True)
        # 裸 mkdtemp 是否"非仓"取决于 `GIT_CEILING_DIRECTORIES`（别的测试的 `_repo()` 会设），
        # 不钉住就是测序相关的偶然通过（ocr2-123）。显式封顶到本目录，隔离断言。
        _old = os.environ.get("GIT_CEILING_DIRECTORIES")
        os.environ["GIT_CEILING_DIRECTORIES"] = str(ws)
        try:
            ok, msg = seal_record(ws, "M10", baseline="abc1234", result="closed")
        finally:
            if _old is None:
                del os.environ["GIT_CEILING_DIRECTORIES"]
            else:
                os.environ["GIT_CEILING_DIRECTORIES"] = _old
        self.assertFalse(ok)
        self.assertIn("git", msg.lower())


class TestTrailerSanitization(TestCase):
    """外部取来的值不得破坏 trailer 块（ocr-306/307）。"""

    def test_newline_and_colon_in_values_keep_four_keys(self) -> None:

        block = format_seal_trailers(
            "M11", "a7259c26", "k3dit\nAudit-extra: injected", "closed: with colon")
        self.assertEqual(len(block.splitlines()), 4, block)
        self.assertNotIn("\n\n", block, "空行会把最后一段拆开 ⇒ git 不再当 trailer 块")
        got = parse_seal_trailers(block)
        self.assertEqual(sorted(k.lower() for k in got), sorted(SEAL_TRAILER_KEYS))
        self.assertNotIn("audit-extra", {k.lower() for k in got})

    def test_empty_values_still_emit_all_four_keys(self) -> None:
        got = parse_seal_trailers(format_seal_trailers("M11", "", "", ""))
        self.assertEqual(len(got), 4)

    def test_same_commit_accepts_abbreviated_and_uppercase(self) -> None:
        from k3dge.engine.seal import _same_commit

        full = "a7259c26f3c2" + "0" * 28
        self.assertTrue(_same_commit(full, full[:7]))
        self.assertTrue(_same_commit(full, full.upper()))
        self.assertFalse(_same_commit(full, "b" * 40))


class TestAuditEvidence(TestCase):
    """判据只认 git 事实；本地账是投影，**冲突以 git 为准**（ADR-0004 §2.1.10）。"""

    def test_absent_tag_means_not_sealed(self) -> None:
        from k3dge.engine.audit_flow import audit_evidence

        ws = _repo()
        ev = audit_evidence(ws, "M10")
        self.assertEqual(ev, {"tag": "", "trailers": {}, "sealed": False})

    def test_tag_with_trailers_is_sealed(self) -> None:
        """干净树也要能读回记录：`_commit_all` 不造空提交 ⇒ tag 注解是第二载体。"""
        from k3dge.engine.audit_flow import audit_evidence

        ws = _repo()
        baseline = _git(ws, "rev-parse", "HEAD")
        ok, msg = seal_record(ws, "M10", baseline=baseline, seat="k3dit@seat", result="closed")
        self.assertTrue(ok, msg)
        self.assertIn("无改动", msg)                       # 干净树 ⇒ 没有封版提交
        ev = audit_evidence(ws, "M10")
        self.assertEqual(ev["tag"], baseline)
        self.assertTrue(ev["sealed"])
        self.assertEqual(ev["trailers"]["audit-result"], "closed")
        self.assertEqual(ev["trailers"]["audit-seat"], "k3dit@seat")

    def test_tag_without_trailers_is_not_sealed(self) -> None:
        """有 tag 不等于有记录：四键齐才算封版记录（缺键就是缺记录，不猜）。"""
        from k3dge.engine.audit_flow import audit_evidence

        ws = _repo()
        _git(ws, "-c", "user.name=t", "-c", "user.email=t@t", "tag", "-a", "M10", "-m", "hand-made", "HEAD")
        ev = audit_evidence(ws, "M10")
        self.assertTrue(ev["tag"])
        self.assertFalse(ev["sealed"])

    def test_local_job_state_cannot_claim_a_seal(self) -> None:
        """本地账说 `collected`、仓里没有 tag/trailer ⇒ 判"未封"（git 优先）。"""
        from k3dge.engine import audit_flow

        ws = _repo()
        (ws / ".agent").mkdir(exist_ok=True)
        (ws / ".agent" / "audit_jobs.json").write_text(
            '{"jobs": [{"job_id": "J1", "role": "audit", "milestone_id": "M10",'
            ' "state": "collected", "baseline": "deadbeef", "report": "docs/reviews/x.md",'
            ' "counts": {"待修": 0}, "merge_ok": true}]}',
            encoding="utf-8")
        self.assertFalse(audit_flow.audit_evidence(ws, "M10")["sealed"])


class TestGuideStubScanIgnoresMentions(unittest.TestCase):
    """桩判定只认真桩：代码块/行内代码里**提到**标记不得把已写好的文档判成未填（guides_filled）。"""

    def _ws(self, body: str) -> Path:

        ws = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, ws, ignore_errors=True)
        (ws / "docs" / "guides").mkdir(parents=True)
        (ws / "docs" / "guides" / "g.md").write_text(body, encoding="utf-8")
        return ws

    def test_mention_in_code_span_is_not_a_stub(self) -> None:
        from k3dge.engine.seal import scan_unfilled_guides

        ws = self._ws("# G\n\n解释这条闸：`` <!-- k3dge:guide-stub --> `` 会被 seal 前置闸拦。\n")
        self.assertEqual(scan_unfilled_guides(ws), [])
        ws2 = self._ws("# G\n\n```md\n<!-- k3dge:guide-stub -->\n```\n\n正文已写。\n")
        self.assertEqual(scan_unfilled_guides(ws2), [])

    def test_real_marker_still_blocks(self) -> None:
        from k3dge.engine.seal import scan_unfilled_guides

        ws = self._ws("# G\n\n<!-- k3dge:guide-stub -->\n")
        self.assertEqual(scan_unfilled_guides(ws), ["g.md"])
