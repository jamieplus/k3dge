"""里程碑重挂（ADR-0004 §2.1.9）：票的里程碑事实＝frontmatter + 文件名两处，必须同改。"""

import subprocess
import tempfile
from pathlib import Path
from unittest import TestCase

from k3dge.engine import pure_refs
from k3dge.engine.task_write import (
    build_task_name,
    reassign_milestone,
    reassign_task_milestone,
    split_task_name,
)
import shutil
import atexit


# ocr2-796：atexit 只在解释器正常退出时清——传进 TestCase 时按测回收
# （同 test_seal_flow.TestSealFlowEdges._ws 的正确形状）。
def _ws(tc=None) -> Path:
    ws = Path(tempfile.mkdtemp())
    if tc is not None:
        tc.addCleanup(shutil.rmtree, ws, ignore_errors=True)
    else:
        atexit.register(shutil.rmtree, ws, True)
    (ws / "docs" / "tasks").mkdir(parents=True)
    (ws / ".agent").mkdir()
    (ws / ".agent" / "milestone").write_text("M10\n", encoding="utf-8")
    return ws


def _task(ws: Path, name: str, milestone: str = "M10") -> Path:
    p = ws / "docs" / "tasks" / name
    p.write_text(
        f"---\nstatus: idea\nmilestone: {milestone}\npriority: P2\ndate: 2026-09-20\n---\n\n# X\n",
        encoding="utf-8",
    )
    return p


class TestNameParts(TestCase):
    def test_split_and_rebuild_roundtrip(self) -> None:
        parts = split_task_name("2026-09-20-M10-feat-x_y.done.md")
        self.assertEqual(parts["date"], "2026-09-20")
        self.assertEqual(parts["ms"], "M10")
        self.assertEqual(parts["type"], "feat")
        self.assertEqual(parts["slug"], "x_y")
        self.assertEqual(parts["done"], ".done")
        self.assertEqual(build_task_name(parts, "M11"), "2026-09-20-M11-feat-x_y.done.md")
        self.assertEqual(build_task_name(parts, None), "2026-09-20-feat-x_y.done.md")

    def test_compound_slug_keeps_every_segment(self) -> None:
        """ocr2-534：slug 自身以类型词开头时不得被吞。旧贪婪 `ms` 把
        `M10-fix-refactor-x` 拆成 ms=`M10-fix`/type=`refactor`/slug=`x` ⇒ 重挂时
        `fix-` 段从文件名静默消失（数据丢失）。"""
        parts = split_task_name("2026-09-20-M10-fix-refactor-x.md")
        self.assertEqual(parts["ms"], "M10", parts)
        self.assertEqual(parts["type"], "fix", parts)
        self.assertEqual(parts["slug"], "refactor-x", parts)
        self.assertEqual(build_task_name(parts, "M11"), "2026-09-20-M11-fix-refactor-x.md")
        # 里程碑段本身带 `-` 的合法名仍不能丢段
        p2 = split_task_name("2026-09-20-M1-x-fix-y.md")
        self.assertEqual((p2["ms"], p2["type"], p2["slug"]), ("M1-x", "fix", "y"), p2)

    def test_unparsable_name_is_none(self) -> None:
        self.assertIsNone(split_task_name("random.md"))
        self.assertIsNone(split_task_name("2026-09-20-M10-unknowntype-x.md"))


