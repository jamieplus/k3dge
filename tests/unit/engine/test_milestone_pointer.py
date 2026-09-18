"""milestone_pointer: id 校验（防路径穿越）+ 游标读写 + bump。"""
import tempfile
import unittest
from pathlib import Path

from k3dge.engine.milestone_pointer import (
    _validate_milestone_id,
    bump_milestone,
    get_current_milestone,
    set_current_milestone,
)


class TestValidateMilestoneId(unittest.TestCase):
    """安全边界：milestone id 会被拼进路径（archive/M10、报告名），必须挡穿越。"""

    def test_rejects_path_traversal(self):
        for bad in ("../evil", "..", "M1/../x", "a/../b"):
            self.assertIsNotNone(_validate_milestone_id(bad), f"must reject: {bad!r}")

    def test_rejects_path_separators(self):
        for bad in ("M1/sub", "M1\\sub", "/abs", "M1/", "sub/M1"):
            self.assertIsNotNone(_validate_milestone_id(bad), f"must reject: {bad!r}")

    def test_rejects_empty_and_whitespace(self):
        for bad in ("", " ", "\t", "\n"):
            self.assertIsNotNone(_validate_milestone_id(bad), f"must reject: {bad!r}")

    def test_rejects_non_alnum_start(self):
        # 正则要求首字符是字母或数字
        for bad in ("-M1", ".M1", "_M1"):
            self.assertIsNotNone(_validate_milestone_id(bad), f"must reject: {bad!r}")

    def test_accepts_normal_ids(self):
        for ok in ("M1", "M10", "M1.2", "M1-x", "M1_x", "adhoc", "0", "a1"):
            self.assertIsNone(_validate_milestone_id(ok), f"must accept: {ok!r}")

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
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                set_current_milestone(Path(d), "../evil")

    def test_corrupt_cursor_falls_back_to_m0(self):
        """坏内容（含穿越串）不得被当游标读出——回落 M0，不崩。"""
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            p = ws / ".agent" / "milestone"
            p.parent.mkdir(parents=True)
            p.write_text("../../etc/passwd\n", encoding="utf-8")
            self.assertEqual(get_current_milestone(ws), "M0")

    def test_empty_cursor_falls_back(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            p = ws / ".agent" / "milestone"
            p.parent.mkdir(parents=True)
            p.write_text("   \n", encoding="utf-8")
            self.assertEqual(get_current_milestone(ws), "M0")


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

    def test_non_m_shape_falls_back_to_suffix(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            set_current_milestone(ws, "adhoc")
            self.assertEqual(bump_milestone(ws), "adhoc-next")

    def test_bump_persists(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d)
            bump_milestone(ws)
            # 新进程语义：重读盘上值
            self.assertEqual(get_current_milestone(ws), "M1")


if __name__ == "__main__":
    unittest.main()
