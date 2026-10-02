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


def _ws() -> Path:
    ws = Path(tempfile.mkdtemp())
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

    def test_unparsable_name_is_none(self) -> None:
        self.assertIsNone(split_task_name("random.md"))
        self.assertIsNone(split_task_name("2026-09-20-M10-unknowntype-x.md"))


class TestReassignTask(TestCase):
    def test_moves_frontmatter_and_filename_together(self) -> None:
        ws = _ws()
        p = _task(ws, "2026-09-20-M10-feat-x.md")
        ok, msg, newp = reassign_task_milestone(ws, p, "M11")
        self.assertTrue(ok, msg)
        self.assertEqual(newp.name, "2026-09-20-M11-feat-x.md")
        self.assertFalse(p.exists())
        # 闸必须绿：两处同改才算重挂成功（半吊子会被 TASK_MILESTONE_MISMATCH 拦）
        rel = newp.relative_to(ws).as_posix()
        self.assertEqual(pure_refs.check_task_consistency(rel, newp.read_text(encoding="utf-8")), [])

    def test_idempotent(self) -> None:
        ws = _ws()
        p = _task(ws, "2026-09-20-M10-feat-x.md")
        reassign_task_milestone(ws, p, "M11")
        again = ws / "docs" / "tasks" / "2026-09-20-M11-feat-x.md"
        ok, msg, newp = reassign_task_milestone(ws, again, "M11")
        self.assertTrue(ok, msg)
        self.assertIn("幂等", msg)
        self.assertEqual(newp, again)

    def test_dry_run_touches_nothing(self) -> None:
        ws = _ws()
        p = _task(ws, "2026-09-20-M10-feat-x.md")
        ok, msg, _ = reassign_task_milestone(ws, p, "M11", dry_run=True)
        self.assertTrue(ok, msg)
        self.assertIn("[dry-run]", msg)
        self.assertTrue(p.exists())
        self.assertIn("milestone: M10", p.read_text(encoding="utf-8"))

    def test_refuses_bad_id_and_bad_name(self) -> None:
        ws = _ws()
        p = _task(ws, "2026-09-20-M10-feat-x.md")
        self.assertFalse(reassign_task_milestone(ws, p, "M 11")[0])       # 非法 id
        bad = _task(ws, "2026-09-20-random.md")
        self.assertFalse(reassign_task_milestone(ws, bad, "M11")[0])      # 名字拆不出段位

    def test_removing_milestone_drops_the_segment(self) -> None:
        ws = _ws()
        p = _task(ws, "2026-09-20-M10-feat-x.md")
        ok, msg, newp = reassign_task_milestone(ws, p, None)
        self.assertTrue(ok, msg)
        self.assertEqual(newp.name, "2026-09-20-feat-x.md")
        self.assertNotIn("milestone:", newp.read_text(encoding="utf-8"))


class TestReassignBulk(TestCase):
    def test_only_matching_milestone_moves(self) -> None:
        ws = _ws()
        _task(ws, "2026-09-20-M10-feat-a.md")
        _task(ws, "2026-09-20-M10-fix-b.done.md")
        _task(ws, "2026-09-19-M9-docs-c.md", milestone="M9")
        ok, lines = reassign_milestone(ws, "M10", "M11")
        self.assertTrue(ok, lines)
        names = sorted(p.name for p in (ws / "docs" / "tasks").glob("*.md"))
        self.assertEqual(names, ["2026-09-19-M9-docs-c.md",
                                 "2026-09-20-M11-feat-a.md",
                                 "2026-09-20-M11-fix-b.done.md"])

    def test_nothing_to_do_is_ok(self) -> None:
        ws = _ws()
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


class TestBoundaryNudge(TestCase):
    """`TASK_MILESTONE_AFTER_BOUNDARY`（advisory）：边界之后新增的票仍挂在边界那一版。"""

    def _repo(self) -> Path:
        ws = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, ws, ignore_errors=True)
        (ws / "docs" / "tasks").mkdir(parents=True)
        (ws / ".agent").mkdir()
        (ws / ".agent" / "milestone").write_text("M10\n", encoding="utf-8")

        def g(*a) -> str:
            # 前置 git **步步查错**（t-298）：旧写法把 rc/stderr 扔了——缺 git、全局
            # gpgsign/hooksPath 让 commit 或 tag 崩时，夹具半初始化往下跑，
            # 红在 `tasks_after_boundary`/`validate_docs` 的下游断言里毫无线索。
            r = subprocess.run(["git", "-C", str(ws), *a], capture_output=True, text=True)
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
        from k3dge.engine import milestone_files

        ws = self._repo()
        p = _task(ws, "2026-09-20-M10-feat-late.md")
        reassign_task_milestone(ws, p, "M11")
        self.assertEqual(milestone_files.tasks_after_boundary(ws), [])

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