class TestReassignTask(TestCase):
    def test_moves_frontmatter_and_filename_together(self) -> None:
        ws = _ws(self)
        p = _task(ws, "2026-09-20-M10-feat-x.md")
        ok, msg, newp = reassign_task_milestone(ws, p, "M11")
        self.assertTrue(ok, msg)
        self.assertEqual(newp.name, "2026-09-20-M11-feat-x.md")
        self.assertFalse(p.exists())
        # 闸必须绿：两处同改才算重挂成功（半吊子会被 TASK_MILESTONE_MISMATCH 拦）
        rel = newp.relative_to(ws).as_posix()
        self.assertEqual(pure_refs.check_task_consistency(rel, newp.read_text(encoding="utf-8")), [])

    def test_idempotent(self) -> None:
        ws = _ws(self)
        p = _task(ws, "2026-09-20-M10-feat-x.md")
        reassign_task_milestone(ws, p, "M11")
        again = ws / "docs" / "tasks" / "2026-09-20-M11-feat-x.md"
        ok, msg, newp = reassign_task_milestone(ws, again, "M11")
        self.assertTrue(ok, msg)
        self.assertIn("幂等", msg)
        self.assertEqual(newp, again)

    def test_dry_run_touches_nothing(self) -> None:
        ws = _ws(self)
        p = _task(ws, "2026-09-20-M10-feat-x.md")
        ok, msg, target = reassign_task_milestone(ws, p, "M11", dry_run=True)
        self.assertTrue(ok, msg)
        self.assertIn("[dry-run]", msg)
        self.assertTrue(p.exists())
        self.assertIn("milestone: M10", p.read_text(encoding="utf-8"))
        # ocr2-797：只断源文件不动时，dry-run 顺手把改名副本落盘也照样绿——
        # 目标文件名必须仍不存在（函数返回的正是目标路径）。
        self.assertIsNotNone(target)
        self.assertFalse(target.exists(), f"dry-run 落下了目标文件：{target}")

    def test_refuses_bad_id_and_bad_name(self) -> None:
        ws = _ws(self)
        p = _task(ws, "2026-09-20-M10-feat-x.md")
        self.assertFalse(reassign_task_milestone(ws, p, "M 11")[0])       # 非法 id
        bad = _task(ws, "2026-09-20-random.md")
        self.assertFalse(reassign_task_milestone(ws, bad, "M11")[0])      # 名字拆不出段位

    def test_removing_milestone_drops_the_segment(self) -> None:
        ws = _ws(self)
        p = _task(ws, "2026-09-20-M10-feat-x.md")
        ok, msg, newp = reassign_task_milestone(ws, p, None)
        self.assertTrue(ok, msg)
        self.assertEqual(newp.name, "2026-09-20-feat-x.md")
        self.assertNotIn("milestone:", newp.read_text(encoding="utf-8"))


