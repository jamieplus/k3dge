"""milestone_pointer: id 校验（防路径穿越）+ 游标读写 + bump。"""
import tempfile
import unittest
from pathlib import Path

from k3dge.engine.milestone_pointer import (
    MilestoneError,
    _validate_milestone_id,
    bump_milestone,
    get_current_milestone,
    set_current_milestone,
)


class TestValidateMilestoneId(unittest.TestCase):
    """安全边界：milestone id 会被拼进路径（archive/M10、报告名），必须挡穿越。"""

    # 判据形状＝truthiness（t-180）：所有调用方（set/align/seal/task_write）都按
    # `if err:` 决定——返回**假值字符串**（如 `""`）的"拒绝"等于放行。断言必须钉住
    # 被钉的那一层：拒 ⇒ 真值消息；受 ⇒ None（不接受 `""` 冒充通过）。
    def _assert_rejected(self, bad: str) -> None:
        self.assertTrue(_validate_milestone_id(bad), f"must reject: {bad!r}")

    def test_rejects_path_traversal(self):
        for bad in ("../evil", "..", "M1/../x", "a/../b"):
            self._assert_rejected(bad)

    def test_rejects_path_separators(self):
        for bad in ("M1/sub", "M1\\sub", "/abs", "M1/", "sub/M1"):
            self._assert_rejected(bad)

    def test_rejects_empty_and_whitespace(self):
        for bad in ("", " ", "\t", "\n"):
            self._assert_rejected(bad)

    def test_rejects_non_alnum_start(self):
        # 正则要求首字符是字母或数字
        for bad in ("-M1", ".M1", "_M1"):
            self._assert_rejected(bad)

    def test_public_write_path_enforces_the_same_boundary(self) -> None:
        """公开入口对**同一批**危险 id 必须拒（t-181）：私有 `_validate_milestone_id`
        的返回消息形状是白盒细节——哪天它改成抛异常/改名，公开契约（`set_current_milestone`
        拒不安全 id、不写盘）不许跟着漂移。每类形状至少一个代表。"""
        for bad in ("../evil", "M1/sub", "/abs", " ", ""):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as d:
                ws = Path(d)
                with self.assertRaises(MilestoneError):
                    set_current_milestone(ws, bad)
                self.assertFalse((ws / ".agent" / "milestone").exists(),
                                 "拒了但盘已写＝半落地")

    def test_non_string_id_is_rejected_as_milestone_error(self) -> None:
        """非 str id 不得泄 TypeError（ocr2-490）：MCP/ frontmatter 不做类型校验，
        公开契约是"一切拒绝都是 MilestoneError"。"""
        for bad in (123, 0, None, True, ["M1"], {"m": "M1"}, Path("M1")):
            with self.subTest(bad=bad):
                err = _validate_milestone_id(bad)  # type: ignore[arg-type]
                self.assertTrue(err, f"必须拒：{bad!r}")
                self.assertIsInstance(err, str)
        for bad in (123, None, ["M1"], Path("M1")):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as d:
                ws = Path(d)
                with self.assertRaises(MilestoneError):
                    set_current_milestone(ws, bad)  # type: ignore[arg-type]
                try:
                    set_current_milestone(ws, bad)  # type: ignore[arg-type]
                except MilestoneError:
                    pass
                except TypeError:
                    self.fail(f"非 str {bad!r} 泄出 TypeError 而非 MilestoneError")
                self.assertFalse((ws / ".agent" / "milestone").exists())

    def test_accepts_normal_ids(self):
        for ok in ("M1", "M10", "M1.2", "M1-x", "M1_x", "adhoc", "0", "a1"):
            self.assertIsNone(_validate_milestone_id(ok), f"must accept: {ok!r}")

    def test_rejects_overlong_id(self):
        """长度上限 64（t-185）：id 是路径分量（archive/<id>、报告名），不设限＝把
        5000 字符拼进文件名。边界：64 收、65 拒。"""
        self.assertIsNone(_validate_milestone_id("M" + "1" * 63))
        self.assertTrue(_validate_milestone_id("M" + "1" * 64))

    def test_error_message_names_the_id(self):
        err = _validate_milestone_id("../x")
        self.assertIn("../x", err or "")


