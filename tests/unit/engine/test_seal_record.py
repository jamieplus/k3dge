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


class _RepoMixin:
    """临时仓 helper：**按测**回收 + 按测隔离 `GIT_CEILING_DIRECTORIES`（ocr2-523）。

    旧形状是模块级 `_repo()`：全局改 `os.environ` 且只在 `atexit` 回收——
    ①覆盖调用方设的 ceiling；②保护是执行顺序的副作用，同进程后续测试跑在残留值下；
    ③崩溃/中止的 run 里临时仓堆到会话结束。现在每次调用登记 `addCleanup`
    （rmtree + 还原 env），作用域归调用它的那个测试。
    """

    def _repo(self) -> Path:
        root = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        prev = os.environ.get("GIT_CEILING_DIRECTORIES")
        os.environ["GIT_CEILING_DIRECTORIES"] = str(root.parent)

        def _restore() -> None:
            if prev is None:
                os.environ.pop("GIT_CEILING_DIRECTORIES", None)
            else:
                os.environ["GIT_CEILING_DIRECTORIES"] = prev

        self.addCleanup(_restore)
        _git(root, "init", "-q")
        _git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit",
             "-q", "--no-verify", "--allow-empty", "-m", "chore: init")
        return root


class TestTrailerFormat(_RepoMixin, TestCase):
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
        """ocr2-525：必须走**真 git `%(trailers)` 形状**（首个后续行 4 空格缩进），
        而不是空串退化成 `parse_seal_trailers("") == {}`。旧夹具仓只有无 trailer 的
        init 提交、`_git()` 又 strip，`key.strip()` 的缩进分支从未被走。"""
        ws = self._repo()
        _git(ws, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--no-verify",
             "--allow-empty", "-m", "chore: with trailers",
             "-m", "Seal-milestone: M10\nAudit-baseline: abc1234\nAudit-seat: k3dit@seat\nAudit-result: closed")
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_CONFIG")}
        env["GIT_CONFIG_GLOBAL"] = os.devnull
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        r = subprocess.run(["git", "-C", str(ws), "log", "-1", "--format=%(trailers)"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        raw = r.stdout
        self.assertIn("Seal-milestone: M10", raw, f"没拿到真 trailer 输出：{raw!r}")
        parsed = parse_seal_trailers(raw)
        self.assertEqual(parsed["seal-milestone"], "M10")
        self.assertEqual(parsed["audit-baseline"], "abc1234")
        self.assertEqual(parsed["audit-seat"], "k3dit@seat")
        self.assertEqual(parsed["audit-result"], "closed")
        # `key.strip()` 的缩进分支（git 在部分形状/版本下续行带 4 空格缩进）显式覆盖
        indented = parse_seal_trailers("    Seal-milestone: M10\n    Audit-result: closed")
        self.assertEqual(indented["seal-milestone"], "M10")
        self.assertEqual(indented["audit-result"], "closed")


class TestSealRecord(_RepoMixin, TestCase):
    def test_commit_carries_trailers_and_tag_points_at_baseline(self) -> None:
        ws = self._repo()
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
        ws = self._repo()
        baseline = _git(ws, "rev-parse", "HEAD")
        ok, msg = seal_record(ws, "M11", baseline=baseline, result="closed")
        self.assertTrue(ok, msg)
        self.assertEqual(_git(ws, "rev-list", "--count", "HEAD"), "1")  # 只有 init
        self.assertEqual(_git(ws, "rev-parse", "M11^{commit}"), baseline)  # durable 边界在

    def test_reentrant_seal_record_is_idempotent(self) -> None:
        """code-7 正面回应：seal 是幂等重入入口。基线不变时重跑 `seal_record`
        ⇒ 不追加第二份提交、边界 tag 不移动 ⇒ git 事实唯一，本地账只是投影
        （声明面 `on_rerun=append` 落的是可重建投影，judged 只读 tag+trailer）。"""
        ws = self._repo()
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

    def test_invalid_id_refuses_before_any_commit(self) -> None:
        """非法里程碑 id 在提交**之前**被拒：不留悬空封版提交（ocr2-311）。"""
        ws = self._repo()
        (ws / "f.md").write_text("x\n", encoding="utf-8")     # 脏树 ⇒ 否则无提交可观察
        before = _git(ws, "rev-list", "--count", "HEAD")
        ok, _msg = seal_record(ws, "M 10", baseline=_git(ws, "rev-parse", "HEAD"),
                               result="closed")
        self.assertFalse(ok)
        self.assertEqual(_git(ws, "rev-list", "--count", "HEAD"), before)   # 无封版提交


class TestTagBoundary(_RepoMixin, TestCase):
    def test_idempotent_same_target_and_refuses_move(self) -> None:
        ws = self._repo()
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
        ws = self._repo()
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


class TestTrailerSanitization(_RepoMixin, TestCase):
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


class TestAuditEvidence(_RepoMixin, TestCase):
    """判据只认 git 事实；本地账是投影，**冲突以 git 为准**（ADR-0004 §2.1.10）。"""

    def test_absent_tag_means_not_sealed(self) -> None:
        from k3dge.engine.audit_flow import audit_evidence

        ws = self._repo()
        ev = audit_evidence(ws, "M10")
        self.assertEqual(ev, {"tag": "", "trailers": {}, "sealed": False})

    def test_tag_with_trailers_is_sealed(self) -> None:
        """干净树也要能读回记录：`_commit_all` 不造空提交 ⇒ tag 注解是第二载体。"""
        from k3dge.engine.audit_flow import audit_evidence

        ws = self._repo()
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

        ws = self._repo()
        _git(ws, "-c", "user.name=t", "-c", "user.email=t@t", "tag", "-a", "M10", "-m", "hand-made", "HEAD")
        ev = audit_evidence(ws, "M10")
        self.assertTrue(ev["tag"])
        self.assertFalse(ev["sealed"])

    def test_local_job_state_cannot_claim_a_seal(self) -> None:
        """本地账说 `collected`、仓里没有 tag/trailer ⇒ 判"未封"（git 优先）。"""
        import json

        from k3dge.engine import audit_flow

        ws = self._repo()
        (ws / ".agent").mkdir(exist_ok=True)
        raw = ('{"jobs": [{"job_id": "J1", "role": "audit", "milestone_id": "M10",'
               ' "state": "collected", "baseline": "deadbeef", "report": "docs/reviews/x.md",'
               ' "counts": {"待修": 0}, "merge_ok": true}]}')
        (ws / ".agent" / "audit_jobs.json").write_text(raw, encoding="utf-8")
        # ocr2-785：先证夹具真是"会认领封版的账"——JSON 坏掉/键名拼错时，
        # `sealed is False` 是"账不可读"而非"git 优先"，本测就白跑了。
        jobs = [j for j in json.loads(raw)["jobs"]
                if j.get("milestone_id") == "M10" and j.get("state") == "collected"]
        self.assertEqual(len(jobs), 1, f"夹具不再是 M10 的 collected 账：{raw}")
        self.assertFalse(audit_flow.audit_evidence(ws, "M10")["sealed"])

    def test_uppercase_baseline_is_still_sealed(self) -> None:
        """ocr2-208：基线大小写不敏感（写侧允许大写，读侧不得因大小写判未封）。"""
        from k3dge.engine.audit_flow import audit_evidence

        ws = self._repo()
        sha = _git(ws, "rev-parse", "HEAD")
        _git(ws, "-c", "user.name=t", "-c", "user.email=t@t", "tag", "-a", "M10", "-m",
             format_seal_trailers("M10", sha.upper(), "k3dit@seat", "closed"), "HEAD")
        self.assertTrue(audit_evidence(ws, "M10")["sealed"])

    def test_tag_annotation_must_match_requested_milestone(self) -> None:
        """ocr2-207：第二载体（tag 注解）的 `seal-milestone` 必须等于本轮，与提交 trailer 同闸。"""
        from k3dge.engine.audit_flow import audit_evidence

        ws = self._repo()
        sha = _git(ws, "rev-parse", "HEAD")
        _git(ws, "-c", "user.name=t", "-c", "user.email=t@t", "tag", "-a", "M10", "-m",
             format_seal_trailers("M9", sha, "k3dit@seat", "closed"), "HEAD")
        self.assertFalse(audit_evidence(ws, "M10")["sealed"])

    def test_unreadable_tag_reports_error_not_only_unsealed(self) -> None:
        """ocr2-206：tag 读不出来（坏 ref/对象缺失）必须带 error，不得静默判"未封"。"""
        from unittest import mock

        from k3dge.engine.audit_flow import audit_evidence

        ws = self._repo()

        class _R:
            def __init__(self, rc, out="", err=""):
                self.returncode, self.stdout, self.stderr = rc, out, err

        def fake(cmd, **k):
            if "--git-dir" in cmd:
                return _R(0, ".git\n")
            if "rev-parse" in cmd and "--verify" in cmd:
                return _R(128, "", "fatal: bad object")
            return _R(0, "", "")

        with mock.patch("subprocess.run", side_effect=fake):
            ev = audit_evidence(ws, "M10")
        self.assertFalse(ev["sealed"])
        self.assertIn("tag 读不出", ev.get("error", ""), ev)

    def test_non_ascii_git_output_survives_ascii_locale(self) -> None:
        """ocr2-205：`git for-each-ref` 输出非 ASCII 时按 UTF-8 解码，ASCII locale 不崩栈。"""
        import locale

        from k3dge.engine.audit_flow import audit_evidence

        ws = self._repo()
        _git(ws, "-c", "user.name=t", "-c", "user.email=t@t", "tag", "-a", "M10", "-m",
             "备注：中文", "HEAD")
        orig = locale.getencoding
        locale.getencoding = lambda: "ascii"
        try:
            ev = audit_evidence(ws, "M10")      # 不得抛 UnicodeDecodeError
        finally:
            locale.getencoding = orig
        self.assertIsInstance(ev, dict)


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