class TestReassignBulk(TestCase):
    def test_only_matching_milestone_moves(self) -> None:
        ws = _ws(self)
        _task(ws, "2026-09-20-M10-feat-a.md")
        _task(ws, "2026-09-20-M10-fix-b.done.md")
        _task(ws, "2026-09-19-M9-docs-c.md", milestone="M9")
        ok, lines = reassign_milestone(ws, "M10", "M11")
        self.assertTrue(ok, lines)
        names = sorted(p.name for p in (ws / "docs" / "tasks").glob("*.md"))
        self.assertEqual(names, ["2026-09-19-M9-docs-c.md",
                                 "2026-09-20-M11-feat-a.md",
                                 "2026-09-20-M11-fix-b.done.md"])
        # ocr2-798：只断文件名时"改名而 frontmatter 仍挂 M10"的半迁移照样绿——
        # 单票测的两处同改不变式在这里逐票复验（只查里程碑档：`.done.md` 夹具
        # 自带的 status/结案形态与重挂无关，不在此断）。
        # 负对照：半迁移（改名 M11 而 frontmatter 仍 M10）必须真触发该码——
        # 否则上面的 NotIn 是"闸根本不跑"的假绿。
        half = ("---\nstatus: idea\nmilestone: M10\npriority: P2\ndate: 2026-09-20\n---\n\n# X\n")
        half_codes = [c for c, _ in pure_refs.check_task_consistency(
            "docs/tasks/2026-09-20-M11-feat-a.md", half)]
        self.assertIn("TASK_MILESTONE_MISMATCH", half_codes, half_codes)
        for name in ("2026-09-20-M11-feat-a.md", "2026-09-20-M11-fix-b.done.md"):
            moved = ws / "docs" / "tasks" / name
            rel = moved.relative_to(ws).as_posix()
            codes = [c for c, _ in pure_refs.check_task_consistency(
                rel, moved.read_text(encoding="utf-8"))]
            self.assertNotIn("TASK_MILESTONE_MISMATCH", codes, (name, codes))

    def test_nothing_to_do_is_ok(self) -> None:
        ws = _ws(self)
        _task(ws, "2026-09-20-M11-feat-a.md", milestone="M11")
        ok, lines = reassign_milestone(ws, "M10", "M11")
        self.assertTrue(ok, lines)
        self.assertIn("没有 M10 的票", lines[0])

    def test_unreadable_ticket_does_not_half_migrate(self) -> None:
        """坏文件让整批在循环中途抛异常 ⇒ 前面的票已改、后面的没改（334）。

        自 `TestBoundaryNudge` 挪来（t-299）：这是**批量重挂**的行为测，advisory 类里
        放着它，读者会以为"边界提醒"也讲"坏票不挡批"。
        两处收口：①`chmod(0o000)` 只在非 root 的 POSIX 上挡读（CI 容器常 root、
        Windows 只切只读位）——前提可能静默消失（t-296）。换成同名**目录**占住
        `.md` 路径：`read_text` 恒抛 OSError，跨平台确定；②坏票必须排在**前**：
        `sorted(glob)` 下旧夹具它最后读，"遇坏即中止"的实现同样留下 call_count==1，
        断言空转（t-297）。再断被迁移的正是那张好票。
        """
        from unittest import mock

        ws = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, ws, ignore_errors=True)
        d = ws / "docs" / "tasks"
        d.mkdir(parents=True)
        bad = d / "2026-08-01-M10-feat-zz-bad.md"      # 排最前（sorted 序）
        bad.mkdir()
        good = d / "2026-09-02-M10-feat-a.md"
        good.write_text(
            "---\nmilestone: M10\nstatus: idea\n---\n\n# A\n", encoding="utf-8")
        with mock.patch("k3dge.engine.task_write.reassign_task_milestone",
                        side_effect=lambda *a, **k: (True, "moved", None)) as rr:
            ok, lines = reassign_milestone(ws, "M10", "M11")
        self.assertFalse(ok, lines)
        self.assertTrue([l for l in lines if "读不出" in l], lines)
        self.assertEqual(rr.call_count, 1, "读不出的票不得挡掉别的票，也不得半途崩")
        self.assertEqual(rr.call_args_list[0].args[1], good,
                         f"被迁移的必须是好票：{rr.call_args_list}")

    def test_apply_failure_does_not_abort_batch(self) -> None:
        """apply 阶段某张抛异常只记 FAIL，不中止整批（ocr2-326）。"""
        from unittest import mock

        ws = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, ws, ignore_errors=True)
        d = ws / "docs" / "tasks"
        d.mkdir(parents=True)
        (d / "2026-09-01-M10-feat-a.md").write_text(
            "---\nmilestone: M10\nstatus: idea\n---\n\n# a\n", encoding="utf-8")
        (d / "2026-09-02-M10-feat-b.md").write_text(
            "---\nmilestone: M10\nstatus: idea\n---\n\n# b\n", encoding="utf-8")

        def _fake(_ws, p, _ms, dry_run=False):
            if p.name.endswith("a.md"):
                raise OSError("boom")
            return True, "moved", None

        with mock.patch("k3dge.engine.task_write.reassign_task_milestone", side_effect=_fake) as rr:
            ok, lines = reassign_milestone(ws, "M10", "M11")
        self.assertFalse(ok)
        self.assertTrue(any("应用失败" in l for l in lines), lines)
        self.assertEqual(rr.call_count, 2, "坏的不挡后面的票")