class TestCursor(unittest.TestCase):
    def test_default_is_m0(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(get_current_milestone(Path(d)), "M0")

    def test_set_then_get(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            set_current_milestone(ws, "M7")
            self.assertEqual(get_current_milestone(ws), "M7")
            self.assertTrue((ws / ".agent" / "milestone").is_file())

    def test_set_rejects_unsafe_id(self):
        """游标失败**全部** `MilestoneError`（t-182）：`MilestoneError ⊂ ValueError`，
        只断言 ValueError 分不出实现回了裸 ValueError 还是公开类——`except
        MilestoneError` 包住读改写序列的调用方接不住不安全 id，正是本契约要防的。
        """
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):      # 兼容面：只按 ValueError 捕获的调用方不受影响
                set_current_milestone(Path(d), "../evil")
            with self.assertRaises(MilestoneError) as cm:
                set_current_milestone(Path(d), "../evil")
            self.assertIs(type(cm.exception), MilestoneError)

    def test_corrupt_cursor_raises(self):
        """坏内容（含穿越串）⇒ 抛 MilestoneError，不得静默回落 M0（ocr-086）。"""
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            p = ws / ".agent" / "milestone"
            p.parent.mkdir(parents=True)
            p.write_text("../../etc/passwd\n", encoding="utf-8")
            with self.assertRaises(MilestoneError):
                get_current_milestone(ws)

    def test_cursor_path_not_a_regular_file_raises(self):
        """形状坏也要响（t-183，ocr-086 的未覆盖面）：旧代码 `not p.is_file()` 直接
        落回 M0——游标位是目录/指目录的符号链接时，`bump` 会以 M0 为基数改写真实位置。
        """
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            p = ws / ".agent" / "milestone"
            p.mkdir(parents=True)
            with self.assertRaises(MilestoneError):
                get_current_milestone(ws)
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            real = ws / "elsewhere"
            real.mkdir()
            link = ws / ".agent"
            link.mkdir(parents=True)
            (link / "milestone").symlink_to(real)   # 指目录的符号链接：exists 但非文件
            with self.assertRaises(MilestoneError):
                get_current_milestone(ws)
            # 指**普通文件**的符号链接是合法游标（is_file 跟随链接）
            (link / "milestone").unlink()
            target = ws / "cur"
            target.write_text("M7\n", encoding="utf-8")
            (link / "milestone").symlink_to(target)
            self.assertEqual(get_current_milestone(ws), "M7")
            # 写侧必须穿透链接写目标，不得替换链接本身（ocr2-491）
            set_current_milestone(ws, "M8")
            self.assertTrue((link / "milestone").is_symlink(), "bump/set 把链接换成了普通文件")
            self.assertEqual(target.read_text(encoding="utf-8").strip(), "M8")
            self.assertEqual(get_current_milestone(ws), "M8")
            self.assertEqual(bump_milestone(ws), "M9")
            self.assertTrue((link / "milestone").is_symlink())
            self.assertEqual(target.read_text(encoding="utf-8").strip(), "M9")

    def test_unreadable_cursor_raises_not_silent_m0(self):
        """ocr-086 三案之一：游标**读不出**（非 UTF-8 / OSError）必须抛（t-184）。

        旧实现把 read_text 的异常折回 M0 之外的静默路径，回归成"回落 M0"就没人红——
        `bump` 会以 M0 为基数把真游标永久改写。非 UTF-8 字节是可移植的失败注入。
        """
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            p = ws / ".agent" / "milestone"
            p.parent.mkdir(parents=True)
            p.write_bytes(b"\xff\xfe M\x0010")   # 非 UTF-8 ⇒ UnicodeDecodeError
            with self.assertRaises(MilestoneError):
                get_current_milestone(ws)

    def test_empty_cursor_raises(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            p = ws / ".agent" / "milestone"
            p.parent.mkdir(parents=True)
            p.write_text("   \n", encoding="utf-8")
            with self.assertRaises(MilestoneError):
                get_current_milestone(ws)


class TestBump(unittest.TestCase):
    def test_m0_to_m1(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(bump_milestone(Path(d)), "M1")

    def test_sequential(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            self.assertEqual(bump_milestone(ws), "M1")
            self.assertEqual(bump_milestone(ws), "M2")
            self.assertEqual(get_current_milestone(ws), "M2")

    def test_m9_to_m10_not_lexical(self):
        """M9 的下一个是 M10（数值），不是 M9→M9x 之类。"""
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            set_current_milestone(ws, "M9")
            self.assertEqual(bump_milestone(ws), "M10")

    def test_non_m_shape_raises(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            set_current_milestone(ws, "adhoc")
            with self.assertRaises(MilestoneError):
                bump_milestone(ws)

    def test_valid_cursor_is_not_always_bumpable(self):
        r"""两份契约钉开（t-185）：校验器的闭集**大于** bump 的 `^M(\d+)$`。
        `M1.2`/`m1`/`M10x`/`0` 是合法游标（validator 收）但 bump 必须**明确拒**，
        不许静默当 M0 起点。
        """
        for cid in ("M1.2", "m1", "M10x", "0", "adhoc"):
            with self.subTest(cid=cid), tempfile.TemporaryDirectory() as d:
                ws = Path(d)
                self.assertIsNone(_validate_milestone_id(cid))
                set_current_milestone(ws, cid)
                with self.assertRaises(MilestoneError):
                    bump_milestone(ws)
                self.assertEqual(get_current_milestone(ws), cid, "拒绝 bump 不得改游标")

    def test_zero_padded_cursor_normalizes_on_bump(self):
        r"""`M01` 匹配 `^M(\d+)$` ⇒ bump 成 `M2`：补零（以及依赖它的排序/归档名）丢失。
        现状如实钉住——要保零就得改 bump 的写出形状，那时这条测必须先翻（t-185）。"""
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            set_current_milestone(ws, "M01")
            self.assertEqual(bump_milestone(ws), "M2")

    def test_bump_persists(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            bump_milestone(ws)
            # 新进程语义：重读盘上值
            self.assertEqual(get_current_milestone(ws), "M1")


class TestBumpLocking(unittest.TestCase):
    """bump 的读-改-写必须持排它锁（丢失更新，ocr2-280）。"""

    def test_read_modify_write_holds_lock(self):
        import os

        try:
            import fcntl
        except ImportError:
            self.skipTest("fcntl unavailable")

        from k3dge.engine import milestone_pointer as mp

        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            seen = {}
            real_get = mp.get_current_milestone

            def spy(w):
                lock = ws / ".agent" / "milestone.lock"
                fd = os.open(str(lock), os.O_RDWR)
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    seen["locked"] = False
                except BlockingIOError:
                    seen["locked"] = True
                finally:
                    os.close(fd)
                return real_get(w)

            from unittest import mock

            with mock.patch.object(mp, "get_current_milestone", spy):
                mp.bump_milestone(ws)
            self.assertTrue(seen.get("locked"), "bump 读-改-写未持排它锁")


if __name__ == "__main__":
    unittest.main()