class TestBoundaryNudge(TestCase):
    """`TASK_MILESTONE_AFTER_BOUNDARY`（advisory）：边界之后新增的票仍挂在边界那一版。"""

    def _repo(self) -> Path:
        import os

        ws = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, ws, ignore_errors=True)
        (ws / "docs" / "tasks").mkdir(parents=True)
        (ws / ".agent").mkdir()
        (ws / ".agent" / "milestone").write_text("M10\n", encoding="utf-8")
        # ocr2-799：宿主 global/system git 配置（commit.gpgsign/tag.gpgsign/
        # core.hooksPath/alias.*）会让种子提交或注解 tag 崩，前置半初始化后
        # 红在下游断言里毫无线索。钉死配置隔离，断言只反映被测行为。
        env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")

        def g(*a) -> str:
            # 前置 git **步步查错**（t-298）：旧写法把 rc/stderr 扔了——缺 git、全局
            # gpgsign/hooksPath 让 commit 或 tag 崩时，夹具半初始化往下跑，
            # 红在 `tasks_after_boundary`/`validate_docs` 的下游断言里毫无线索。
            r = subprocess.run(["git", "-C", str(ws), *a], capture_output=True,
                               text=True, env=env)
            if r.returncode != 0:
                raise RuntimeError(f"git {' '.join(a)} 失败：{(r.stderr or r.stdout).strip()}")
            return r.stdout

        g("init", "-q")
        (ws / "seed.md").write_text("seed\n", encoding="utf-8")
        g("add", "-A")
        g("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--no-verify", "-m", "chore: seed")
        g("-c", "user.name=t", "-c", "user.email=t@t", "tag", "-a", "M10", "-m", "boundary")
        return ws

    def test_task_added_after_boundary_and_still_labelled_is_reported(self) -> None:
        from k3dge.engine import doc_catalog, milestone_files

        ws = self._repo()
        _task(ws, "2026-09-20-M10-feat-late.md")          # 边界之后新增，仍挂 M10
        rows = milestone_files.tasks_after_boundary(ws)
        self.assertEqual([r[0] for r in rows], ["docs/tasks/2026-09-20-M10-feat-late.md"])
        self.assertEqual(rows[0][1], "M10")
        codes = [v.rule_id for v in doc_catalog.validate_docs(ws, ["tasks"])
                 if v.rule_id == "TASK_MILESTONE_AFTER_BOUNDARY"]
        self.assertEqual(codes, ["TASK_MILESTONE_AFTER_BOUNDARY"])

    def test_reassigned_task_is_not_reported(self) -> None:
        from k3dge.engine import doc_catalog, milestone_files

        ws = self._repo()
        p = _task(ws, "2026-09-20-M10-feat-late.md")
        # 正对照（ocr2-535）：重挂前**确实**被报——否则后面的"清空"可能只是检测空转。
        self.assertEqual([r[0] for r in milestone_files.tasks_after_boundary(ws)],
                         ["docs/tasks/2026-09-20-M10-feat-late.md"])
        self.assertIn("TASK_MILESTONE_AFTER_BOUNDARY",
                      [v.rule_id for v in doc_catalog.validate_docs(ws, ["tasks"])])
        ok, msg, _ = reassign_task_milestone(ws, p, "M11")
        self.assertTrue(ok, msg)                       # 重挂本身必须成功
        self.assertEqual(milestone_files.tasks_after_boundary(ws), [])
        self.assertNotIn("TASK_MILESTONE_AFTER_BOUNDARY",
                         [v.rule_id for v in doc_catalog.validate_docs(ws, ["tasks"])])

    def test_advisory_never_blocks(self) -> None:
        from k3dge.engine import doc_catalog, gate_facts
        from k3dge.engine.models import Violation

        self.assertEqual(gate_facts.severity("TASK_MILESTONE_AFTER_BOUNDARY"), "warn")
        v = Violation("TASK_MILESTONE_AFTER_BOUNDARY", "m",
                      file_path="docs/tasks/x.md", detail={"path": "docs/tasks/x.md", "milestone": "M10"})
        self.assertTrue(v.format().startswith("[GATE WARN]"))
        self.assertIn("k3dge milestone reassign M10", v.format())


class TestTaskWriteGuards(TestCase):
    def _ws(self) -> Path:
        ws = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, ws, ignore_errors=True)
        (ws / "docs" / "tasks").mkdir(parents=True)
        (ws / "docs" / "reviews").mkdir(parents=True)
        return ws

    def test_create_task_rejects_bad_priority_and_newlines(self) -> None:
        from k3dge.engine.task_write import create_task

        ws = self._ws()
        ok, msg, _ = create_task(ws, "t", priority="urgent")
        self.assertFalse(ok)
        self.assertIn("invalid priority", msg)
        ok2, _, p2 = create_task(ws, "t2", priority="P1", report="docs/reviews/r.md\ninjected: x")
        self.assertTrue(ok2)
        self.assertNotIn("injected", p2.read_text(encoding="utf-8"))

    def test_mark_done_refuses_unreadable_report(self) -> None:
        from k3dge.engine.task_write import mark_task_done

        ws = self._ws()
        tp = ws / "docs" / "tasks" / "2026-10-02-M10-fix-x.md"
        tp.write_text("---\nstatus: idea\nmilestone: M10\npriority: P2\ndate: 2026-10-02\nreport: docs/reviews/missing.md\n---\n\n# X\n", encoding="utf-8")
        ok, msg = mark_task_done(ws, str(tp))[:2]
        self.assertFalse(ok)
        self.assertIn("不可读", msg)

    def test_reassign_checks_target_before_writing(self) -> None:
        ws = self._ws()
        a = ws / "docs" / "tasks" / "2026-10-02-M10-fix-a.md"
        b = ws / "docs" / "tasks" / "2026-10-02-M11-fix-a.md"
        a.write_text("---\nstatus: idea\nmilestone: M10\npriority: P2\ndate: 2026-10-02\n---\n\n# A\n", encoding="utf-8")
        b.write_text("---\nstatus: idea\nmilestone: M11\npriority: P2\ndate: 2026-10-02\n---\n\n# B\n", encoding="utf-8")
        ok, msg, _ = reassign_task_milestone(ws, a, "M11")
        self.assertFalse(ok)
        # 原文未动：内容仍是 M10（ocr2-084 的腐票形态不得出现）
        self.assertIn("milestone: M10", a.read_text(encoding="utf-8"))

    def test_row_match_requires_min_length(self) -> None:
        """短描述/短标题不得让模糊配对近乎无条件命中（ocr2-322）。"""
        from k3dge.engine.task_write import _row_hits_task

        self.assertFalse(_row_hits_task({"问题描述": "无", "ID": "X"}, "这是一条很长的任务标题", "stem"))
        self.assertFalse(_row_hits_task({"问题描述": "路径错", "ID": "X"}, "修复路径错误的任务", "stem"))
        self.assertTrue(_row_hits_task({"问题描述": "修复登录超时的竞态问题", "ID": "X"},
                                       "修复登录超时", "stem"))

    def test_backfill_added_even_when_name_appears_elsewhere(self) -> None:
        """票名已在 `处置` 格出现，也必须在回填段新增一行（ocr2-323）。"""
        from k3dge.engine.task_write import _ensure_backfill_section

        lines = ["# 报告", "", "| A | 已修 → 2026-10-02-M10-fix-x.md |", "",
                 "## 回填 — 自动", "", "> | old |"]
        _ensure_backfill_section(lines, "\n".join(lines), "2026-10-02-M10-fix-x.md", "A")
        self.assertIn("> | 2026-10-02-M10-fix-x.md | 已修 | 自动回填 |", "\n".join(lines))

    def test_body_status_cannot_bypass_report_gate(self) -> None:
        """有 frontmatter 时正文游离的 `Status: done` 不得绕过报告闸（ocr2-324）。"""
        from k3dge.engine.task_write import mark_task_done

        ws = self._ws()
        rep = ws / "docs" / "reviews" / "r.md"
        rep.write_text(
            "| ID | 日期 | 严重度 | 优先级 | 类型 | 问题描述 | 位置 | 状态 | 处置 | 验证 | 复审 | 验收 |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
            "| A | 2026-10-02 | 中 | P2 | 缺陷 | d | f:1 | 待修 |  |  |  |  |\n",
            encoding="utf-8")
        tp = ws / "docs" / "tasks" / "2026-10-02-M10-fix-x.md"
        tp.write_text(
            "---\nstatus: idea\nmilestone: M10\npriority: P2\ndate: 2026-10-02\n"
            "report: docs/reviews/r.md\n---\n\n# X\n- **Status**: done\n", encoding="utf-8")
        ok, msg = mark_task_done(ws, str(tp))[:2]
        self.assertFalse(ok)
        self.assertIn("待修", msg)
